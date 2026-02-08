"""
FastAPI 백엔드 서버
API 엔드포인트: /api/* 하위
프론트엔드: / (정적 파일 서빙)
"""
import os
import logging
import tempfile
import shutil
from pathlib import Path

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

from src.agent import Agent
from src.data import get_post_by_id, filter_posts, get_post_stats, list_files

app = FastAPI(
    title="Plan Agent API",
    description="AI 기반 기획위원회 PM/통계 시스템",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


class ChatResponse(BaseModel):
    response: str
    status: str = "ok"


# ========== API 라우터 ==========

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    try:
        agent = get_agent()
        connections = agent.is_ready()
    except Exception as e:
        # health는 절대 500으로 죽지 않게 함
        return {"status": "error", "error": str(e)}

    status = "healthy"
    vdb = connections.get("vectordb")
    if isinstance(vdb, dict) and vdb.get("status") in ("error", "repaired"):
        status = "degraded"
    return {"status": status, "connections": connections}

@router.get("/vectordb/status")
def vectordb_status():
    """벡터DB 색인 상태/진행률"""
    agent = get_agent()
    return agent.vectordb_status()


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

    save_path = UPLOAD_DIR / file.filename
    save_path.write_bytes(content)

    extracted = ""
    is_image = ext in ALLOWED_IMG_EXT
    if not is_image:
        try:
            from src.data.parser import parse_file
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
        message = f"[업로드된 파일 내용]\n{request.file_context}\n\n[질문]\n{message}"
    response = agent.chat(message, request.session_id)
    return ChatResponse(response=response)


@router.post("/chat/reset")
def reset_chat(request: ResetChatRequest):
    """대화 초기화"""
    agent = get_agent()
    agent.reset(request.session_id or "default")
    return {"status": "ok", "message": "대화가 초기화되었습니다."}


# ========== 게시글 ==========

@router.get("/posts")
def api_list_posts(year: int = None, author: str = None, keyword: str = None, limit: int = 0):
    """게시글 목록"""
    agent = get_agent()
    filtered = filter_posts(agent.posts, year=year, author=author, keyword=keyword, limit=limit)
    return [
        {
            "id": p["id"],
            "title": p["title"],
            "author": p.get("author", ""),
            "date": p.get("date", ""),
            "views": p.get("views", 0),
            "files_count": len(p.get("files", [])),
        }
        for p in filtered
    ]


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
    output = []
    for r in results:
        post = get_post_by_id(agent.posts, r["id"])
        if post:
            output.append({
                "id": post["id"],
                "title": post["title"],
                "author": post.get("author", ""),
                "date": post.get("date", ""),
                "content_preview": post.get("content", "")[:300],
                "relevance": round(1 - r.get("distance", 0), 3),
            })
    return output


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
        "recent_posts": [
            {
                "id": p["id"],
                "title": p["title"],
                "author": p.get("author", ""),
                "date": p.get("date", ""),
            }
            for p in recent
        ],
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


def _fetch_notion_children(client, page_id: str, depth: int = 0, max_depth: int = 3) -> list:
    """노션 페이지 하위 구조를 재귀적으로 조회"""
    if depth >= max_depth:
        return []
    try:
        resp = client.blocks.children.list(block_id=page_id, page_size=100)
    except Exception:
        return []

    nodes = []
    for block in resp.get("results", []):
        if block.get("type") == "child_page":
            title = block["child_page"].get("title", "Untitled")
            child_id = block["id"]
            children = _fetch_notion_children(client, child_id, depth + 1, max_depth)
            nodes.append({"id": child_id, "title": title, "children": children})
        elif block.get("type") == "child_database":
            title = block["child_database"].get("title", "Untitled DB")
            nodes.append({"id": block["id"], "title": f"[DB] {title}", "children": []})
    return nodes


@router.get("/notion/tree")
def notion_tree():
    """노션 공개용/운영진용 페이지 트리 구조"""
    agent = get_agent()
    if not agent.notion.is_connected():
        raise HTTPException(status_code=503, detail="노션 미연결")

    result = {}
    for key, label in [("NOTION_PUBLIC_PAGE_ID", "public"), ("NOTION_ADMIN_PAGE_ID", "admin")]:
        page_id = os.getenv(key, "")
        if not page_id:
            result[label] = {"id": "", "title": label, "children": []}
            continue

        children = _fetch_notion_children(agent.notion.client, page_id)
        # 루트 페이지 제목 가져오기
        try:
            page = agent.notion.client.pages.retrieve(page_id=page_id)
            title = ""
            for prop in page.get("properties", {}).values():
                if prop.get("type") == "title":
                    title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                    break
            if not title:
                title = label
        except Exception:
            title = label

        result[label] = {"id": page_id, "title": title, "children": children}

    return result


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
