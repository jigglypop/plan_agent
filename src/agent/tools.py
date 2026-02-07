"""
에이전트 도구 정의 + 실행
각 도구는 단일 책임 원칙에 따라 하나의 메서드로 구현
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.data import load_posts, get_post_by_id, filter_posts, get_post_stats, list_files
from src.vectordb import VectorStore
from src.notion import NotionClient


TOOLS = [
    # === 읽기 도구 ===
    {
        "type": "function",
        "function": {
            "name": "search_posts",
            "description": "기획위원회 게시판 게시글을 의미 기반으로 검색합니다. 과거 행사, 회의록, 예산, 장소 견적 등을 찾을 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어 (자연어, 예: '2024 겨울행사 예산', '글램핑 장소')"},
                    "n_results": {"type": "integer", "description": "결과 수 (기본 10, 최대 20)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_post",
            "description": "특정 게시글의 전체 내용을 조회합니다. search_posts에서 찾은 게시글의 상세 내용이 필요할 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "게시글 ID"}
                },
                "required": ["post_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_posts",
            "description": "게시글 목록을 필터링합니다. 특정 연도, 작성자, 키워드로 필터링 가능합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "연도 필터 (예: 2025)"},
                    "author": {"type": "string", "description": "작성자 필터"},
                    "keyword": {"type": "string", "description": "제목/본문 키워드 필터"},
                    "limit": {"type": "integer", "description": "최대 결과 수 (기본 20)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "게시글 전체 통계를 조회합니다. 연도별 게시글 수, 작성자별 통계, 첨부파일 수 등.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_attached_files",
            "description": "첨부파일 목록을 조회합니다. 예산안, 결산안, 회의록, 기획서 등 파일을 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "파일명 키워드 (예: '예산', '결산', '회의록')"},
                    "year": {"type": "integer", "description": "연도 필터"}
                },
                "required": []
            }
        }
    },
    # === 쓰기 도구 ===
    {
        "type": "function",
        "function": {
            "name": "create_notion_event",
            "description": "노션 데이터베이스에 새 행사를 생성합니다. 행사명, 날짜, 장소, 예산, 카테고리, 담당자를 지정할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "행사 제목"},
                    "date": {"type": "string", "description": "행사 날짜 (YYYY-MM-DD)"},
                    "location": {"type": "string", "description": "장소"},
                    "budget": {"type": "integer", "description": "예산 (원)"},
                    "category": {"type": "string", "description": "카테고리 (신년회/봄/여름/가을/겨울/기타)"},
                    "manager": {"type": "string", "description": "담당자"},
                    "description": {"type": "string", "description": "행사 설명"}
                },
                "required": ["title", "date"]
            }
        }
    },
]


class ToolExecutor:
    """도구 실행기"""

    def __init__(self, posts: List[Dict], vector_store: VectorStore, notion: NotionClient):
        self.posts = posts
        self.store = vector_store
        self.notion = notion

    def run(self, name: str, args: Dict) -> Any:
        """도구 이름으로 디스패치"""
        method = getattr(self, f"_tool_{name}", None)
        if not method:
            return {"error": f"알 수 없는 도구: {name}"}
        return method(**args)

    # === 읽기 도구 ===

    def _tool_search_posts(self, query: str, n_results: int = 10) -> List[Dict]:
        n = min(n_results, 20)
        results = self.store.search_posts(query, n)
        output = []
        for r in results:
            post = get_post_by_id(self.posts, r["id"])
            meta = r.get("metadata", {})
            output.append({
                "id": r["id"],
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "date": meta.get("date", ""),
                "content_preview": (post.get("content", "")[:500] if post else ""),
                "files": [f.get("name", "") for f in (post or {}).get("files", [])],
            })
        return output

    def _tool_get_post(self, post_id: str) -> Dict:
        post = get_post_by_id(self.posts, post_id)
        if not post:
            return {"error": "게시글을 찾을 수 없습니다."}
        result = {
            "id": post["id"],
            "title": post["title"],
            "author": post.get("author", ""),
            "date": post.get("date", ""),
            "content": post.get("content", ""),
            "files": post.get("files", []),
            "url": post.get("url", ""),
        }
        # 첨부파일 파싱 내용 포함
        file_content = post.get("file_content", "")
        if file_content:
            result["file_content"] = file_content[:8000]
        return result

    def _tool_list_posts(self, year: int = None, author: str = None,
                         keyword: str = None, limit: int = 20) -> List[Dict]:
        filtered = filter_posts(self.posts, year=year, author=author, keyword=keyword, limit=limit)
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

    def _tool_get_stats(self) -> Dict:
        return get_post_stats(self.posts)

    def _tool_list_attached_files(self, keyword: str = None, year: int = None) -> List[Dict]:
        return list_files(self.posts, keyword=keyword, year=year)[:30]

    # === 쓰기 도구 ===

    def _tool_create_notion_event(self, title: str, date: str,
                                  location: str = "", budget: int = 0,
                                  category: str = "기타", manager: str = "",
                                  description: str = "") -> Dict:
        if not self.notion.is_connected():
            return {"error": "노션이 연결되지 않았습니다. NOTION_TOKEN을 확인하세요."}

        db_id = os.getenv("NOTION_DATABASE_ID")
        if not db_id:
            return {"error": "NOTION_DATABASE_ID가 설정되지 않았습니다."}

        properties = {
            "행사명": self.notion.make_title(title),
            "카테고리": self.notion.make_select(category),
            "상태": self.notion.make_select("기획중"),
        }

        # 날짜 파싱
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            properties["날짜"] = self.notion.make_date(dt)
        except ValueError:
            pass

        if location:
            properties["장소"] = self.notion.make_rich_text(location)
        if budget:
            properties["예산"] = self.notion.make_number(budget)
        if manager:
            properties["담당자"] = self.notion.make_rich_text(manager)

        # 본문 블록
        content_blocks = []
        if description:
            content_blocks.append(self.notion.make_paragraph(description))

        result = self.notion.create_page(db_id, properties, content_blocks or None)
        if not result:
            return {"error": "노션 페이지 생성에 실패했습니다."}

        return {
            "status": "created",
            "page_id": result.get("id", ""),
            "url": result.get("url", ""),
            "title": title,
            "date": date,
        }
