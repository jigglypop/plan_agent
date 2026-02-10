"""
AI 에이전트 코어
LangGraph create_react_agent 기반 ReAct 에이전트
"""
import os
import logging
import sqlite3
import threading
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, AsyncGenerator, Optional
from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src import prepare_vdb_payload
from src.data_loader import load_posts, get_post_stats
from src.data_loader.parser import enrich_posts_with_files
from src.vectordb import VectorStore
from src.vectordb.store import load_posts_from_rag_jsonl
from src.vectordb.store import perf_reset as vdb_perf_reset, perf_snapshot as vdb_perf_snapshot
from src.notion import NotionClient
from src.agent.tools import (
    inject_deps, get_search_tools, get_notion_tools,
)


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """당신은 멘사코리아 기획위원회의 AI 에이전트 '염시코기 2세'입니다.

기획위원회는 멘사코리아의 계절 행사(신년회/봄/여름/가을/겨울)를 기획하고 운영하는 위원회입니다.
2005년부터 현재까지 약 20년간의 게시판 데이터(회의록, 예산안, 행사 기획, 결산, 장소 견적 등)에 접근할 수 있습니다.

역할:
1. 과거 행사 검색 및 정보 제공 (예산, 장소, 참석자 수, 견적 등)
2. 회의록 검색 및 요약
3. 예산/결산 관련 자료 검색 및 분석 + 첨부파일 AI 분석
4. 행사 기획 시 참고 자료 제공 (과거 유사 행사 기반)
5. 노션에 행사/체크리스트 생성, 노션 DB 조회
6. 위원회 운영 관련 정보 제공

노션 경로:
- 공개용(public): 외부에 공개되는 정보 (행사 안내, 공지 등). target="public"으로 지정.
- 운영진용(admin): 내부 운영 자료 (예산, 회의록, 기획 메모 등). target="admin"으로 지정.
- 사용자가 "공개"/"외부"/"공지"라고 하면 public, "운영진"/"내부"/"회의"라고 하면 admin으로 판단.

도구 사용 규칙:
- 복잡한 질문은 여러 도구를 순차적으로 호출하여 답변 (예: 검색 -> 상세 조회 -> 파일 분석)
- search_posts로 관련 게시글을 찾고, 필요하면 get_post로 전문 확인, analyze_file로 첨부파일 AI 분석
- 수치가 있으면 구체적으로 제시하고 출처(게시글 제목, 날짜)를 함께 안내
- 모르는 내용은 모른다고 솔직하게 답변

출처 표기 규칙:
- 게시글을 인용할 때 반드시 마크다운 링크로 출처를 포함: [게시글 제목](URL)
- 노션 페이지를 생성하면 반드시 [페이지 제목](notion URL)을 응답에 포함
- URL이 없는 경우에만 텍스트로 제목과 날짜를 표기

전문가 에이전트:
- search_expert: 게시판 데이터 검색/분석 + 웹 검색/페이지 읽기가 필요할 때 호출 (과거 행사, 예산, 회의록, 장소 견적, 첨부파일 분석, 외부 정보 검색 등)
- notion_expert: 노션 콘텐츠 생성/관리/조회가 필요할 때 호출 (행사 등록, 페이지 작성, 칸반보드, DB 쿼리, 체크리스트 생성)

위임 규칙:
- 간단한 인사/일반 질문은 직접 답변
- 데이터 검색 또는 첨부파일 분석이 필요하면 search_expert에게 위임
- 노션 작업(생성/조회/수정/삭제/DB 쿼리/칸반보드/체크리스트/댓글)이 필요하면 notion_expert에게 위임
- 복합 요청(예: "과거 예산 찾아서 노션에 정리")은 순차 위임: search_expert -> notion_expert

응답 규칙:
- 한국어로 간결하고 정확하게 답변
- 이모지 사용 금지
"""


