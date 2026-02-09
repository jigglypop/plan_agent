"""
PM 기능 모듈
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from src.data import Event, Task, TaskStatus, EventStatus


@dataclass
class Reminder:
    event_id: str
    event_title: str
    days_until: int
    message: str
    priority: str  # high, medium, low


@dataclass
class ActionItem:
    task_id: str
    title: str
    assignee: str
    due_date: datetime
    event_title: str


class PMManager:
    """PM 업무 관리자"""
    
    def __init__(self, events: List[Event], tasks: List[Task]):
        self.events = events
        self.tasks = tasks
    
    # ========== 일정 관리 ==========
    
    def get_upcoming_events(self, days: int = 30) -> List[Event]:
        """다가오는 행사 목록"""
        now = datetime.now()
        end = now + timedelta(days=days)
        upcoming = [e for e in self.events 
                    if e.start_date and now <= e.start_date <= end 
                    and e.status not in [EventStatus.COMPLETED, EventStatus.CANCELLED]]
        return sorted(upcoming, key=lambda x: x.start_date)
    
    def get_today_events(self) -> List[Event]:
        """오늘 행사"""
        today = datetime.now().date()
        return [e for e in self.events if e.start_date and e.start_date.date() == today]
    
    def generate_reminders(self) -> List[Reminder]:
        """D-day 리마인더 생성"""
        reminders = []
        now = datetime.now()
        
        for event in self.events:
            if event.status in [EventStatus.COMPLETED, EventStatus.CANCELLED]:
                continue
            if not event.start_date:
                continue
            
            days_until = (event.start_date - now).days
            
            if days_until < 0:
                continue
            
            # D-30, D-7, D-3, D-1, D-day
            thresholds = {
                0: ("high", "오늘 행사입니다!"),
                1: ("high", "내일 행사가 있습니다."),
                3: ("medium", "행사 3일 전입니다. 최종 점검이 필요합니다."),
                7: ("medium", "행사 1주일 전입니다. 준비 상황을 확인하세요."),
                30: ("low", "행사 1달 전입니다. 사전 준비를 시작하세요."),
            }
            
            for threshold, (priority, msg) in thresholds.items():
                if days_until == threshold:
                    reminders.append(Reminder(
                        event_id=event.id,
                        event_title=event.title,
                        days_until=days_until,
                        message=msg,
                        priority=priority
                    ))
                    break
        
        return sorted(reminders, key=lambda x: x.days_until)
    
    def check_schedule_conflicts(self) -> List[Dict]:
        """일정 충돌 감지"""
        conflicts = []
        events = [e for e in self.events 
                  if e.status not in [EventStatus.COMPLETED, EventStatus.CANCELLED]
                  and e.start_date is not None]
        
        for i, e1 in enumerate(events):
            for e2 in events[i+1:]:
                # 같은 날, 같은 장소
                if (e1.start_date.date() == e2.start_date.date() 
                    and e1.location == e2.location
                    and not e1.is_online):
                    conflicts.append({
                        "event1": e1.title,
                        "event2": e2.title,
                        "date": e1.start_date.strftime("%Y-%m-%d"),
                        "location": e1.location,
                        "type": "장소 충돌"
                    })
                
                # 같은 담당자, 시간 겹침
                if e1.manager == e2.manager and e1.end_date and e2.end_date:
                    if not (e1.end_date <= e2.start_date or e2.end_date <= e1.start_date):
                        conflicts.append({
                            "event1": e1.title,
                            "event2": e2.title,
                            "manager": e1.manager,
                            "type": "담당자 일정 충돌"
                        })
        
        return conflicts
    
    # ========== 태스크 관리 ==========
    
    def get_pending_tasks(self) -> List[Task]:
        """미완료 태스크"""
        return [t for t in self.tasks if t.status in [TaskStatus.TODO, TaskStatus.IN_PROGRESS]]
    
    def get_overdue_tasks(self) -> List[Task]:
        """기한 초과 태스크"""
        now = datetime.now()
        return [t for t in self.tasks 
                if t.due_date and t.due_date < now
                and t.status not in [TaskStatus.DONE, TaskStatus.BLOCKED]]
    
    def get_tasks_due_soon(self, days: int = 3) -> List[Task]:
        """곧 마감인 태스크"""
        now = datetime.now()
        end = now + timedelta(days=days)
        return [t for t in self.tasks 
                if t.due_date and now <= t.due_date <= end 
                and t.status not in [TaskStatus.DONE, TaskStatus.BLOCKED]]
    
    def get_tasks_by_assignee(self, assignee: str) -> List[Task]:
        """담당자별 태스크"""
        return [t for t in self.tasks if t.assignee == assignee]
    
    def get_action_items(self) -> List[ActionItem]:
        """액션 아이템 목록 (우선 처리 필요)"""
        items = []
        overdue = self.get_overdue_tasks()
        due_soon = self.get_tasks_due_soon()
        
        # 이벤트 매핑
        event_map = {e.id: e.title for e in self.events}
        
        seen_ids = {i.task_id for i in items}
        for task in overdue + due_soon:
            if task.id not in seen_ids:
                items.append(ActionItem(
                    task_id=task.id,
                    title=task.title,
                    assignee=task.assignee,
                    due_date=task.due_date,
                    event_title=event_map.get(task.event_id, "")
                ))
                seen_ids.add(task.id)
        
        return sorted(items, key=lambda x: x.due_date)
    
    def generate_checklist(self, event: Event) -> List[str]:
        """행사별 체크리스트 자동 생성"""
        base_checklist = [
            "장소 예약 확인",
            "예산 신청/승인",
            "홍보물 제작",
            "참가자 모집 공지",
            "물품 구매 목록 작성",
            "식사/다과 준비",
            "현수막/배너 제작",
            "사전 안내 메일 발송",
            "당일 진행 일정표 작성",
            "현장 셋업",
            "참석자 명단 확인",
            "사진/영상 촬영자 배정",
            "비상 연락망 공유",
        ]
        
        # 온라인 행사 추가 항목
        if event.is_online:
            base_checklist.extend([
                "화상회의 링크 생성",
                "접속 테스트",
                "녹화 설정 확인",
            ])
        
        # 대규모 행사 추가 항목
        if getattr(event, "expected_attendees", 0) and event.expected_attendees > 100:
            base_checklist.extend([
                "주차 안내",
                "안전요원 배치",
                "의료 지원 준비",
            ])
        
        return base_checklist
    
    # ========== 리포트 ==========
    
    def generate_weekly_report(self) -> Dict:
        """주간 리포트"""
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        week_later = now + timedelta(days=7)
        
        completed_this_week = [e for e in self.events 
                               if e.status == EventStatus.COMPLETED 
                               and e.end_date and week_ago <= e.end_date <= now]
        
        upcoming_next_week = [e for e in self.events 
                              if e.start_date and now <= e.start_date <= week_later
                              and e.status not in [EventStatus.COMPLETED, EventStatus.CANCELLED]]
        
        return {
            "period": f"{week_ago.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}",
            "completed_events": len(completed_this_week),
            "completed_list": [{"title": e.title, "attendees": getattr(e, "actual_attendees", 0)} for e in completed_this_week],
            "upcoming_events": len(upcoming_next_week),
            "upcoming_list": [{"title": e.title, "date": e.start_date.strftime('%Y-%m-%d') if e.start_date else ""} for e in upcoming_next_week],
            "pending_tasks": len(self.get_pending_tasks()),
            "overdue_tasks": len(self.get_overdue_tasks()),
            "conflicts": self.check_schedule_conflicts(),
            "generated_at": now.isoformat()
        }
    
    def get_dashboard_data(self) -> Dict:
        """대시보드용 데이터"""
        return {
            "reminders": [r.__dict__ for r in self.generate_reminders()[:5]],
            "today_events": [{"title": e.title, "location": e.location} for e in self.get_today_events()],
            "upcoming_events": [{"title": e.title, "date": e.start_date.strftime('%m/%d') if e.start_date else "", "days": (e.start_date - datetime.now()).days if e.start_date else 0} 
                               for e in self.get_upcoming_events(7)],
            "overdue_tasks": len(self.get_overdue_tasks()),
            "pending_tasks": len(self.get_pending_tasks()),
            "conflicts_count": len(self.check_schedule_conflicts()),
        }
