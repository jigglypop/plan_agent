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
            "description": "노션 데이터베이스에 새 행사를 생성합니다. target으로 공개용/운영진용 경로를 선택합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "행사 제목"},
                    "date": {"type": "string", "description": "행사 날짜 (YYYY-MM-DD)"},
                    "location": {"type": "string", "description": "장소"},
                    "budget": {"type": "integer", "description": "예산 (원)"},
                    "category": {"type": "string", "description": "카테고리 (신년회/봄/여름/가을/겨울/기타)"},
                    "manager": {"type": "string", "description": "담당자"},
                    "description": {"type": "string", "description": "행사 설명"},
                    "target": {"type": "string", "enum": ["public", "admin"], "description": "공개용(public) 또는 운영진용(admin). 기본값 admin"}
                },
                "required": ["title", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_notion_page",
            "description": "노션에 자유 형식 페이지를 생성합니다. 회의록, 공지, 메모 등을 공개용/운영진용으로 나눠 작성합니다. parent_page_id가 있으면 해당 페이지 하위에 생성합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "페이지 제목"},
                    "content": {"type": "string", "description": "페이지 본문 내용"},
                    "target": {"type": "string", "enum": ["public", "admin"], "description": "공개용(public) 또는 운영진용(admin). 기본값 admin"},
                    "parent_page_id": {"type": "string", "description": "부모 페이지 ID. 지정하면 해당 페이지 하위에 생성"}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_notion",
            "description": "노션 페이지의 하위 콘텐츠를 조회합니다. 공개용/운영진용 페이지에 어떤 내용이 있는지 확인합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "enum": ["public", "admin"], "description": "공개용(public) 또는 운영진용(admin). 기본값 admin"}
                },
                "required": []
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

    def _resolve_notion_target(self, target: str) -> tuple:
        """target에 따라 (page_id, label) 반환"""
        if target == "public":
            page_id = os.getenv("NOTION_PUBLIC_PAGE_ID", "")
            return page_id, "공개용"
        page_id = os.getenv("NOTION_ADMIN_PAGE_ID", "")
        return page_id, "운영진용"

    def _tool_create_notion_event(self, title: str, date: str,
                                  location: str = "", budget: int = 0,
                                  category: str = "기타", manager: str = "",
                                  description: str = "",
                                  target: str = "admin") -> Dict:
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

        content_blocks = []
        if description:
            content_blocks.append(self.notion.make_paragraph(description))

        result = self.notion.create_page(db_id, properties, content_blocks or None)
        if not result:
            return {"error": "노션 페이지 생성에 실패했습니다."}

        # 대상 페이지에 링크 블록 추가
        page_id, label = self._resolve_notion_target(target)
        if page_id:
            link_text = f"[{label}] {title} ({date})"
            self.notion.append_block(page_id, [self.notion.make_paragraph(link_text)])

        return {
            "status": "created",
            "target": label,
            "page_id": result.get("id", ""),
            "url": result.get("url", ""),
            "title": title,
            "date": date,
        }

    def _tool_create_notion_page(self, title: str, content: str,
                                 target: str = "admin",
                                 parent_page_id: str = "") -> Dict:
        if not self.notion.is_connected():
            return {"error": "노션이 연결되지 않았습니다."}

        if parent_page_id:
            page_id = parent_page_id
            label = "지정 위치"
        else:
            page_id, label = self._resolve_notion_target(target)
        if not page_id:
            return {"error": f"{label} 페이지 ID가 설정되지 않았습니다."}

        # 본문을 2000자 단위로 분할 (Notion API 블록 제한)
        blocks = []
        for i in range(0, len(content), 2000):
            blocks.append(self.notion.make_paragraph(content[i:i + 2000]))

        try:
            result = self.notion.client.pages.create(
                parent={"page_id": page_id},
                properties={"title": [{"text": {"content": title}}]},
                children=blocks,
            )
            return {
                "status": "created",
                "target": label,
                "title": title,
                "page_id": result.get("id", ""),
                "url": result.get("url", ""),
            }
        except Exception as e:
            return {"error": f"노션 하위 페이지 생성 실패: {e}"}

    def _tool_query_notion(self, target: str = "admin") -> Dict:
        if not self.notion.is_connected():
            return {"error": "노션이 연결되지 않았습니다."}

        page_id, label = self._resolve_notion_target(target)
        if not page_id:
            return {"error": f"{label} 페이지 ID가 설정되지 않았습니다."}

        try:
            response = self.notion.client.blocks.children.list(block_id=page_id, page_size=50)
            items = []
            for block in response.get("results", []):
                btype = block.get("type", "")
                rich = block.get(btype, {}).get("rich_text", [])
                text = "".join(r.get("plain_text", "") for r in rich)
                if text.strip():
                    items.append({"type": btype, "text": text.strip()})
            return {"target": label, "page_id": page_id, "items": items}
        except Exception as e:
            return {"error": f"노션 조회 실패: {e}"}
