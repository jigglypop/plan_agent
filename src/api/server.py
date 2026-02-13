"""
FastAPI 백엔드 서버
API 엔드포인트: /api/* 하위
프론트엔드: / (정적 파일 서빙)
"""
import os
import json
import logging
from pathlib import Path

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from src import format_post_item, format_search_item
from src.agent import Agent
from src.data_loader import get_post_by_id, filter_posts, get_post_stats, list_files

app = FastAPI(
    title="Plan Agent API",
    description="AI 기반 기획위원회 에이전트",
    version="2.0.0",
)

_allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 에이전트 (싱글턴)
import threading
_agent = None
_agent_lock = threading.Lock()


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = Agent()
    return _agent


# ========== 모델 ==========

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_DOC_EXT = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".txt", ".csv"}
ALLOWED_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    file_context: Optional[str] = None


class ResetChatRequest(BaseModel):
    session_id: Optional[str] = "default"

class StopChatRequest(BaseModel):
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    status: str = "ok"


class SajuReportRequest(BaseModel):
    saju_text: str
    year: int = 2026


SAJU_SYSTEM_PROMPT = """당신은 30년 경력의 맹파명리(盲派命理)/자미두수 전문가입니다.
사용자가 제공하는 만세력 사주(절기 기반) + 자미두수 명반 데이터를 종합 분석하여 신년운세 보고서를 작성합니다.

핵심 분석 방법론 - 맹파명리(盲派命理) 위주:
- 맹파는 신강/신약 판단에 의존하지 않는다. 신강/신약 분류는 참고만 하고, 절대 핵심 분석 기준으로 삼지 않는다.
- 맹파의 핵심은 "주종관계(主從關係)"와 "빈주법(賓主法)"이다. 일간이 하고 싶은 일(체, 體)과 실제 환경(용, 用)의 관계를 본다.
- 천간은 뜻(의지), 지지는 실제 환경(현실). 천간의 뜻이 지지에서 뿌리를 얻는지, 지지의 환경이 천간의 뜻을 도와주는지를 중심으로 해석한다.
- 격국(格局)보다 "상(象, 형상/이미지)"을 중시한다. 간지 조합이 그리는 구체적 장면과 이야기를 읽어낸다.
- 합형충파해(合刑沖破害)를 단순 길흉이 아닌, 간지 간의 역학 관계와 변화의 맥락으로 해석한다.
- 신살(역마, 도화, 화개, 천을귀인, 양인 등)은 맹파에서도 보조 참고로 활용한다.
- 십성(十星)의 배치와 힘의 강약을 통해 성격/적성/재물/관계 해석
- 지장간 분석으로 숨겨진 기운과 잠재력 파악
- 12운성으로 각 기둥의 에너지 상태 판단
- 대운과 세운(해당 연도)의 흐름을 종합하여 운세 판단. 대운/세운의 간지가 원국에 어떤 "상(象)"을 만드는지 읽는다.
- 공망(空亡)의 영향 반영
- 자미두수 명반의 각 궁 주성 배치와 사화(화록/화권/화과/화기), 비성사화 비입을 참고하여 성격/운세를 보충 분석

보고서 구성 (반드시 이 순서와 구조를 따를 것):

## 사주 원국 분석
일간의 오행/음양 특성, 천간의 뜻과 지지의 환경 관계, 간지가 그리는 "상(象)" 해석
합형충파해가 만드는 역학 관계, 신살 해석 포함
(신강/신약은 참고 수준으로만 언급, 맹파적 주종관계 중심으로 분석)

## 오행 분석
목/화/토/금/수 각 오행의 분포와 과다/부족, 상생상극 관계

## 성격과 적성
사주 십성 + 자미두수 명궁 주성을 종합하여 성격 특성, 강점과 약점, 적합한 분야

## {year}년 신년운세

### 총운
해당 연도의 세운(천간/지지)이 원국에 만드는 "상(象)", 대운과의 관계

### 재물운
편재/정재의 상태, 재물 흐름, 투자/지출 관련 조언

### 직업운
관성(편관/정관)과 식상(식신/상관)의 흐름, 승진/이직/사업 운

### 대인관계/연애운
비겁과 인성의 관계, 이성운, 결혼운(미혼인 경우), 인간관계 변화

### 건강운
오행 불균형에서 오는 건강 취약점, 주의해야 할 부위, 예방법

## 자미두수 명반 해석
명궁/재백궁/관록궁/부처궁 등 주요 궁의 주성 해석, 비성사화 비입 분석, 현재 대한/유년 흐름

## 월별 운세 포인트
1월~12월 중 특히 주목할 시기와 이유 (간략히)

## 종합 조언
올해를 잘 보내기 위한 핵심 조언 3~5가지

작성 규칙:
- 한국어로 작성
- 마크다운 형식 엄수: 제목은 반드시 ##/###/#### 사용, 목록은 - 사용
- 이모지 사용 금지
- 근거 없는 공포 조성 금지, 균형 잡힌 해석
- 전문 용어 사용 시 괄호 안에 쉬운 설명 병기
- 분량: 충분히 상세하게 (2000자 이상)
"""


