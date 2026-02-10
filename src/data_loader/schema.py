"""
데이터 스키마
기획위원회 행사/태스크/예산/참석자 모델 + 게시글 모델
"""
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional


class EventCategory(Enum):
    SEMINAR = "세미나"
    WORKSHOP = "워크샵"
    CONFERENCE = "컨퍼런스"
    MEETING = "정기회의"
    NETWORKING = "네트워킹"
    FESTIVAL = "축제"
    COMPETITION = "대회"
    OTHER = "기타"


class EventStatus(Enum):
    PLANNED = "기획중"
    CONFIRMED = "확정"
    IN_PROGRESS = "진행중"
    COMPLETED = "완료"
    CANCELLED = "취소"


class TaskStatus(Enum):
    TODO = "할일"
    IN_PROGRESS = "진행중"
    DONE = "완료"
    BLOCKED = "보류"


@dataclass
class Event:
    id: str
    title: str
    category: EventCategory
    status: EventStatus
    start_date: datetime
    end_date: datetime
    location: str = ""
    is_online: bool = False
    expected_attendees: int = 0
    actual_attendees: int = 0
    budget: int = 0
    actual_cost: int = 0
    manager: str = ""
    description: str = ""
    tags: list = field(default_factory=list)


@dataclass
class Task:
    id: str
    event_id: str
    title: str
    status: TaskStatus
    assignee: str
    due_date: datetime
    priority: int = 2


@dataclass
class BudgetItem:
    id: str
    event_id: str
    category: str
    description: str
    planned_amount: int
    actual_amount: int = 0
    is_paid: bool = False
    paid_at: Optional[datetime] = None


@dataclass
class Attendee:
    id: str
    event_id: str
    name: str
    email: str = ""
    phone: str = ""
    registered_at: Optional[datetime] = None
    attended: bool = False
    feedback_score: int = 0
    feedback_comment: str = ""


def generate_all_dummy_data():
    """하위 호환용 빈 데이터 반환"""
    return {
        "events": [],
        "tasks": [],
        "budget_items": [],
        "attendees": [],
    }
