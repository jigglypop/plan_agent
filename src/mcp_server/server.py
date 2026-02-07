"""
MCP 서버 - Claude와 연동
벡터 DB 검색, 통계 조회, 행사 관리 기능 제공
"""
import os
import sys

from mcp.server.fastmcp import FastMCP

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from src.data import load_posts, get_post_by_id, filter_posts, get_post_stats, list_files
from src.vectordb import VectorStore
from src.notion import NotionClient

# MCP 서버 초기화
mcp = FastMCP("plan-agent")

# 전역 인스턴스
_store = None
_posts = None
_notion = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def get_posts():
    global _posts
    if _posts is None:
        _posts = load_posts()
    return _posts


def get_notion() -> NotionClient:
    global _notion
    if _notion is None:
        _notion = NotionClient()
    return _notion


# ========== 벡터 검색 도구 ==========

@mcp.tool()
def search_posts(query: str, limit: int = 5) -> list[dict]:
    """
    기획위원회 게시글을 시맨틱 검색합니다.

    Args:
        query: 검색 쿼리 (예: "겨울행사 예산", "글램핑 장소", "회의록")
        limit: 결과 개수

    Returns:
        검색된 게시글 목록 (제목, 작성자, 날짜, 본문 미리보기)
    """
    store = get_store()
    posts = get_posts()
    results = store.search_posts(query, limit)
    output = []
    for r in results:
        post = get_post_by_id(posts, r["id"])
        meta = r.get("metadata", {})
        output.append({
            "id": r["id"],
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "date": meta.get("date", ""),
            "content_preview": (post.get("content", "")[:500] if post else ""),
            "files": [f.get("name", "") for f in (post or {}).get("files", [])],
            "relevance": round(1 - r.get("distance", 0), 3),
        })
    return output


@mcp.tool()
def get_post_detail(post_id: str) -> dict:
    """
    게시글 전체 내용을 조회합니다.

    Args:
        post_id: 게시글 ID

    Returns:
        게시글 전체 내용
    """
    posts = get_posts()
    post = get_post_by_id(posts, post_id)
    if not post:
        return {"error": "게시글을 찾을 수 없습니다."}
    return post


@mcp.tool()
def filter_board_posts(year: int = None, author: str = None, keyword: str = None, limit: int = 20) -> list[dict]:
    """
    게시글 목록을 필터링합니다.

    Args:
        year: 연도 필터
        author: 작성자 필터
        keyword: 제목/본문 키워드
        limit: 최대 결과 수

    Returns:
        필터링된 게시글 목록
    """
    posts = get_posts()
    filtered = filter_posts(posts, year=year, author=author, keyword=keyword, limit=limit)
    return [
        {
            "id": p["id"],
            "title": p["title"],
            "author": p.get("author", ""),
            "date": p.get("date", ""),
            "files_count": len(p.get("files", [])),
        }
        for p in filtered
    ]


# ========== 통계 도구 ==========

@mcp.tool()
def get_board_stats() -> dict:
    """
    게시판 전체 통계를 조회합니다.

    Returns:
        게시글 수, 첨부파일 수, 연도별/작성자별 통계
    """
    posts = get_posts()
    return get_post_stats(posts)


@mcp.tool()
def get_attached_files(keyword: str = None, year: int = None) -> list[dict]:
    """
    첨부파일 목록을 조회합니다.

    Args:
        keyword: 파일명 키워드 (예: "예산", "결산", "회의록")
        year: 연도 필터

    Returns:
        첨부파일 목록
    """
    posts = get_posts()
    return list_files(posts, keyword=keyword, year=year)[:30]


# ========== 벡터 DB 관리 ==========

@mcp.tool()
def get_vectordb_stats() -> dict:
    """
    벡터 DB에 저장된 데이터 통계를 조회합니다.

    Returns:
        저장된 항목 수 (events, tasks, posts)
    """
    store = get_store()
    return store.get_stats()


@mcp.tool()
def reload_vectordb() -> str:
    """
    crawled.json에서 벡터 DB를 다시 로드합니다.

    Returns:
        초기화 결과 메시지
    """
    store = get_store()
    posts = load_posts()
    store.add_posts_batch([
        {
            "id": p["id"],
            "title": p["title"],
            "content": p.get("content", ""),
            "author": p.get("author", ""),
            "date": p.get("date", ""),
            "url": p.get("url", ""),
        }
        for p in posts
    ])
    stats = store.get_stats()
    return f"로드 완료: 게시글 {stats['posts']}건"


# ========== 노션 도구 ==========

@mcp.tool()
def notion_list_databases() -> list[dict]:
    """
    노션에서 접근 가능한 데이터베이스 목록을 조회합니다.

    Returns:
        데이터베이스 목록
    """
    notion = get_notion()
    if not notion.is_connected():
        return [{"error": "노션이 연결되지 않았습니다. NOTION_TOKEN을 확인하세요."}]
    return notion.list_databases()


@mcp.tool()
def notion_status() -> dict:
    """
    노션 연결 상태를 확인합니다.

    Returns:
        연결 상태 정보
    """
    notion = get_notion()
    return {
        "connected": notion.is_connected(),
        "token_set": bool(os.getenv("NOTION_TOKEN")),
        "database_id_set": bool(os.getenv("NOTION_DATABASE_ID"))
    }


# ========== 리소스 ==========

@mcp.resource("stats://summary")
def stats_summary_resource() -> str:
    """게시판 통계 요약 리소스"""
    posts = get_posts()
    stats = get_post_stats(posts)
    store = get_store()
    db_stats = store.get_stats()

    lines = [
        "# 기획위원회 게시판 통계",
        "",
        f"- 총 게시글: {stats['total_posts']}건",
        f"- 총 첨부파일: {stats['total_files']}개",
        f"- 기간: {stats['year_range']}",
        f"- VectorDB: 게시글 {db_stats.get('posts', 0)}건 색인됨",
        "",
        "## 연도별 게시글",
    ]
    for y, c in list(stats["by_year"].items())[-10:]:
        lines.append(f"- {y}년: {c}건")

    return "\n".join(lines)


@mcp.resource("dashboard://today")
def dashboard_today_resource() -> str:
    """대시보드 리소스"""
    posts = get_posts()
    stats = get_post_stats(posts)
    recent = posts[:5]

    lines = [
        "# 기획위원회 대시보드",
        "",
        f"총 게시글: {stats['total_posts']}건",
        "",
        "## 최근 게시글",
    ]
    for p in recent:
        lines.append(f"- [{p.get('date', '')}] {p['title']} ({p.get('author', '')})")

    return "\n".join(lines)


def run():
    """MCP 서버 실행"""
    mcp.run()


if __name__ == "__main__":
    run()