# ========== API 라우터 ==========

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    try:
        agent = get_agent()
        connections = agent.is_ready()
    except Exception as e:
        return {"status": "error", "error": str(e)}

    status = "healthy"
    vdb = connections.get("vectordb")
    if isinstance(vdb, dict) and vdb.get("total", 0) == 0:
        status = "degraded"
    return {"status": status, "connections": connections}

@router.get("/vectordb/status")
def vectordb_status():
    """벡터DB 색인 상태/진행률"""
    agent = get_agent()
    return agent.vectordb_status()


@router.post("/vectordb/reindex")
def vectordb_reindex():
    """벡터DB 색인 재시작 (비동기 백그라운드)"""
    agent = get_agent()
    status = agent.vectordb_status()
    if status.get("reindexing"):
        return {"status": "already_running", "message": "이미 색인 중입니다."}
    agent._start_vectordb_reindex(reason="api_trigger")
    return {"status": "started", "message": "색인이 시작되었습니다."}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """파일 업로드 + 텍스트 추출"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXT | ALLOWED_IMG_EXT:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 형식: {ext}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="파일 크기 제한 10MB 초과")

    stem = Path(file.filename).stem
    save_path = UPLOAD_DIR / file.filename
    counter = 1
    while save_path.exists():
        save_path = UPLOAD_DIR / f"{stem}_{counter}{ext}"
        counter += 1
    save_path.write_bytes(content)

    extracted = ""
    is_image = ext in ALLOWED_IMG_EXT
    if not is_image:
        try:
            from src.data_loader.parser import parse_file
            extracted = parse_file(str(save_path)) or ""
        except Exception as e:
            logger.warning("업로드 파일 파싱 실패 %s: %s", file.filename, e)

    return {
        "filename": file.filename,
        "size": len(content),
        "type": "image" if is_image else "document",
        "extracted_text": extracted[:5000],
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """AI 에이전트와 대화"""
    agent = get_agent()
    message = request.message
    if request.file_context:
        ctx = request.file_context[:6000]
        message = f"[업로드된 파일 내용]\n{ctx}\n\n[질문]\n{message}"
    response = agent.chat(message, request.session_id)
    return ChatResponse(response=response)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    """SSE 스트리밍 AI 응답"""
    agent = get_agent()
    message = request.message
    if request.file_context:
        ctx = request.file_context[:6000]
        message = f"[업로드된 파일 내용]\n{ctx}\n\n[질문]\n{message}"

    async def generate():
        async for item in agent.stream(message, request.session_id):
            # client disconnected -> stop early
            try:
                if await http_request.is_disconnected():
                    break
            except Exception:
                pass
            # Backward compatible: if stream yields plain text, treat it as token.
            if isinstance(item, str):
                yield f"event: token\ndata: {json.dumps({'content': item}, ensure_ascii=False)}\n\n"
                continue

            t = (item or {}).get("type", "")
            if t == "token":
                yield f"event: token\ndata: {json.dumps({'content': item.get('content', '')}, ensure_ascii=False)}\n\n"
            elif t == "status":
                yield f"event: status\ndata: {json.dumps({'message': item.get('message', '')}, ensure_ascii=False)}\n\n"
            elif t == "perf":
                yield f"event: perf\ndata: {json.dumps(item.get('perf', {}), ensure_ascii=False)}\n\n"
            elif t == "error":
                yield f"event: error\ndata: {json.dumps({'message': item.get('message', '')}, ensure_ascii=False)}\n\n"
            else:
                # Unknown event -> emit as token to avoid breaking clients
                yield f"event: token\ndata: {json.dumps({'content': str(item)}, ensure_ascii=False)}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/reset")
def reset_chat(request: ResetChatRequest):
    """대화 초기화"""
    agent = get_agent()
    agent.reset(request.session_id or "default")
    return {"status": "ok", "message": "대화가 초기화되었습니다."}


@router.post("/chat/stop")
def stop_chat(request: StopChatRequest):
    """스트리밍 응답 중단 요청 (네트워크 abort 없이 server-side 종료)"""
    agent = get_agent()
    agent.request_stop(request.session_id or "default")
    return {"status": "ok", "message": "중단 요청됨"}


# ========== 세션 관리 ==========

@router.get("/sessions")
def list_sessions():
    """세션 목록 조회"""
    agent = get_agent()
    return agent.list_sessions()


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """세션 삭제"""
    agent = get_agent()
    if agent.delete_session(session_id):
        return {"status": "ok", "message": f"세션 '{session_id}'이(가) 삭제되었습니다."}
    raise HTTPException(status_code=404, detail="세션을 찾을 수 없거나 삭제에 실패했습니다.")


# ========== 게시글 ==========

@router.get("/posts")
def api_list_posts(year: int = None, author: str = None, keyword: str = None, limit: int = 0):
    """게시글 목록"""
    agent = get_agent()
    filtered = filter_posts(agent.posts, year=year, author=author, keyword=keyword, limit=limit)
    return [format_post_item(p, include_views=True) for p in filtered]


@router.get("/posts/{post_id}")
def api_get_post(post_id: str):
    """게시글 상세"""
    agent = get_agent()
    post = get_post_by_id(agent.posts, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="not found")
    return post


@router.get("/posts/search/{query}")
def api_search_posts(query: str, limit: int = 5):
    """게시글 시맨틱 검색"""
    agent = get_agent()
    results = agent.vector_store.search_posts(query, limit)
    return [
        format_search_item(r, post, include_relevance=True, preview_len=300)
        for r in results
        if (post := get_post_by_id(agent.posts, r["id"]))
    ]


# ========== 통계 ==========

@router.get("/stats")
def api_stats():
    """게시글 통계"""
    agent = get_agent()
    return get_post_stats(agent.posts)


# ========== 파일 ==========

@router.get("/files")
def api_files(keyword: str = None, year: int = None):
    """첨부파일 목록"""
    agent = get_agent()
    return list_files(agent.posts, keyword=keyword, year=year)


# ========== 대시보드 ==========

@router.get("/dashboard")
def api_dashboard():
    """대시보드 데이터"""
    agent = get_agent()
    stats = get_post_stats(agent.posts)
    db_stats = agent.vector_store.get_stats()
    recent = agent.posts[:10]

    return {
        "post_stats": stats,
        "vectordb_stats": db_stats,
        "recent_posts": [format_post_item(p) for p in recent],
    }


# ========== 노션 ==========

@router.get("/notion/status")
def notion_status():
    """노션 연결 상태"""
    agent = get_agent()
    return {
        "connected": agent.notion.is_connected(),
        "token_set": bool(os.getenv("NOTION_TOKEN")),
        "database_id_set": bool(os.getenv("NOTION_DATABASE_ID")),
    }


# 노션 트리 캐시 (재귀 API 호출 비용 절감)
import time as _time
import asyncio as _asyncio
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor

_notion_tree_cache: dict = {}
_notion_tree_ts: float = 0
_NOTION_TREE_TTL = 300  # 5분 캐시
_notion_executor = _ThreadPoolExecutor(max_workers=4)

def _normalize_notion_id(raw_id: str) -> str:
    """Notion id를 API가 안정적으로 받는 UUID 형태로 정규화."""
    s = (raw_id or "").strip()
    if not s:
        return ""
    s2 = s.replace("-", "")
    if len(s2) != 32:
        return s
    try:
        int(s2, 16)
    except Exception:
        return s
    return f"{s2[:8]}-{s2[8:12]}-{s2[12:16]}-{s2[16:20]}-{s2[20:]}"


def _fetch_children_shallow(client, page_id: str) -> list:
    """노션 페이지의 직계 자식만 조회 (1 API call, 재귀 없음)"""
    try:
        resp = client.blocks.children.list(block_id=_normalize_notion_id(page_id), page_size=100)
    except Exception:
        return []

    nodes = []
    for block in resp.get("results", []):
        if block.get("type") == "child_page":
            title = block["child_page"].get("title", "Untitled")
            nodes.append({"id": block["id"], "title": title, "children": [], "has_children": True})
        elif block.get("type") == "child_database":
            title = block["child_database"].get("title", "Untitled DB")
            nodes.append({"id": block["id"], "title": f"[DB] {title}", "children": [], "has_children": False})
    return nodes


def _get_root_title(client, page_id: str, fallback: str) -> str:
    """루트 페이지/DB 제목 조회"""
    try:
        page = client.pages.retrieve(page_id=_normalize_notion_id(page_id))
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                if title:
                    return title
    except Exception:
        pass
    # Full-page database URL (..../<db_id>?v=<view_id>)도 여기로 들어올 수 있음
    try:
        db = client.databases.retrieve(database_id=_normalize_notion_id(page_id))
        title = "".join(t.get("plain_text", "") for t in (db.get("title") or []))
        if title:
            return f"[DB] {title}"
    except Exception:
        pass
    return fallback


def _fetch_root_node(client, page_id: str, label: str) -> dict:
    """루트 페이지 1개의 제목 + 직계 자식 조회 (2 API calls)"""
    if not page_id:
        return {"id": "", "title": label, "children": [], "has_children": False}
    pid = _normalize_notion_id(page_id)
    children = _fetch_children_shallow(client, pid)
    title = _get_root_title(client, pid, label)
    return {"id": pid, "title": title, "children": children, "has_children": len(children) > 0}


@router.get("/notion/tree")
async def notion_tree(force: bool = False):
    """노션 공개용/운영진용 페이지 트리 구조 (5분 캐시, 비동기 병렬 조회)"""
    global _notion_tree_cache, _notion_tree_ts

    if not force and _notion_tree_cache and (_time.time() - _notion_tree_ts) < _NOTION_TREE_TTL:
        return _notion_tree_cache

    agent = get_agent()
    if not agent.notion.is_connected():
        raise HTTPException(status_code=503, detail="노션 미연결")

    client = agent.notion.client
    public_id = os.getenv("NOTION_PUBLIC_PAGE_ID", "")
    admin_id = os.getenv("NOTION_ADMIN_PAGE_ID", "")

    loop = _asyncio.get_event_loop()
    public_future = loop.run_in_executor(
        _notion_executor, _fetch_root_node, client, public_id, "public"
    )
    admin_future = loop.run_in_executor(
        _notion_executor, _fetch_root_node, client, admin_id, "admin"
    )

    public_node, admin_node = await _asyncio.gather(public_future, admin_future)

    # Optional: pin additional pages into the root tree (without moving them in Notion)
    pinned_ids = [
        p.strip()
        for p in os.getenv("NOTION_PINNED_PAGE_IDS", "").split(",")
        if p.strip()
    ]
    if pinned_ids:
        # Deduplicate: avoid adding pages already present in admin/public root children.
        existing_ids = set()
        for n in (public_node, admin_node):
            for ch in n.get("children", []) or []:
                if ch.get("id"):
                    existing_ids.add(ch["id"])

        pinned_futures = []
        for pid in pinned_ids:
            if pid in existing_ids:
                continue
            short = _normalize_notion_id(pid).replace("-", "")[:16]
            pinned_futures.append(loop.run_in_executor(
                _notion_executor, _fetch_root_node, client, pid, f"pinned-{short}"
            ))

        if pinned_futures:
            pinned_nodes = [n for n in await _asyncio.gather(*pinned_futures) if n and n.get("id")]
            # Default: attach to admin root (more conservative for internal docs)
            admin_node["children"] = (admin_node.get("children") or []) + pinned_nodes

    result = {"public": public_node, "admin": admin_node}

    _notion_tree_cache = result
    _notion_tree_ts = _time.time()
    return result


@router.get("/notion/children/{page_id}")
async def notion_children(page_id: str):
    """노션 페이지의 직계 자식만 조회 (lazy loading용, 1 API call)"""
    agent = get_agent()
    if not agent.notion.is_connected():
        raise HTTPException(status_code=503, detail="노션 미연결")
    loop = _asyncio.get_event_loop()
    return await loop.run_in_executor(
        _notion_executor, _fetch_children_shallow, agent.notion.client, page_id
    )


@router.get("/notion/backlinks/{page_id}")
async def notion_backlinks(page_id: str, scope: str = "all", depth: int = 2, limit: int = 50):
    """특정 노션 페이지/DB를 참조하는(멘션/링크) 페이지 목록(역참조)을 반환.

    Notion API에 백링크 API가 없어서, admin/public 루트(+ pinned) 범위에서만 스캔한다.
    """
    agent = get_agent()
    if not agent.notion.is_connected():
        raise HTTPException(status_code=503, detail="노션 미연결")

    scope = (scope or "all").strip().lower()
    roots: list[str] = []
    if scope in ("all", "admin"):
        rid = os.getenv("NOTION_ADMIN_PAGE_ID", "")
        if rid:
            roots.append(rid)
    if scope in ("all", "public"):
        rid = os.getenv("NOTION_PUBLIC_PAGE_ID", "")
        if rid:
            roots.append(rid)
    pinned_ids = [
        p.strip()
        for p in os.getenv("NOTION_PINNED_PAGE_IDS", "").split(",")
        if p.strip()
    ]
    roots.extend(pinned_ids)

    loop = _asyncio.get_event_loop()
    backlinks = await loop.run_in_executor(
        _notion_executor, agent.notion.find_backlinks, page_id, roots, depth, limit
    )
    return {"page_id": page_id, "count": len(backlinks), "backlinks": backlinks}


# ========== VectorDB 문서 조회 ==========

@router.get("/vectordb/documents")
def api_vectordb_documents(query: str = "", limit: int = 50):
    """벡터DB에 인덱싱된 문서 목록 (검색 가능)"""
    agent = get_agent()
    dept = "planning"
    di = agent.vector_store._ensure_dept(dept)

    if query:
        results = agent.vector_store.search_posts(query, min(limit, 50), dept)
        return {
            "query": query,
            "count": len(results),
            "documents": [
                {
                    "id": r["id"],
                    "score": round(r.get("score", 0), 4),
                    **{k: v for k, v in r.get("metadata", {}).items() if k != "id"},
                }
                for r in results
            ],
        }

    # 전체 목록 (메타데이터만)
    docs = []
    for m in di.metas[:limit]:
        docs.append({k: v for k, v in m.items()})
    return {"count": len(docs), "total": di.count(), "documents": docs}


@router.get("/vectordb/documents/{doc_id}")
def api_vectordb_document(doc_id: str):
    """벡터DB 문서 상세 - 원본 게시글 + 파일 목록"""
    agent = get_agent()
    post = get_post_by_id(agent.posts, doc_id)
    if not post:
        # RAG 통합 문서(sig/sig_union/sigjang/notion)는 agent.posts에 없을 수 있음
        rag_posts = getattr(agent, "rag_posts", []) or []
        post = get_post_by_id(rag_posts, doc_id)
    if not post:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    return {
        "id": post["id"],
        "title": post.get("title", ""),
        "author": post.get("author", ""),
        "date": post.get("date", ""),
        "content_preview": (post.get("content", "") or "")[:500],
        "has_file_content": bool(post.get("file_content")),
        "files": [
            {"name": f.get("name", ""), "size": f.get("size", ""), "local_path": f.get("local_path", "")}
            for f in post.get("files", [])
        ],
    }


@router.post("/files/analyze")
async def api_analyze_file(file: UploadFile = File(...), query: str = ""):
    """업로드된 파일을 AI로 분석"""
    if not file.filename:
        raise HTTPException(400, "파일명이 없습니다.")

    ext = Path(file.filename).suffix.lower()
    parseable = {".xlsx", ".xls", ".pdf", ".pptx", ".docx", ".txt", ".csv"}
    if ext not in parseable:
        raise HTTPException(400, f"분석 가능 형식: {', '.join(parseable)}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "파일 크기 제한 10MB 초과")

    # 저장 후 파싱
    save_path = UPLOAD_DIR / file.filename
    counter = 1
    stem = Path(file.filename).stem
    while save_path.exists():
        save_path = UPLOAD_DIR / f"{stem}_{counter}{ext}"
        counter += 1
    save_path.write_bytes(content)

    from src.data_loader.parser import parse_file
    extracted = parse_file(str(save_path)) or ""
    if not extracted.strip():
        return {"filename": file.filename, "error": "파일에서 텍스트를 추출할 수 없습니다."}

    # GPT 분석
    prompt = query or "파일 내용을 분석하여 핵심 내용을 요약하세요. 숫자/금액이 있으면 정리하세요."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "문서 분석 전문가입니다. 한국어로 답변. 이모지 금지."},
                {"role": "user", "content": f"[파일: {file.filename}]\n{extracted[:12000]}\n\n[분석 요청]\n{prompt}"},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        analysis = response.choices[0].message.content or ""
    except Exception as e:
        return {"filename": file.filename, "extracted_length": len(extracted), "error": f"AI 분석 실패: {e}"}

    return {
        "filename": file.filename,
        "extracted_length": len(extracted),
        "extracted_preview": extracted[:1000],
        "analysis": analysis,
    }


# ========== 사주 분석 보고서 (Agent 무의존, OpenAI 직접 호출) ==========

@router.post("/saju/report")
async def saju_report(request: SajuReportRequest, http_request: Request):
    """사주 분석 신년운세 보고서 SSE 스트리밍 (Agent/VectorDB/Notion 무관)"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY가 설정되지 않았습니다.")

    saju_text = request.saju_text.strip()
    if not saju_text:
        raise HTTPException(status_code=400, detail="사주 데이터가 비어 있습니다.")

    year = request.year
    prompt = SAJU_SYSTEM_PROMPT.replace("{year}", str(year))

    async def generate():
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            stream = client.chat.completions.create(
                model=os.getenv("SAJU_MODEL", "gpt-4.1"),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"다음 사주 데이터를 분석하여 {year}년 신년운세 보고서를 작성해주세요.\n\n{saju_text}"},
                ],
                temperature=0.7,
                max_tokens=4000,
                stream=True,
            )
            for chunk in stream:
                if await http_request.is_disconnected():
                    break
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield f"event: token\ndata: {json.dumps({'content': delta.content}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("사주 보고서 생성 실패: %s", e)
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ========== STT / 회의록 ==========