SEARCH_PROMPT = """당신은 데이터 검색/분석 전문가입니다.
멘사코리아 기획위원회 게시판 데이터(2005~현재, 회의록/예산안/행사기획/결산/장소견적)를 검색하고 분석합니다.

도구 활용 순서:
1. search_posts로 관련 게시글 시맨틱 검색
2. 필요하면 get_post로 상세 내용 확인
3. analyze_file로 첨부파일(Excel/PDF/PPT) AI 분석 (예산안, 견적서 해석)
4. get_stats로 전체 통계, list_attached_files로 첨부파일 검색
5. web_search로 외부 정보 검색 (장소, 가격, 최신 뉴스 등)
6. fetch_webpage로 특정 URL의 내용 읽기 (검색 결과의 상세 페이지 등)

응답 규칙:
- 수치와 출처를 반드시 포함. 출처는 마크다운 링크로: [제목](url)
- URL 필드가 있는 게시글은 반드시 링크로 표시
- 한국어로 간결하게
- 이모지 금지
"""


_NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID", "")
_NOTION_PUBLIC_ID = os.getenv("NOTION_PUBLIC_PAGE_ID", "")
_NOTION_ADMIN_ID = os.getenv("NOTION_ADMIN_PAGE_ID", "")

NOTION_PROMPT = f"""당신은 노션 관리 전문가입니다.
멘사코리아 기획위원회 노션에 행사, 페이지, 칸반보드, 체크리스트를 생성하고 기존 콘텐츠를 조회/수정/삭제합니다.

기본 ID:
- 행사 데이터베이스 ID: {_NOTION_DB_ID}
- 공개 페이지 ID: {_NOTION_PUBLIC_ID}
- 운영진 페이지 ID: {_NOTION_ADMIN_ID}
DB 조회시 위 database_id를 바로 사용하세요. list_notion_databases를 먼저 호출할 필요 없습니다.

도구:
- create_notion_event: 행사 DB에 새 행사 등록
- create_notion_page: 자유 형식 페이지 작성 (회의록, 공지, 기획서 등)
- create_notion_board: 칸반보드(데이터베이스) 생성. 상태/담당자/기한/우선순위 컬럼 포함.
- create_notion_checklist: 체크리스트(할일 목록) 페이지 생성
- update_notion_item: DB 항목 속성 변경 (상태 이동, 담당자 변경 등)
- update_notion_page_content: 기존 페이지에 텍스트 블록 추가
- read_notion_page: 페이지 제목과 본문 읽기
- archive_notion_page: 페이지 아카이브(삭제)
- add_notion_comment: 페이지에 댓글 추가
- query_notion: 기존 노션 콘텐츠 조회
- list_notion_databases: 접근 가능한 노션 DB 목록 조회
- query_notion_database: 노션 DB에서 항목 필터링 조회 (상태, 카테고리 등)

응답에 생성/수정된 페이지 URL을 반드시 마크다운 링크로 포함: [제목](url)
한국어로 간결하게.
"""

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
MAX_TOKENS = int(os.getenv("SESSION_MAX_TOKENS", "8000"))
MEMORY_DB = Path(__file__).parent.parent.parent / "data" / "checkpoints.db"


def _parse_notion_prefix(user_message: str) -> tuple:
    """노션 대상 프리픽스 파싱 -> (notion_target, notion_page_id, clean_message)"""
    notion_target = "admin"
    notion_page_id = ""
    clean = user_message

    if clean.startswith("[notion_target="):
        end = clean.find("]")
        if end != -1:
            notion_target = clean[len("[notion_target="):end].strip()
            clean = clean[end + 1:].strip()

    if clean.startswith("[notion_page_id="):
        end = clean.find("]")
        if end != -1:
            notion_page_id = clean[len("[notion_page_id="):end].strip()
            clean = clean[end + 1:].strip()

    return notion_target, notion_page_id, clean


SUB_AGENT_MAX_TOKENS = int(os.getenv("SUB_AGENT_MAX_TOKENS", "60000"))


def _pre_model_hook(state):
    """LLM 호출 전 메시지 트리밍 (슈퍼바이저)"""
    trimmed = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=MAX_TOKENS,
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed}


def _sub_agent_hook(state):
    """서브 에이전트용 트리밍 (도구 결과 누적 방지)"""
    trimmed = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=SUB_AGENT_MAX_TOKENS,
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed}


def _create_agent_tool(graph, name: str, description: str) -> StructuredTool:
    """에이전트 서브그래프를 슈퍼바이저용 도구로 래핑"""
    def _invoke(request: str) -> str:
        result = graph.invoke({"messages": [("user", request)]})
        msgs = result.get("messages")
        return msgs[-1].content if msgs else ""

    return StructuredTool.from_function(
        func=_invoke, name=name, description=description,
    )


