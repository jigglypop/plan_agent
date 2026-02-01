"""
FastAPI 백엔드 서버
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

from src.agent import Agent
from src.crawler import DummyCrawler
from src.stats import StatsAnalyzer
from src.pm import PMManager
from src.notion import NotionClient

app = FastAPI(
    title="Plan Agent API",
    description="AI 기반 기획위원회 PM/통계 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 인스턴스
agent = None
crawler = None
stats = None
pm = None
notion = None


def get_agent():
    global agent
    if agent is None:
        agent = Agent()
    return agent


def get_data():
    global crawler, stats, pm
    if crawler is None:
        crawler = DummyCrawler()
        events = crawler.fetch_events()
        tasks = crawler.fetch_tasks()
        budget_items = crawler.fetch_budget_items()
        attendees = crawler.fetch_attendees()
        stats = StatsAnalyzer(events, tasks, budget_items, attendees)
        pm = PMManager(events, tasks)
    return crawler, stats, pm


def get_notion():
    global notion
    if notion is None:
        notion = NotionClient()
    return notion


# ========== 모델 ==========

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    status: str = "ok"


class EventCreate(BaseModel):
    title: str
    date: str
    location: Optional[str] = ""
    budget: Optional[int] = 0
    manager: Optional[str] = ""
    category: Optional[str] = "기타"


# ========== 엔드포인트 ==========

@app.get("/")
def root():
    return {"message": "Plan Agent API", "version": "1.0.0"}


@app.get("/health")
def health():
    agent = get_agent()
    status = agent.is_ready()
    return {
        "status": "healthy",
        "connections": status
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """AI 에이전트와 대화"""
    agent = get_agent()
    response = agent.chat(request.message)
    return ChatResponse(response=response)


@app.post("/chat/reset")
def reset_chat():
    """대화 초기화"""
    agent = get_agent()
    agent.reset_conversation()
    return {"status": "ok", "message": "대화가 초기화되었습니다."}


@app.get("/stats")
def get_stats():
    """전체 통계"""
    _, stats, _ = get_data()
    return stats.generate_summary()


@app.get("/stats/category")
def get_category_stats():
    """카테고리별 통계"""
    _, stats, _ = get_data()
    return stats.events_by_category()


@app.get("/stats/monthly")
def get_monthly_stats():
    """월별 통계"""
    _, stats, _ = get_data()
    return stats.events_by_month()


@app.get("/stats/manager")
def get_manager_stats():
    """담당자별 통계"""
    _, stats, _ = get_data()
    return stats.events_by_manager()


@app.get("/events")
def get_events():
    """전체 행사 목록"""
    crawler, _, _ = get_data()
    events = crawler.fetch_events()
    return [
        {
            "id": e.id,
            "title": e.title,
            "category": e.category.value,
            "status": e.status.value,
            "start_date": e.start_date.isoformat(),
            "end_date": e.end_date.isoformat(),
            "location": e.location,
            "is_online": e.is_online,
            "expected_attendees": e.expected_attendees,
            "actual_attendees": e.actual_attendees,
            "budget": e.budget,
            "actual_cost": e.actual_cost,
            "manager": e.manager
        }
        for e in events
    ]


@app.get("/events/upcoming")
def get_upcoming_events(days: int = 30):
    """다가오는 행사"""
    _, _, pm = get_data()
    events = pm.get_upcoming_events(days)
    return [
        {
            "id": e.id,
            "title": e.title,
            "start_date": e.start_date.isoformat(),
            "location": e.location,
            "manager": e.manager
        }
        for e in events
    ]


@app.get("/tasks")
def get_tasks():
    """전체 태스크"""
    crawler, _, _ = get_data()
    tasks = crawler.fetch_tasks()
    return [
        {
            "id": t.id,
            "event_id": t.event_id,
            "title": t.title,
            "status": t.status.value,
            "assignee": t.assignee,
            "due_date": t.due_date.isoformat(),
            "priority": t.priority
        }
        for t in tasks
    ]


@app.get("/tasks/overdue")
def get_overdue_tasks():
    """기한 초과 태스크"""
    _, _, pm = get_data()
    tasks = pm.get_overdue_tasks()
    return [
        {
            "id": t.id,
            "title": t.title,
            "assignee": t.assignee,
            "due_date": t.due_date.isoformat()
        }
        for t in tasks
    ]


@app.get("/reminders")
def get_reminders():
    """리마인더"""
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
        for r in reminders
    ]


@app.get("/report/weekly")
def get_weekly_report():
    """주간 리포트"""
    _, _, pm = get_data()
    return pm.generate_weekly_report()


@app.get("/dashboard")
def get_dashboard():
    """대시보드 데이터"""
    _, _, pm = get_data()
    return pm.get_dashboard_data()


# ========== 노션 ==========

@app.get("/notion/status")
def notion_status():
    """노션 연결 상태"""
    notion = get_notion()
    return {
        "connected": notion.is_connected(),
        "token_set": bool(os.getenv("NOTION_TOKEN")),
        "database_id_set": bool(os.getenv("NOTION_DATABASE_ID"))
    }


@app.get("/notion/databases")
def notion_databases():
    """노션 데이터베이스 목록"""
    notion = get_notion()
    if not notion.is_connected():
        raise HTTPException(status_code=503, detail="Notion not connected")
    return notion.list_databases()
