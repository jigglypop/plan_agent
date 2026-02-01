"""
MCP 서버 - Claude와 연동
벡터 DB 검색, 통계 조회, 행사 관리 기능 제공
"""
import os
import sys
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from src.vectordb import VectorStore
from src.crawler import DummyCrawler
from src.stats import StatsAnalyzer
from src.pm import PMManager
from src.notion import NotionClient

# MCP 서버 초기화
mcp = FastMCP("plan-agent")

# 전역 인스턴스
_store = None
_crawler = None
_stats = None
_pm = None
_notion = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def get_data():
    global _crawler, _stats, _pm
    if _crawler is None:
        _crawler = DummyCrawler()
        events = _crawler.fetch_events()
        tasks = _crawler.fetch_tasks()
        budget_items = _crawler.fetch_budget_items()
        attendees = _crawler.fetch_attendees()
        _stats = StatsAnalyzer(events, tasks, budget_items, attendees)
        _pm = PMManager(events, tasks)
    return _crawler, _stats, _pm


def get_notion() -> NotionClient:
    global _notion
    if _notion is None:
        _notion = NotionClient()
    return _notion


# ========== 벡터 검색 도구 ==========

@mcp.tool()
def search_events(query: str, limit: int = 5) -> list[dict]:
    """
    행사를 시맨틱 검색합니다.
    
    Args:
        query: 검색 쿼리 (예: "해커톤", "네트워킹 행사", "3월 세미나")
        limit: 결과 개수 (기본 5개)
    
    Returns:
        검색된 행사 목록
    """
    store = get_store()
    results = store.search_events(query, limit)
    return [
        {
            "id": r["id"],
            "title": r["metadata"].get("title", ""),
            "category": r["metadata"].get("category", ""),
            "date": r["metadata"].get("date", ""),
            "location": r["metadata"].get("location", ""),
            "manager": r["metadata"].get("manager", ""),
            "relevance": 1 - r["distance"]  # 거리를 관련도로 변환
        }
        for r in results
    ]


@mcp.tool()
def search_tasks(query: str, limit: int = 5) -> list[dict]:
    """
    태스크를 시맨틱 검색합니다.
    
    Args:
        query: 검색 쿼리 (예: "홍보물 제작", "예산 신청")
        limit: 결과 개수
    
    Returns:
        검색된 태스크 목록
    """
    store = get_store()
    results = store.search_tasks(query, limit)
    return [
        {
            "id": r["id"],
            "title": r["metadata"].get("title", ""),
            "status": r["metadata"].get("status", ""),
            "assignee": r["metadata"].get("assignee", ""),
            "relevance": 1 - r["distance"]
        }
        for r in results
    ]


@mcp.tool()
def search_posts(query: str, limit: int = 5) -> list[dict]:
    """
    크롤링된 게시글을 시맨틱 검색합니다.
    
    Args:
        query: 검색 쿼리
        limit: 결과 개수
    
    Returns:
        검색된 게시글 목록
    """
    store = get_store()
    results = store.search_posts(query, limit)
    return [
        {
            "id": r["id"],
            "title": r["metadata"].get("title", ""),
            "author": r["metadata"].get("author", ""),
            "date": r["metadata"].get("date", ""),
            "url": r["metadata"].get("url", ""),
            "relevance": 1 - r["distance"]
        }
        for r in results
    ]


@mcp.tool()
def search_all(query: str, limit: int = 3) -> dict:
    """
    행사, 태스크, 게시글을 통합 검색합니다.
    
    Args:
        query: 검색 쿼리
        limit: 각 카테고리당 결과 개수
    
    Returns:
        검색 결과 (events, tasks, posts)
    """
    store = get_store()
    return store.search_all(query, limit)


# ========== 통계 도구 ==========

@mcp.tool()
def get_stats_summary() -> dict:
    """
    전체 통계 요약을 조회합니다.
    
    Returns:
        통계 요약 (행사수, 참석자, 예산, 참석률 등)
    """
    _, stats, _ = get_data()
    return stats.generate_summary()


@mcp.tool()
def get_category_stats() -> dict:
    """
    카테고리별 행사 통계를 조회합니다.
    
    Returns:
        카테고리별 행사 수
    """
    _, stats, _ = get_data()
    return stats.events_by_category()


@mcp.tool()
def get_monthly_stats() -> dict:
    """
    월별 행사 통계를 조회합니다.
    
    Returns:
        월별 행사 수
    """
    _, stats, _ = get_data()
    return stats.events_by_month()


