"""
더미 크롤러 - 테스트용
실제 사이트 연동 전까지 사용
"""
from typing import List
from .base import BaseCrawler
from src.data import Event, generate_all_dummy_data


class DummyCrawler(BaseCrawler):
    """더미 데이터 반환 크롤러"""
    
    def __init__(self):
        super().__init__()
        self._data = None
    
    def login(self) -> bool:
        """더미는 로그인 불필요"""
        return True
    
    def _load_data(self):
        if self._data is None:
            self._data = generate_all_dummy_data()
        return self._data
    
    def fetch_events(self, start_date=None, end_date=None) -> List[Event]:
        """더미 행사 목록 반환"""
        data = self._load_data()
        events = data["events"]
        
        if start_date:
            events = [e for e in events if e.start_date >= start_date]
        if end_date:
            events = [e for e in events if e.start_date <= end_date]
        
        return events
    
    def fetch_event_detail(self, event_id: str) -> Event:
        """더미 행사 상세 반환"""
        data = self._load_data()
        for event in data["events"]:
            if event.id == event_id:
                return event
        return None
    
    def fetch_tasks(self, event_id: str = None):
        """태스크 목록"""
        data = self._load_data()
        tasks = data["tasks"]
        if event_id:
            tasks = [t for t in tasks if t.event_id == event_id]
        return tasks
    
    def fetch_budget_items(self, event_id: str = None):
        """예산 항목"""
        data = self._load_data()
        items = data["budget_items"]
        if event_id:
            items = [i for i in items if i.event_id == event_id]
        return items
    
    def fetch_attendees(self, event_id: str = None):
        """참석자 목록"""
        data = self._load_data()
        attendees = data["attendees"]
        if event_id:
            attendees = [a for a in attendees if a.event_id == event_id]
        return attendees
