"""
크롤러 베이스 클래스
실제 크롤링 구현 시 이 클래스를 상속
"""
from abc import ABC, abstractmethod
from typing import List
from src.data import Event


class BaseCrawler(ABC):
    """크롤러 인터페이스"""
    
    def __init__(self, base_url: str = "", credentials: dict = None):
        self.base_url = base_url
        self.credentials = credentials or {}
    
    @abstractmethod
    def login(self) -> bool:
        """로그인 필요시 구현"""
        pass
    
    @abstractmethod
    def fetch_events(self, start_date=None, end_date=None) -> List[Event]:
        """행사 목록 크롤링"""
        pass
    
    @abstractmethod
    def fetch_event_detail(self, event_id: str) -> Event:
        """행사 상세 정보 크롤링"""
        pass
    
    def close(self):
        """리소스 정리"""
        pass
