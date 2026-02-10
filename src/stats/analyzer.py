"""
통계 분석 모듈
"""
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

from src.data_loader import Event, Task, BudgetItem, Attendee, EventStatus, EventCategory


class StatsAnalyzer:
    """행사 통계 분석기"""
    
    def __init__(self, events: List[Event], tasks: List[Task] = None,
                 budget_items: List[BudgetItem] = None, attendees: List[Attendee] = None):
        self.events = events
        self.tasks = tasks or []
        self.budget_items = budget_items or []
        self.attendees = attendees or []
    
    # ========== 기본 통계 ==========
    
    def total_events(self) -> int:
        """총 행사 수"""
        return len(self.events)
    
    def events_by_status(self) -> Dict[str, int]:
        """상태별 행사 수"""
        result = defaultdict(int)
        for e in self.events:
            result[e.status.value] += 1
        return dict(result)
    
    def total_attendees(self) -> int:
        """총 참석자 수"""
        return sum(getattr(e, "actual_attendees", 0) or 0 for e in self.events)
    
    def total_budget(self) -> int:
        """총 예산"""
        return sum(getattr(e, "budget", 0) or 0 for e in self.events)
    
    def total_actual_cost(self) -> int:
        """총 실제 비용"""
        return sum(getattr(e, "actual_cost", 0) or 0 for e in self.events)
    
    def average_attendance_rate(self) -> float:
        """평균 참석률"""
        completed = [e for e in self.events
                     if e.status == EventStatus.COMPLETED
                     and getattr(e, "expected_attendees", 0)
                     and e.expected_attendees > 0]
        if not completed:
            return 0.0
        rates = [(getattr(e, "actual_attendees", 0) or 0) / e.expected_attendees for e in completed]
        return sum(rates) / len(rates) * 100
    
    # ========== 분석 통계 ==========
    
    def events_by_category(self) -> Dict[str, int]:
        """카테고리별 행사 수"""
        result = defaultdict(int)
        for e in self.events:
            result[e.category.value] += 1
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
    
    def events_by_month(self) -> Dict[str, int]:
        """월별 행사 수"""
        result = defaultdict(int)
        for e in self.events:
            if not e.start_date:
                continue
            key = e.start_date.strftime("%Y-%m")
            result[key] += 1
        return dict(sorted(result.items()))
    
    def events_by_year(self) -> Dict[int, int]:
        """연도별 행사 수"""
        result = defaultdict(int)
        for e in self.events:
            if not e.start_date:
                continue
            result[e.start_date.year] += 1
        return dict(sorted(result.items()))
    
    def events_by_weekday(self) -> Dict[str, int]:
        """요일별 행사 수"""
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        result = defaultdict(int)
        for e in self.events:
            if not e.start_date:
                continue
            result[weekdays[e.start_date.weekday()]] += 1
        return {d: result[d] for d in weekdays}
    
    def events_by_manager(self) -> Dict[str, int]:
        """담당자별 행사 수"""
        result = defaultdict(int)
        for e in self.events:
            result[getattr(e, "manager", "") or ""] += 1
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
    
    def events_by_location(self) -> Dict[str, int]:
        """장소별 행사 수"""
        result = defaultdict(int)
        for e in self.events:
            result[getattr(e, "location", "") or ""] += 1
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
    
    def online_vs_offline(self) -> Dict[str, int]:
        """온/오프라인 비율"""
        online = sum(1 for e in self.events if e.is_online)
        return {"온라인": online, "오프라인": len(self.events) - online}
    
    def budget_efficiency(self) -> float:
        """예산 효율성 (실제비용/예산)"""
        total_budget = self.total_budget()
        if total_budget == 0:
            return 0.0
        return self.total_actual_cost() / total_budget * 100
    
    def cost_per_attendee(self) -> float:
        """참석자 1인당 비용"""
        total = self.total_attendees()
        if total == 0:
            return 0.0
        return self.total_actual_cost() / total
    
    def top_events_by_attendance(self, n: int = 10) -> List[Dict]:
        """참석자 많은 행사 TOP N"""
        completed = [e for e in self.events if e.status == EventStatus.COMPLETED]
        sorted_events = sorted(completed, key=lambda x: getattr(x, "actual_attendees", 0) or 0, reverse=True)[:n]
        return [{"title": e.title, "attendees": getattr(e, "actual_attendees", 0),
                 "date": e.start_date.strftime("%Y-%m-%d") if e.start_date else ""} 
                for e in sorted_events]
    
    def top_events_by_budget(self, n: int = 10) -> List[Dict]:
        """예산 높은 행사 TOP N"""
        sorted_events = sorted(self.events, key=lambda x: getattr(x, "budget", 0) or 0, reverse=True)[:n]
        return [{"title": e.title, "budget": getattr(e, "budget", 0),
                 "date": e.start_date.strftime("%Y-%m-%d") if e.start_date else ""} 
                for e in sorted_events]
    
    # ========== 태스크 통계 ==========
    
    def task_completion_rate(self) -> float:
        """태스크 완료율"""
        if not self.tasks:
            return 0.0
        done = sum(1 for t in self.tasks if t.status and t.status.value == "완료")
        return done / len(self.tasks) * 100
    
    def tasks_by_status(self) -> Dict[str, int]:
        """상태별 태스크 수"""
        result = defaultdict(int)
        for t in self.tasks:
            result[t.status.value if t.status else "미지정"] += 1
        return dict(result)
    
    def tasks_by_assignee(self) -> Dict[str, int]:
        """담당자별 태스크 수"""
        result = defaultdict(int)
        for t in self.tasks:
            result[t.assignee] += 1
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
    
    def overdue_tasks(self) -> List[Task]:
        """기한 초과 태스크"""
        now = datetime.now()
        return [t for t in self.tasks 
                if t.due_date and t.due_date < now
                and t.status and t.status.value not in ["완료", "보류"]]
    
    # ========== 예산 통계 ==========
    
    def budget_by_category(self) -> Dict[str, int]:
        """카테고리별 예산"""
        result = defaultdict(int)
        for item in self.budget_items:
            result[item.category] += item.planned_amount
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
    
    def actual_cost_by_category(self) -> Dict[str, int]:
        """카테고리별 실제 비용"""
        result = defaultdict(int)
        for item in self.budget_items:
            result[item.category] += item.actual_amount
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
    
    # ========== 피드백 통계 ==========
    
    def average_feedback_score(self) -> float:
        """평균 피드백 점수"""
        scores = [a.feedback_score for a in self.attendees if a.feedback_score]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
    
    def feedback_distribution(self) -> Dict[int, int]:
        """피드백 점수 분포"""
        result = defaultdict(int)
        for a in self.attendees:
            if a.feedback_score:
                result[a.feedback_score] += 1
        return dict(sorted(result.items()))
    
    # ========== 종합 리포트 ==========
    
    def generate_summary(self) -> Dict[str, Any]:
        """종합 요약 리포트"""
        return {
            "overview": {
                "total_events": self.total_events(),
                "events_by_status": self.events_by_status(),
                "total_attendees": self.total_attendees(),
                "total_budget": self.total_budget(),
                "total_actual_cost": self.total_actual_cost(),
            },
            "performance": {
                "average_attendance_rate": round(self.average_attendance_rate(), 1),
                "budget_efficiency": round(self.budget_efficiency(), 1),
                "cost_per_attendee": round(self.cost_per_attendee(), 0),
                "task_completion_rate": round(self.task_completion_rate(), 1),
                "average_feedback_score": round(self.average_feedback_score(), 2),
            },
            "distribution": {
                "by_category": self.events_by_category(),
                "by_month": self.events_by_month(),
                "by_weekday": self.events_by_weekday(),
                "online_vs_offline": self.online_vs_offline(),
            },
            "rankings": {
                "top_by_attendance": self.top_events_by_attendance(5),
                "top_by_budget": self.top_events_by_budget(5),
                "by_manager": self.events_by_manager(),
            },
            "generated_at": datetime.now().isoformat()
        }
