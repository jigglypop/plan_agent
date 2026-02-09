"""
노션 API 클라이언트
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from notion_client import Client
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
    Client = None


logger = logging.getLogger(__name__)


class NotionClient:
    """노션 연동 클라이언트"""
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv("NOTION_TOKEN")
        self.client = None
        
        if NOTION_AVAILABLE and self.token:
            self.client = Client(auth=self.token)
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.client is not None
    
    def list_databases(self) -> List[Dict]:
        """접근 가능한 데이터베이스 목록"""
        if not self.client:
            return []
        
        try:
            response = self.client.search()
            return [
                {
                    "id": db["id"],
                    "title": db["title"][0]["plain_text"] if db.get("title") and len(db["title"]) > 0 else "Untitled",
                    "url": db.get("url", "")
                }
                for db in response.get("results", [])
                if db.get("object") == "database"
            ]
        except Exception as e:
            logger.exception("Error listing databases: %s", e)
            return []
    
    def get_database(self, database_id: str) -> Optional[Dict]:
        """데이터베이스 정보 조회"""
        if not self.client:
            return None
        
        try:
            return self.client.databases.retrieve(database_id=database_id)
        except Exception as e:
            logger.exception("Error getting database: %s", e)
            return None
    
    def query_database(self, database_id: str, filter_obj: Dict = None, sorts: List = None) -> List[Dict]:
        """데이터베이스 쿼리"""
        if not self.client:
            return []
        
        try:
            params = {"database_id": database_id}
            if filter_obj:
                params["filter"] = filter_obj
            if sorts:
                params["sorts"] = sorts
            
            response = self.client.databases.query(**params)
            return response.get("results", [])
        except Exception as e:
            logger.exception("Error querying database: %s", e)
            return []
    
    def create_page(self, database_id: str, properties: Dict, content: List[Dict] = None) -> Optional[Dict]:
        """페이지(행) 생성"""
        if not self.client:
            return None
        
        try:
            params = {
                "parent": {"database_id": database_id},
                "properties": properties
            }
            if content:
                params["children"] = content
            
            return self.client.pages.create(**params)
        except Exception as e:
            logger.exception("Error creating page: %s", e)
            return None
    
    def update_page(self, page_id: str, properties: Dict) -> Optional[Dict]:
        """페이지 업데이트"""
        if not self.client:
            return None
        
        try:
            return self.client.pages.update(page_id=page_id, properties=properties)
        except Exception as e:
            logger.exception("Error updating page: %s", e)
            return None
    
    def get_page(self, page_id: str) -> Optional[Dict]:
        """페이지 조회"""
        if not self.client:
            return None
        
        try:
            return self.client.pages.retrieve(page_id=page_id)
        except Exception as e:
            logger.exception("Error getting page: %s", e)
            return None
    
    def append_block(self, block_id: str, children: List[Dict]) -> Optional[Dict]:
        """블록 추가"""
        if not self.client:
            return None
        
        try:
            return self.client.blocks.children.append(block_id=block_id, children=children)
        except Exception as e:
            logger.exception("Error appending block: %s", e)
            return None
    
    # ========== 헬퍼 메서드 ==========
    
    @staticmethod
    def make_title(text: str) -> Dict:
        """제목 속성 생성"""
        return {"title": [{"text": {"content": text}}]}
    
    @staticmethod
    def make_rich_text(text: str) -> Dict:
        """텍스트 속성 생성"""
        return {"rich_text": [{"text": {"content": text}}]}
    
    @staticmethod
    def make_number(value: int | float) -> Dict:
        """숫자 속성 생성"""
        return {"number": value}
    
    @staticmethod
    def make_select(option: str) -> Dict:
        """셀렉트 속성 생성"""
        return {"select": {"name": option}}
    
    @staticmethod
    def make_date(date: datetime, end_date: datetime = None) -> Dict:
        """날짜 속성 생성"""
        date_obj = {"start": date.isoformat()}
        if end_date:
            date_obj["end"] = end_date.isoformat()
        return {"date": date_obj}
    
    @staticmethod
    def make_checkbox(checked: bool) -> Dict:
        """체크박스 속성 생성"""
        return {"checkbox": checked}
    
    @staticmethod
    def make_paragraph(text: str) -> Dict:
        """문단 블록 생성"""
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            }
        }
    
    @staticmethod
    def make_heading(text: str, level: int = 2) -> Dict:
        """제목 블록 생성"""
        heading_type = f"heading_{level}"
        return {
            "object": "block",
            "type": heading_type,
            heading_type: {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            }
        }
    
    @staticmethod
    def make_bulleted_list(items: List[str]) -> List[Dict]:
        """불릿 리스트 생성"""
        return [
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": item}}]
                }
            }
            for item in items
        ]

    @staticmethod
    def make_to_do(text: str, checked: bool = False) -> Dict:
        """할 일 블록 생성"""
        return {
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "checked": checked,
            }
        }

    @staticmethod
    def make_divider() -> Dict:
        """구분선 블록 생성"""
        return {"object": "block", "type": "divider", "divider": {}}

    @staticmethod
    def make_callout(text: str) -> Dict:
        """콜아웃 블록 생성"""
        return {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
            }
        }

    # ========== DB 생성/관리 ==========

    def create_database(self, parent_page_id: str, title: str, properties: Dict) -> Optional[Dict]:
        """데이터베이스 생성"""
        if not self.client:
            return None
        try:
            return self.client.databases.create(
                parent={"page_id": parent_page_id},
                title=[{"text": {"content": title}}],
                properties=properties,
            )
        except Exception as e:
            logger.exception("Error creating database: %s", e)
            return None

    def archive_page(self, page_id: str) -> Optional[Dict]:
        """페이지 아카이브 (삭제 대용)"""
        if not self.client:
            return None
        try:
            return self.client.pages.update(page_id=page_id, archived=True)
        except Exception as e:
            logger.exception("Error archiving page: %s", e)
            return None

    def get_block_children(self, block_id: str, page_size: int = 50) -> List[Dict]:
        """블록의 자식 블록 조회"""
        if not self.client:
            return []
        try:
            resp = self.client.blocks.children.list(block_id=block_id, page_size=page_size)
            return resp.get("results", [])
        except Exception as e:
            logger.exception("Error getting block children: %s", e)
            return []

    def add_comment(self, page_id: str, text: str) -> Optional[Dict]:
        """페이지에 댓글 추가"""
        if not self.client:
            return None
        try:
            return self.client.comments.create(
                parent={"page_id": page_id},
                rich_text=[{"type": "text", "text": {"content": text}}],
            )
        except Exception as e:
            logger.exception("Error adding comment: %s", e)
            return None
