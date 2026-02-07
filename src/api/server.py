"""
FastAPI 백엔드 서버
API 엔드포인트: /api/* 하위
프론트엔드: / (정적 파일 서빙)
"""
import os
from pathlib import Path

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
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
_agent = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


# ========== 모델 ==========

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    status: str = "ok"


# ========== API 라우터 ==========

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    agent = get_agent()
    return {"status": "healthy", "connections": agent.is_ready()}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """AI 에이전트와 대화"""
    agent = get_agent()
    response = agent.chat(request.message, request.session_id)
    return ChatResponse(response=response)


@router.post("/chat/reset")
def reset_chat(session_id: str = "default"):
    """대화 초기화"""
    agent = get_agent()
    agent.reset(session_id)
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
        return {"error": "not found"}
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
