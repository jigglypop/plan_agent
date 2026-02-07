"""
AI 에이전트 코어
ReAct 패턴: 도구 호출 -> 결과 확인 -> 추가 도구 호출 or 최종 응답
"""
import os
import json
from typing import Dict, Any

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

from src.data import load_posts, get_post_stats
from src.data.parser import enrich_posts_with_files
from src.vectordb import VectorStore
from src.notion import NotionClient
from src.agent.tools import TOOLS, ToolExecutor
from src.agent.memory import Memory


SYSTEM_PROMPT = """당신은 멘사코리아 기획위원회의 AI 에이전트입니다.

기획위원회는 멘사코리아의 계절 행사(신년회/봄/여름/가을/겨울)를 기획하고 운영하는 위원회입니다.
2005년부터 현재까지 약 20년간의 게시판 데이터(회의록, 예산안, 행사 기획, 결산, 장소 견적 등)에 접근할 수 있습니다.

역할:
1. 과거 행사 검색 및 정보 제공 (예산, 장소, 참석자 수, 견적 등)
2. 회의록 검색 및 요약
3. 예산/결산 관련 자료 검색 및 분석
4. 행사 기획 시 참고 자료 제공 (과거 유사 행사 기반)
5. 노션에 행사/체크리스트 생성
6. 위원회 운영 관련 정보 제공

도구 사용 규칙:
- 복잡한 질문은 여러 도구를 순차적으로 호출하여 답변 (예: 검색 -> 상세 조회 -> 분석)
- search_posts로 관련 게시글을 찾고, 필요하면 get_post로 전문을 확인
- 수치가 있으면 구체적으로 제시하고 출처(게시글 제목, 날짜)를 함께 안내
- 모르는 내용은 모른다고 솔직하게 답변

응답 규칙:
- 한국어로 간결하고 정확하게 답변
- 이모지 사용 금지
"""

MAX_TOOL_STEPS = 5


class Agent:
    """AI 에이전트 - ReAct 패턴 + 영속 기억"""

    def __init__(self):
        self.client = None
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.posts = load_posts()
        enrich_posts_with_files(self.posts)
        self.vector_store = VectorStore()
        self.notion = NotionClient()
        self.memory = Memory()
        self.executor = ToolExecutor(self.posts, self.vector_store, self.notion)

        # 런타임 세션 (도구 호출 포함 전체 메시지)
        self._sessions: Dict[str, list] = {}

    def is_ready(self) -> Dict[str, Any]:
        return {
            "openai": self.client is not None,
            "notion": self.notion.is_connected(),
            "data_loaded": len(self.posts) > 0,
            "posts_count": len(self.posts),
            "vectordb": self.vector_store.get_stats(),
        }

    def reset(self, session_id: str = "default"):
        self._sessions.pop(session_id, None)
        self.memory.clear(session_id)

    def chat(self, user_message: str, session_id: str = "default") -> str:
        if not self.client:
            return self._fallback(user_message)

        messages = self._get_session(session_id)
        messages.append({"role": "user", "content": user_message})
        self.memory.save(session_id, "user", user_message)

        try:
            return self._react_loop(messages, session_id)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"

    def _react_loop(self, messages: list, session_id: str) -> str:
        """ReAct 루프: 도구 호출 -> 결과 확인 -> 반복 or 최종 응답"""
        for _ in range(MAX_TOOL_STEPS):
            response = self.client.chat.completions.create(
                model="gpt-5.2",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=TOOLS,
                tool_choice="auto",
            )

            msg = response.choices[0].message

            if not msg.tool_calls:
                content = msg.content or ""
                messages.append({"role": "assistant", "content": content})
                self.memory.save(session_id, "assistant", content)
                return content

            # 도구 호출 실행
            messages.append(msg)
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                result = self.executor.run(tc.function.name, args)
                messages.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        # MAX_TOOL_STEPS 소진 시 강제 최종 응답
        response = self.client.chat.completions.create(
            model="gpt-5.2",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        )
        content = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": content})
        self.memory.save(session_id, "assistant", content)
        return content

    def _get_session(self, session_id: str) -> list:
        """세션 메시지 가져오기 (없으면 영속 기억에서 복원)"""
        if session_id not in self._sessions:
            history = self.memory.load(session_id, limit=10)
            self._sessions[session_id] = history
        return self._sessions[session_id]

    def _fallback(self, message: str) -> str:
        """GPT 없이 기본 응답"""
        msg = message.lower()

        if any(k in msg for k in ["통계", "현황"]):
            stats = get_post_stats(self.posts)
            lines = [
                "게시글 통계:",
                f"- 총 게시글: {stats['total_posts']}건",
                f"- 총 첨부파일: {stats['total_files']}개",
                f"- 기간: {stats['year_range']}",
                "",
                "연도별 게시글:",
            ]
            for y, c in list(stats["by_year"].items())[-10:]:
                lines.append(f"  {y}년: {c}건")
            return "\n".join(lines)

        if any(k in msg for k in ["검색", "찾아", "알려"]):
            results = self.vector_store.search_posts(message, 5)
            if not results:
                return "검색 결과가 없습니다."
            lines = ["검색 결과:"]
            for r in results:
                meta = r.get("metadata", {})
                lines.append(
                    f"- [{meta.get('date', '')}] {meta.get('title', '')} ({meta.get('author', '')})"
                )
            return "\n".join(lines)

        stats = get_post_stats(self.posts)
        return (
            f"기획위원회 AI 에이전트입니다.\n"
            f"현재 {stats['total_posts']}건의 게시글 데이터에 접근 가능합니다.\n\n"
            f"질문 예시:\n"
            f'- "2024 겨울행사 예산 알려줘"\n'
            f'- "글램핑 행사 찾아줘"\n'
            f'- "작년 회의록 보여줘"\n'
            f'- "예산안 파일 목록"\n\n'
            f"GPT 연동 시 더 자연스러운 대화가 가능합니다."
        )