@router.post("/stt/transcribe")
async def api_stt_transcribe(file: UploadFile = File(...)):
    """음성파일 STT 변환"""
    allowed = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"지원 형식: {', '.join(allowed)}")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:  # Whisper 25MB 제한
        raise HTTPException(400, "파일 크기 제한 25MB 초과")

    from src.stt.transcriber import transcribe_audio
    transcript = transcribe_audio(content, file.filename or "audio.wav")
    return {"transcript": transcript, "length": len(transcript)}


@router.post("/stt/minutes")
async def api_stt_minutes(file: UploadFile = File(...)):
    """음성파일 -> 회의록 SSE 스트리밍 생성"""
    import json as _json
    allowed = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"지원 형식: {', '.join(allowed)}")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "파일 크기 제한 25MB 초과")

    filename = file.filename or "audio.wav"

    def event_stream():
        from src.stt.transcriber import (
            transcribe_audio, generate_minutes_stream,
            _extract_section, _parse_action_items,
        )

        # 1) STT 단계
        yield f"event: status\ndata: {_json.dumps({'phase': 'stt', 'message': '음성 인식 중...'})}\n\n"

        try:
            transcript = transcribe_audio(content, filename)
        except Exception as e:
            yield f"event: error\ndata: {_json.dumps({'message': f'STT 실패: {e}'})}\n\n"
            return

        yield f"event: transcript\ndata: {_json.dumps({'transcript': transcript})}\n\n"

        # 2) 회의록 생성 (스트리밍)
        yield f"event: status\ndata: {_json.dumps({'phase': 'minutes', 'message': '회의록 생성 중...'})}\n\n"

        full_text = ""
        try:
            for chunk in generate_minutes_stream(transcript):
                full_text += chunk
                yield f"event: chunk\ndata: {_json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {_json.dumps({'message': f'회의록 생성 실패: {e}'})}\n\n"
            return

        # 3) 섹션 추출
        summary = _extract_section(full_text, "회의 요약")
        action_items = _extract_section(full_text, "후속 조치")
        action_items_list = _parse_action_items(action_items)

        # 4) 노션 저장
        notion_saved = False
        notion_checklist_saved = False
        try:
            agent = get_agent()
            if agent.notion.is_connected():
                from datetime import datetime as dt
                now_str = dt.now().strftime('%Y-%m-%d %H:%M')
                admin_page_id = os.getenv("NOTION_ADMIN_PAGE_ID", "")

                if admin_page_id:
                    blocks = []
                    for i in range(0, len(full_text), 2000):
                        blocks.append(agent.notion.make_paragraph(full_text[i:i + 2000]))
                    agent.notion.client.pages.create(
                        parent={"page_id": admin_page_id},
                        properties={"title": [{"text": {"content": f"회의록 {now_str}"}}]},
                        children=blocks,
                    )
                    notion_saved = True

                    if action_items_list:
                        todo_blocks = [{
                            "object": "block", "type": "to_do",
                            "to_do": {"rich_text": [{"type": "text", "text": {"content": item}}], "checked": False},
                        } for item in action_items_list]
                        agent.notion.client.pages.create(
                            parent={"page_id": admin_page_id},
                            properties={"title": [{"text": {"content": f"후속 조치 {now_str}"}}]},
                            children=todo_blocks,
                        )
                        notion_checklist_saved = True
        except Exception:
            pass

        # 5) 완료 이벤트
        done_data = {
            "summary": summary,
            "action_items": action_items,
            "action_items_list": action_items_list,
            "notion_saved": notion_saved,
            "notion_checklist_saved": notion_checklist_saved,
        }
        yield f"event: done\ndata: {_json.dumps(done_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# 라우터 등록
app.include_router(router)

# 하위호환: /health 직접 접근
@app.get("/health")
def root_health():
    return health()


# ========== 프론트엔드 정적 파일 서빙 ==========
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