class Agent:
    """AI 에이전트 - LangGraph ReAct"""

    def __init__(self):
        self.posts = load_posts()
        # 운영 데이터 확장: notion_rag.jsonl(노션 + mensa boards)을 함께 로드해
        # search_posts 결과의 preview/get_post 조회까지 자연스럽게 동작시키기 위함.
        self.rag_posts = load_posts_from_rag_jsonl("data/notion_rag.jsonl")
        self._all_posts = self.posts + self.rag_posts
        # 첨부파일 텍스트 파싱은 비용이 크고(특히 PDF/PPT),
        # 런타임 검색/채팅은 VectorDB를 사용하므로 시작 시점에 전량 파싱하지 않음.
        # (벡터 인덱싱/재인덱싱 경로에서 enrich_posts_with_files를 수행)
        self.vector_store = VectorStore()
        self.notion = NotionClient()

        # 도구에 의존성 주입
        inject_deps(self._all_posts, self.vector_store, self.notion)

        # 멀티 에이전트 그래프 생성
        self._model_available = bool(os.getenv("OPENAI_API_KEY"))
        self.graph = None
        self._checkpointer = None
        self.graph_stream = None
        self._checkpointer_async = None

        if self._model_available:
            model = ChatOpenAI(
                model=DEFAULT_MODEL,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            # 전문가 에이전트 (stateless - 체크포인터 없음, 트리밍 적용)
            search_graph = create_react_agent(
                model, tools=get_search_tools(), prompt=SEARCH_PROMPT,
                pre_model_hook=_sub_agent_hook,
            )
            notion_graph = create_react_agent(
                model, tools=get_notion_tools(), prompt=NOTION_PROMPT,
                pre_model_hook=_sub_agent_hook,
            )

            # 전문가를 슈퍼바이저용 도구로 래핑
            agent_tools = [
                _create_agent_tool(
                    search_graph, "search_expert",
                    "게시판 데이터 검색/분석 전문가. 과거 행사, 예산, 회의록, 장소 견적 등을 검색하고 분석합니다.",
                ),
                _create_agent_tool(
                    notion_graph, "notion_expert",
                    "노션 관리 전문가. 노션에 행사/페이지/체크리스트를 생성하고 기존 내용을 조회합니다.",
                ),
            ]

            # 슈퍼바이저 (체크포인터로 대화 영속)
            MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(MEMORY_DB), check_same_thread=False)
            self._checkpointer = SqliteSaver(self._conn)
            self.graph = create_react_agent(
                model,
                tools=agent_tools,
                pre_model_hook=_pre_model_hook,
                checkpointer=self._checkpointer,
                prompt=SYSTEM_PROMPT,
            )

            # 스트리밍은 async checkpointer가 필요함 (SqliteSaver는 async 미지원)
            try:
                self._checkpointer_async = AsyncSqliteSaver.from_conn_string(str(MEMORY_DB))
                self.graph_stream = create_react_agent(
                    model,
                    tools=agent_tools,
                    pre_model_hook=_pre_model_hook,
                    checkpointer=self._checkpointer_async,
                    prompt=SYSTEM_PROMPT,
                )
            except Exception as e:
                logger.warning("Async checkpointer init failed, streaming will degrade: %s", e)
                self.graph_stream = create_react_agent(
                    model,
                    tools=agent_tools,
                    pre_model_hook=_pre_model_hook,
                    prompt=SYSTEM_PROMPT,
                )

        # VectorDB reindex
        self._vdb_reindex_lock = threading.Lock()
        self._vdb_reindexing = False

    def is_ready(self) -> Dict[str, Any]:
        vdb = self.vector_store.get_stats()
        expected_posts = sum(1 for p in self.posts if p.get("id") is not None)
        return {
            "openai": self._model_available,
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

            payload = prepare_vdb_payload(self._all_posts)

            logger.warning("VectorDB reindex started (reason=%s, dept=%s, posts=%d)", reason, dept, len(payload))
            self.vector_store.add_posts_batch(payload, dept=dept)
            logger.warning("VectorDB reindex completed (dept=%s): %s", dept, self.vector_store.get_stats(dept))
        except Exception as e:
            logger.exception("VectorDB reindex failed (reason=%s): %s", reason, e)
        finally:
            with self._vdb_reindex_lock:
                self._vdb_reindexing = False

    def reset(self, session_id: str = "default"):
        """세션 초기화 - 체크포인터에서 해당 thread 삭제"""
        if self._checkpointer:
            config = {"configurable": {"thread_id": session_id}}
            # 빈 메시지로 새 체크포인트를 기록하여 이전 대화를 덮어씀
            try:
                if self.graph:
                    self.graph.update_state(config, {"messages": []})
            except Exception as e:
                logger.warning("세션 초기화 실패 (session=%s): %s", session_id, e)

    def _build_messages(self, user_message: str) -> list:
        """노션 프리픽스 파싱 후 메시지 리스트 생성"""
        notion_target, notion_page_id, clean = _parse_notion_prefix(user_message)

        system_suffix = ""
        if notion_target:
            label = "공개용(public)" if notion_target == "public" else "운영진용(admin)"
            system_suffix += f"\n\n현재 사용자가 선택한 노션 대상: {label}. 노션 관련 도구 호출 시 target=\"{notion_target}\"을 사용하세요."
        if notion_page_id:
            system_suffix += f"\n사용자가 특정 노션 페이지를 선택했습니다. 노션 페이지 생성 시 parent_page_id=\"{notion_page_id}\"를 사용하세요."

        messages = [("user", clean)]
        if system_suffix:
            messages.insert(0, ("system", system_suffix.strip()))
        return messages

    def chat(self, user_message: str, session_id: str = "default") -> str:
        if not self.graph:
            return self._fallback(user_message)

        config = {"configurable": {"thread_id": session_id}}

        try:
            result = self.graph.invoke(
                {"messages": self._build_messages(user_message)},
                config=config,
            )
            msgs = result.get("messages")
            if not msgs:
                return "응답을 생성하지 못했습니다."
            return msgs[-1].content or ""
        except Exception as e:
            err_str = str(e)
            # 운영 안정성: 체크포인터에 툴콜이 남고 ToolMessage가 유실되면 INVALID_CHAT_HISTORY가 발생함
            if "INVALID_CHAT_HISTORY" in err_str or ("ToolMessage" in err_str and "tool_calls" in err_str):
                logger.warning("Invalid chat history. Reset and retry once. (session=%s)", session_id)
                self.reset(session_id)
                try:
                    result = self.graph.invoke(
                        {"messages": self._build_messages(user_message)},
                        config=config,
                    )
                    msgs = result.get("messages")
                    if msgs:
                        return msgs[-1].content or ""
                except Exception as retry_err:
                    logger.exception("Retry after reset failed: %s", retry_err)
                    return f"오류가 발생했습니다: {retry_err}"
            # 토큰 초과 시 세션 리셋 후 재시도
            if "context_length_exceeded" in err_str or "token" in err_str.lower():
                logger.warning("토큰 초과 - 세션 리셋 후 재시도 (session=%s)", session_id)
                self.reset(session_id)
                try:
                    result = self.graph.invoke(
                        {"messages": self._build_messages(user_message)},
                        config=config,
                    )
                    msgs = result.get("messages")
                    if msgs:
                        return "(이전 대화가 초기화되었습니다)\n\n" + (msgs[-1].content or "")
                except Exception as retry_err:
                    logger.exception("재시도도 실패: %s", retry_err)
                    return f"토큰 초과로 세션을 초기화했으나 재시도도 실패했습니다: {retry_err}"
            logger.exception("Agent chat failed: %s", e)
            return f"오류가 발생했습니다: {e}"

    @staticmethod
    def _status_for_event(event: dict) -> Optional[str]:
        """LangGraph astream_events -> 사용자용 상태 메시지."""
        ev = (event or {}).get("event", "")
        name = (event or {}).get("name", "") or ""

        if ev == "on_tool_start":
            if name == "search_expert":
                return "게시판/문서 검색 중"
            if name == "notion_expert":
                return "노션 작업 중"
            if name == "search_posts":
                return "벡터 검색 중"
            if name == "get_post":
                return "문서 내용 가져오는 중"
            if name == "list_attached_files":
                return "첨부파일 목록 조회 중"
            if name == "analyze_file":
                return "첨부파일 분석 중"
            if name == "fetch_webpage":
                return "웹페이지 읽는 중"
            if name == "web_search":
                return "웹 검색 중"
            return f"도구 실행 중: {name}"

        if ev == "on_chat_model_start":
            return "답변 생성 중"

        return None

    async def stream(self, user_message: str, session_id: str = "default") -> AsyncGenerator[Dict[str, Any], None]:
        """SSE 스트리밍용 비동기 제너레이터. token/status/perf 이벤트 yield."""
        if not self.graph:
            yield {"type": "token", "content": self._fallback(user_message)}
            return

        config = {"configurable": {"thread_id": session_id}}

        try:
            vdb_perf_reset()
            t0 = time.perf_counter()
            yield {"type": "status", "message": "요청 처리 시작"}

            tool_started_at: Dict[str, float] = {}
            tool_ms: Dict[str, float] = {}
            llm_started_at: Optional[float] = None
            llm_ms_total: float = 0.0

            if not self.graph_stream:
                # 최후 fallback: 스트리밍 불가 시 일반 응답을 한 번에 내려줌
                yield {"type": "status", "message": "답변 생성 중"}
                yield {"type": "token", "content": self.chat(user_message, session_id)}
                yield {"type": "perf", "perf": {"total_ms": round((time.perf_counter() - t0) * 1000, 1)}}
                return

            async for event in self.graph_stream.astream_events(
                {"messages": self._build_messages(user_message)},
                config=config,
                version="v2",
            ):
                ev = event.get("event", "")
                name = event.get("name", "") or ""

                # Status events (throttling is done implicitly by only reacting to key starts)
                msg = self._status_for_event(event)
                if msg:
                    yield {"type": "status", "message": msg}

                # Tool timing
                if ev == "on_tool_start" and name:
                    tool_started_at[name] = time.perf_counter()
                elif ev == "on_tool_end" and name:
                    started = tool_started_at.pop(name, None)
                    if started is not None:
                        ms = (time.perf_counter() - started) * 1000
                        tool_ms[name] = float(tool_ms.get(name, 0.0)) + ms

                # LLM timing
                if ev == "on_chat_model_start":
                    llm_started_at = time.perf_counter()
                elif ev == "on_chat_model_end":
                    if llm_started_at is not None:
                        llm_ms_total += (time.perf_counter() - llm_started_at) * 1000
                        llm_started_at = None

                if ev == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield {"type": "token", "content": chunk.content}

            perf = {
                "total_ms": round((time.perf_counter() - t0) * 1000, 1),
                "llm_ms": round(llm_ms_total, 1),
                "tools_ms": {k: round(v, 1) for k, v in sorted(tool_ms.items(), key=lambda x: -x[1])},
                "vectordb": {k: round(v, 1) if isinstance(v, (int, float)) else v for k, v in vdb_perf_snapshot().items()},
            }
            yield {"type": "perf", "perf": perf}
        except asyncio.CancelledError:
            # Client aborted the stream; do not treat as error.
            logger.info("Stream cancelled (session=%s)", session_id)
            return
        except Exception as e:
            err_str = str(e)
            if "INVALID_CHAT_HISTORY" in err_str or ("ToolMessage" in err_str and "tool_calls" in err_str):
                logger.warning("Invalid chat history in stream. Reset session. (session=%s)", session_id)
                self.reset(session_id)
            logger.exception("Agent stream failed: %s", e)
            yield {"type": "error", "message": f"오류가 발생했습니다: {e}"}

    # ========== 세션 관리 ==========

    def list_sessions(self) -> list[dict]:
        """체크포인터 DB에서 세션 목록 조회"""
        if not self._checkpointer:
            return []
        try:
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"
            )
            sessions = [{"session_id": row[0]} for row in cursor.fetchall()]
            conn.close()
            return sessions
        except Exception as e:
            logger.warning("세션 목록 조회 실패: %s", e)
            return []

    def delete_session(self, session_id: str) -> bool:
        """특정 세션의 체크포인트 삭제"""
        if not self._checkpointer:
            return False
        try:
            conn = sqlite3.connect(str(MEMORY_DB))
            conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (session_id,))
            conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (session_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning("세션 삭제 실패 (session=%s): %s", session_id, e)
            return False

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
