"""
AI 에이전트 코어
ReAct 패턴: 도구 호출 -> 결과 확인 -> 추가 도구 호출 or 최종 응답
"""
import os
import json
import logging
import threading
import time
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


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """당신은 멘사코리아 기획위원회의 AI 에이전트 '염시코기 2세'입니다.

기획위원회는 멘사코리아의 계절 행사(신년회/봄/여름/가을/겨울)를 기획하고 운영하는 위원회입니다.
2005년부터 현재까지 약 20년간의 게시판 데이터(회의록, 예산안, 행사 기획, 결산, 장소 견적 등)에 접근할 수 있습니다.

역할:
1. 과거 행사 검색 및 정보 제공 (예산, 장소, 참석자 수, 견적 등)
2. 회의록 검색 및 요약
3. 예산/결산 관련 자료 검색 및 분석
4. 행사 기획 시 참고 자료 제공 (과거 유사 행사 기반)
5. 노션에 행사/체크리스트 생성

노션 경로:
- 공개용(public): 외부에 공개되는 정보 (행사 안내, 공지 등). target="public"으로 지정.
- 운영진용(admin): 내부 운영 자료 (예산, 회의록, 기획 메모 등). target="admin"으로 지정.
- 사용자가 "공개"/"외부"/"공지"라고 하면 public, "운영진"/"내부"/"회의"라고 하면 admin으로 판단.
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
        self._session_last_access: Dict[str, float] = {}
        self._vdb_reindex_lock = threading.Lock()
        self._vdb_reindexing = False

    def is_ready(self) -> Dict[str, Any]:
        vdb = self.vector_store.get_stats()
        expected_posts = sum(1 for p in self.posts if p.get("id") is not None)
        return {
            "openai": self.client is not None,
            "notion": self.notion.is_connected(),
            "data_loaded": len(self.posts) > 0,
            "posts_count": len(self.posts),
            "vectordb": vdb,
            "vectordb_index": self.vector_store.get_index_status(expected_posts=expected_posts),
            "vectordb_reindexing": self._vdb_reindexing,
        }

    def vectordb_status(self) -> Dict[str, Any]:
        expected_posts = sum(1 for p in self.posts if p.get("id") is not None)
        status = self.vector_store.get_index_status(expected_posts=expected_posts)
        status["reindexing"] = self._vdb_reindexing
        return status

    def _start_vectordb_reindex(self, reason: str = "", dept: str = "planning"):
        with self._vdb_reindex_lock:
            if self._vdb_reindexing:
                return
            self._vdb_reindexing = True

        t = threading.Thread(target=self._run_vectordb_reindex, args=(reason, dept), daemon=True)
        t.start()

    def _run_vectordb_reindex(self, reason: str, dept: str = "planning"):
        try:
            if not self.vector_store._openai:
                logger.warning("VectorDB reindex skipped (no OpenAI client) reason=%s", reason)
                return

            payload = [
                {
                    "id": str(p.get("id", "")),
                    "title": p.get("title", ""),
                    "content": p.get("content", ""),
                    "file_content": p.get("file_content", ""),
                    "files": p.get("files", []),
                    "author": p.get("author", ""),
                    "date": p.get("date", ""),
                    "url": p.get("url", ""),
                }
                for p in self.posts
                if p.get("id") is not None
            ]

            logger.warning("VectorDB reindex started (reason=%s, dept=%s, posts=%d)", reason, dept, len(payload))
            self.vector_store.add_posts_batch(payload, dept=dept)
            logger.warning("VectorDB reindex completed (dept=%s): %s", dept, self.vector_store.get_stats(dept))
        except Exception as e:
            logger.exception("VectorDB reindex failed (reason=%s): %s", reason, e)
        finally:
            with self._vdb_reindex_lock:
                self._vdb_reindexing = False

    def reset(self, session_id: str = "default"):
        self._sessions.pop(session_id, None)
        self._session_last_access.pop(session_id, None)
        self.memory.clear(session_id)

    def chat(self, user_message: str, session_id: str = "default") -> str:
        if not self.client:
            return self._fallback(user_message)

        # 노션 대상 프리픽스 파싱
        notion_target = "admin"
        notion_page_id = ""
        clean_message = user_message
        if user_message.startswith("[notion_target="):
            end = user_message.index("]")
            notion_target = user_message[len("[notion_target="):end].strip()
            clean_message = user_message[end + 1:].strip()
        if clean_message.startswith("[notion_page_id="):
            end = clean_message.index("]")
            notion_page_id = clean_message[len("[notion_page_id="):end].strip()
            clean_message = clean_message[end + 1:].strip()

        messages = self._get_session(session_id)
        messages.append({"role": "user", "content": clean_message})
        self._trim_messages(messages)
        self.memory.save(session_id, "user", clean_message)

        try:
            return self._react_loop(messages, session_id, notion_target=notion_target, notion_page_id=notion_page_id)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"

    def _sanitize_messages(self, messages: list):
        """메시지 리스트에서 깨진 tool_call 블록을 제거하여 OpenAI API 호환 상태로 복구"""
        i = 0
        while i < len(messages):
            msg = messages[i]
            if self._msg_role(msg) == "assistant" and self._msg_has_tool_calls(msg):
                # 이 assistant 메시지의 tool_call_id 목록
                if isinstance(msg, dict):
                    tc_ids = {tc["id"] for tc in msg.get("tool_calls", [])}
                else:
                    tc_ids = {tc.id for tc in (msg.tool_calls or [])}

                # 바로 뒤에 오는 tool 응답들의 tool_call_id 수집
                j = i + 1
                found_ids = set()
                while j < len(messages) and self._msg_role(messages[j]) == "tool":
                    tid = messages[j].get("tool_call_id", "") if isinstance(messages[j], dict) else ""
                    found_ids.add(tid)
                    j += 1

                if tc_ids != found_ids:
                    # 블록이 깨져 있으면 assistant + 뒤따르는 tool 응답 전부 제거
                    del messages[i:j]
                    continue
            elif self._msg_role(msg) == "tool":
                # 앞에 대응하는 assistant가 없는 고아 tool 응답
                messages.pop(i)
                continue
            i += 1

    def _react_loop(self, messages: list, session_id: str, notion_target: str = "admin", notion_page_id: str = "") -> str:
        """ReAct 루프: 도구 호출 -> 결과 확인 -> 반복 or 최종 응답"""
        system_prompt = SYSTEM_PROMPT
        if notion_target:
            label = "공개용(public)" if notion_target == "public" else "운영진용(admin)"
            system_prompt += f"\n\n현재 사용자가 선택한 노션 대상: {label}. 노션 관련 도구 호출 시 target=\"{notion_target}\"을 사용하세요."
        if notion_page_id:
            system_prompt += f"\n사용자가 특정 노션 페이지를 선택했습니다. 노션 페이지 생성 시 parent_page_id=\"{notion_page_id}\"를 사용하세요."

        for _ in range(MAX_TOOL_STEPS):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-5.2",
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )
            except Exception as api_err:
                err_str = str(api_err)
                if "tool_call" in err_str and "400" in err_str:
                    logger.warning("OpenAI 400 tool_call 오류 - 메시지 복구 시도: %s", err_str[:200])
                    self._sanitize_messages(messages)
                    try:
                        response = self.client.chat.completions.create(
                            model="gpt-5.2",
                            messages=[{"role": "system", "content": system_prompt}] + messages,
                            tools=TOOLS,
                            tool_choice="auto",
                        )
                    except Exception:
                        raise api_err
                else:
                    raise

            msg = response.choices[0].message

            if not msg.tool_calls:
                content = msg.content or ""
                messages.append({"role": "assistant", "content": content})
                self._trim_messages(messages)
                self.memory.save(session_id, "assistant", content)
                return content

            # 도구 호출 실행
            messages.append(msg)
            for tc in msg.tool_calls:
                raw_args = tc.function.arguments or ""
                try:
                    args = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError as e:
                    result = {
                        "error": "invalid_tool_arguments",
                        "tool": tc.function.name,
                        "exception": str(e),
                        "raw": raw_args[:2000],
                    }
                    messages.append({
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
                    self._trim_messages(messages)
                    continue

                try:
                    result = self.executor.run(tc.function.name, args)
                except Exception as e:
                    result = {
                        "error": "tool_execution_failed",
                        "tool": tc.function.name,
                        "exception": str(e),
                    }
                messages.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
                self._trim_messages(messages)

        # MAX_TOOL_STEPS 소진 시 강제 최종 응답
        response = self.client.chat.completions.create(
            model="gpt-5.2",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        )
        content = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": content})
        self._trim_messages(messages)
        self.memory.save(session_id, "assistant", content)
        return content

    def _get_session(self, session_id: str) -> list:
        """세션 메시지 가져오기 (없으면 영속 기억에서 복원)"""
        self._evict_sessions()
        if session_id not in self._sessions:
            history = self.memory.load(session_id, limit=10)
            self._sessions[session_id] = history
        self._session_last_access[session_id] = time.time()
        return self._sessions[session_id]

    @staticmethod
    def _session_ttl_seconds() -> int:
        return int(os.getenv("SESSION_TTL_SECONDS", "3600"))

    @staticmethod
    def _session_max_messages() -> int:
        return int(os.getenv("SESSION_MAX_MESSAGES", "80"))

    def _evict_sessions(self):
        ttl = self._session_ttl_seconds()
        if ttl <= 0:
            return

        now = time.time()
        stale = [sid for sid, ts in self._session_last_access.items() if (now - ts) > ttl]
        for sid in stale:
            self._sessions.pop(sid, None)
            self._session_last_access.pop(sid, None)

    @staticmethod
    def _msg_role(msg) -> str:
        if isinstance(msg, dict):
            return msg.get("role", "")
        return getattr(msg, "role", "")

    @staticmethod
    def _msg_has_tool_calls(msg) -> bool:
        if isinstance(msg, dict):
            return bool(msg.get("tool_calls"))
        return bool(getattr(msg, "tool_calls", None))

    def _trim_messages(self, messages: list):
        max_len = self._session_max_messages()
        if max_len <= 0:
            return
        if len(messages) <= max_len:
            return
        del messages[:-max_len]

        # 잘린 경계에서 tool_call 블록이 깨질 수 있으므로 복구
        # 1) 앞쪽에 남은 고아 tool 응답 제거
        while messages and self._msg_role(messages[0]) == "tool":
            messages.pop(0)

        # 2) 첫 메시지가 tool_calls가 있는 assistant라면 블록째 제거
        if messages and self._msg_role(messages[0]) == "assistant" and self._msg_has_tool_calls(messages[0]):
            messages.pop(0)
            while messages and self._msg_role(messages[0]) == "tool":
                messages.pop(0)

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