@mcp.tool()
def get_manager_stats() -> dict:
    """
    담당자별 행사 통계를 조회합니다.
    
    Returns:
        담당자별 행사 수
    """
    _, stats, _ = get_data()
    return stats.events_by_manager()


# ========== PM 도구 ==========

@mcp.tool()
def get_upcoming_events(days: int = 30) -> list[dict]:
    """
    다가오는 행사 목록을 조회합니다.
    
    Args:
        days: 며칠 이내 (기본 30일)
    
    Returns:
        예정된 행사 목록
    """
    _, _, pm = get_data()
    events = pm.get_upcoming_events(days)
    return [
        {
            "id": e.id,
            "title": e.title,
            "date": e.start_date.strftime("%Y-%m-%d"),
            "location": e.location,
            "manager": e.manager,
            "expected_attendees": e.expected_attendees
        }
        for e in events[:10]
    ]


@mcp.tool()
def get_overdue_tasks() -> list[dict]:
    """
    기한이 지난 태스크를 조회합니다.
    
    Returns:
        기한 초과 태스크 목록
    """
    _, _, pm = get_data()
    tasks = pm.get_overdue_tasks()
    return [
        {
            "id": t.id,
            "title": t.title,
            "assignee": t.assignee,
            "due_date": t.due_date.strftime("%Y-%m-%d"),
            "priority": t.priority
        }
        for t in tasks[:10]
    ]


@mcp.tool()
def get_tasks_by_assignee(assignee: str) -> list[dict]:
    """
    특정 담당자의 태스크를 조회합니다.
    
    Args:
        assignee: 담당자 이름
    
    Returns:
        해당 담당자의 태스크 목록
    """
    _, _, pm = get_data()
    tasks = pm.get_tasks_by_assignee(assignee)
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status.value,
            "due_date": t.due_date.strftime("%Y-%m-%d"),
            "priority": t.priority
        }
        for t in tasks[:10]
    ]


@mcp.tool()
def get_reminders() -> list[dict]:
    """
    행사 리마인더를 조회합니다.
    
    Returns:
        리마인더 목록 (D-day 알림)
    """
    _, _, pm = get_data()
    reminders = pm.generate_reminders()
    return [
        {
            "event_id": r.event_id,
            "event_title": r.event_title,
            "days_until": r.days_until,
            "message": r.message,
            "priority": r.priority
        }
        for r in reminders[:10]
    ]


@mcp.tool()
def get_weekly_report() -> dict:
    """
    주간 리포트를 생성합니다.
    
    Returns:
        주간 활동 리포트
    """
    _, _, pm = get_data()
    return pm.generate_weekly_report()


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
def init_vectordb_with_dummy() -> str:
    """
    벡터 DB를 더미 데이터로 초기화합니다.
    
    Returns:
        초기화 결과 메시지
    """
    from src.vectordb.store import init_vector_store_with_dummy
    store = init_vector_store_with_dummy()
    stats = store.get_stats()
    return f"초기화 완료: 행사 {stats['events']}건, 태스크 {stats['tasks']}건"


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
    """통계 요약 리소스"""
    _, stats, _ = get_data()
    summary = stats.generate_summary()
    return f"""
# 통계 요약

## 개요
- 총 행사: {summary['overview']['total_events']}건
- 총 참석자: {summary['overview']['total_attendees']:,}명
- 총 예산: {summary['overview']['total_budget']:,}원

## 성과 지표
- 평균 참석률: {summary['performance']['average_attendance_rate']}%
- 예산 효율성: {summary['performance']['budget_efficiency']}%
- 태스크 완료율: {summary['performance']['task_completion_rate']}%
"""


@mcp.resource("dashboard://today")
def dashboard_today_resource() -> str:
    """오늘의 대시보드 리소스"""
    _, _, pm = get_data()
    dashboard = pm.get_dashboard_data()
    
    lines = ["# 오늘의 대시보드", ""]
    
    if dashboard.get("today_events"):
        lines.append("## 오늘 행사")
        for e in dashboard["today_events"]:
            lines.append(f"- {e['title']} @ {e['location']}")
    else:
        lines.append("## 오늘 행사 없음")
    
    lines.append("")
    lines.append(f"## 태스크 현황")
    lines.append(f"- 대기 중: {dashboard.get('pending_tasks', 0)}건")
    lines.append(f"- 기한 초과: {dashboard.get('overdue_tasks', 0)}건")
    
    return "\n".join(lines)


def run():
    """MCP 서버 실행"""
    mcp.run()


if __name__ == "__main__":
    run()
