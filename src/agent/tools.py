"""
에이전트 도구 정의
각 도구는 @tool 데코레이터로 LangGraph에 자동 등록
"""
import os
from typing import Dict, List, Optional
from datetime import datetime
from langchain_core.tools import tool

from src import format_post_item, format_search_item
from src.data_loader import get_post_by_id, filter_posts, get_post_stats, list_files
from src.vectordb import VectorStore
from src.notion import NotionClient

# 모듈 레벨 의존성 (Agent 초기화 시 주입)
_posts: List[Dict] = []
_posts_by_id: Dict[str, Dict] = {}
_store: Optional[VectorStore] = None
_notion: Optional[NotionClient] = None

def inject_deps(posts: List[Dict], store: VectorStore, notion: NotionClient):
    """Agent가 초기화할 때 호출하여 도구에 의존성 주입"""
    global _posts, _posts_by_id, _store, _notion
    _posts = posts
    _posts_by_id = {
        str(p.get("id")): p
        for p in posts
        if p.get("id") is not None
    }
    _store = store
    _notion = notion


def _get_post(post_id: str) -> Optional[Dict]:
    """게시글 조회 (id 캐시 우선, 없으면 선형 탐색 fallback)."""
    post = _posts_by_id.get(str(post_id))
    if post is not None:
        return post
    return get_post_by_id(_posts, post_id)


def get_all_tools() -> list:
    """등록된 전체 도구 리스트 반환"""
    return get_search_tools() + get_notion_tools()


def get_search_tools() -> list:
    """검색/분석 도구 그룹"""
    return [search_posts, get_post, list_posts, get_stats, list_attached_files, analyze_file, fetch_webpage, web_search]


def get_notion_tools() -> list:
    """노션 도구 그룹"""
    return [
        create_notion_event, create_notion_page, query_notion,
        query_notion_database, list_notion_databases,
        create_notion_checklist, create_notion_board,
        update_notion_item, update_notion_page_content,
        archive_notion_page, read_notion_page,
        add_notion_comment,
    ]


# ========== 읽기 도구 ==========

@tool
def search_posts(query: str, n_results: int = 10) -> list[dict]:
    """기획위원회 게시판 게시글을 의미 기반으로 검색합니다. 과거 행사, 회의록, 예산, 장소 견적 등을 찾을 때 사용합니다.

    Args:
        query: 검색어 (자연어, 예: '2024 겨울행사 예산', '글램핑 장소')
        n_results: 결과 수 (기본 10, 최대 20)
    """
    n = min(n_results, 10)
    results = _store.search_posts(query, n)
    return [
        format_search_item(r, _get_post(r["id"]), include_files=True, preview_len=300)
        for r in results
    ]


@tool
def get_post(post_id: str) -> dict:
    """특정 게시글의 전체 내용을 조회합니다. search_posts에서 찾은 게시글의 상세 내용이 필요할 때 사용합니다.

    Args:
        post_id: 게시글 ID
    """
    post = _get_post(post_id)
    if not post:
        return {"error": "게시글을 찾을 수 없습니다."}
    content = post.get("content", "")
    result = {
        "id": post["id"],
        "title": post["title"],
        "author": post.get("author", ""),
        "date": post.get("date", ""),
        "content": content[:4000] + ("...(truncated)" if len(content) > 4000 else ""),
        "files": [f.get("name", "") for f in post.get("files", [])],
        "url": post.get("url", ""),
    }
    file_content = post.get("file_content", "")
    if file_content:
        result["file_content"] = file_content[:4000] + ("...(truncated)" if len(file_content) > 4000 else "")
    return result


@tool
def list_posts(year: int = None, author: str = None,
               keyword: str = None, limit: int = 20) -> list[dict]:
    """게시글 목록을 필터링합니다. 특정 연도, 작성자, 키워드로 필터링 가능합니다.

    Args:
        year: 연도 필터 (예: 2025)
        author: 작성자 필터
        keyword: 제목/본문 키워드 필터
        limit: 최대 결과 수 (기본 20)
    """
    filtered = filter_posts(_posts, year=year, author=author, keyword=keyword, limit=limit)
    return [format_post_item(p) for p in filtered]


@tool
def get_stats() -> dict:
    """게시글 전체 통계를 조회합니다. 연도별 게시글 수, 작성자별 통계, 첨부파일 수 등."""
    return get_post_stats(_posts)


@tool
def list_attached_files(keyword: str = None, year: int = None) -> list[dict]:
    """첨부파일 목록을 조회합니다. 예산안, 결산안, 회의록, 기획서 등 파일을 검색합니다.

    Args:
        keyword: 파일명 키워드 (예: '예산', '결산', '회의록')
        year: 연도 필터
    """
    return list_files(_posts, keyword=keyword, year=year)[:30]


# ========== 쓰기 도구 ==========

def _resolve_notion_target(target: str) -> tuple:
    """target에 따라 (page_id, label) 반환"""
    if target == "public":
        page_id = os.getenv("NOTION_PUBLIC_PAGE_ID", "")
        return page_id, "공개용"
    page_id = os.getenv("NOTION_ADMIN_PAGE_ID", "")
    return page_id, "운영진용"


@tool
def create_notion_event(title: str, date: str,
                        location: str = "", budget: int = 0,
                        category: str = "기타", manager: str = "",
                        description: str = "",
                        target: str = "admin") -> dict:
    """노션 데이터베이스에 새 행사를 생성합니다. target으로 공개용/운영진용 경로를 선택합니다.

    Args:
        title: 행사 제목
        date: 행사 날짜 (YYYY-MM-DD)
        location: 장소
        budget: 예산 (원)
        category: 카테고리 (신년회/봄/여름/가을/겨울/기타)
        manager: 담당자
        description: 행사 설명
        target: 공개용(public) 또는 운영진용(admin). 기본값 admin
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다. NOTION_TOKEN을 확인하세요."}

    db_id = os.getenv("NOTION_DATABASE_ID")
    if not db_id:
        return {"error": "NOTION_DATABASE_ID가 설정되지 않았습니다."}

    properties = {
        "행사명": _notion.make_title(title),
        "카테고리": _notion.make_select(category),
        "상태": _notion.make_select("기획중"),
    }

    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        properties["날짜"] = _notion.make_date(dt)
    except ValueError:
        pass

    if location:
        properties["장소"] = _notion.make_rich_text(location)
    if budget:
        properties["예산"] = _notion.make_number(budget)
    if manager:
        properties["담당자"] = _notion.make_rich_text(manager)

    content_blocks = []
    if description:
        content_blocks.append(_notion.make_paragraph(description))

    result = _notion.create_page(db_id, properties, content_blocks or None)
    if not result:
        return {"error": "노션 페이지 생성에 실패했습니다."}

    page_id, label = _resolve_notion_target(target)
    if page_id:
        link_text = f"[{label}] {title} ({date})"
        _notion.append_block(page_id, [_notion.make_paragraph(link_text)])

    return {
        "status": "created",
        "target": label,
        "page_id": result.get("id", ""),
        "url": result.get("url", ""),
        "title": title,
        "date": date,
    }


@tool
def create_notion_page(title: str, content: str,
                       target: str = "admin",
                       parent_page_id: str = "") -> dict:
    """노션에 자유 형식 페이지를 생성합니다. 회의록, 공지, 메모 등을 공개용/운영진용으로 나눠 작성합니다. parent_page_id가 있으면 해당 페이지 하위에 생성합니다.

    Args:
        title: 페이지 제목
        content: 페이지 본문 내용
        target: 공개용(public) 또는 운영진용(admin). 기본값 admin
        parent_page_id: 부모 페이지 ID. 지정하면 해당 페이지 하위에 생성
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    if parent_page_id:
        page_id = parent_page_id
        label = "지정 위치"
    else:
        page_id, label = _resolve_notion_target(target)
    if not page_id:
        return {"error": f"{label} 페이지 ID가 설정되지 않았습니다."}

    blocks = []
    for i in range(0, len(content), 2000):
        blocks.append(_notion.make_paragraph(content[i:i + 2000]))

    try:
        result = _notion.client.pages.create(
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


@tool
def query_notion(target: str = "admin") -> dict:
    """노션 페이지의 하위 콘텐츠를 조회합니다. 공개용/운영진용 페이지에 어떤 내용이 있는지 확인합니다.

    Args:
        target: 공개용(public) 또는 운영진용(admin). 기본값 admin
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    page_id, label = _resolve_notion_target(target)
    if not page_id:
        return {"error": f"{label} 페이지 ID가 설정되지 않았습니다."}

    try:
        response = _notion.client.blocks.children.list(block_id=page_id, page_size=50)
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


# ========== 파일 분석 도구 ==========

@tool
def analyze_file(post_id: str, query: str = "") -> dict:
    """게시글의 첨부파일을 AI로 분석합니다. 예산안, 견적서, 결산표 등 Excel/PDF/PPT/DOCX 파일의 내용을 해석합니다.

    Args:
        post_id: 게시글 ID (search_posts 결과에서 확인)
        query: 분석 질문 (예: '총 예산 금액', '항목별 비용 비교', '주요 내용 요약'). 비워두면 전체 요약.
    """
    post = _get_post(post_id)
    if not post:
        return {"error": "게시글을 찾을 수 없습니다."}

    file_content = post.get("file_content", "")
    if not file_content:
        return {"error": "이 게시글에 파싱 가능한 첨부파일이 없습니다.", "files": [f.get("name") for f in post.get("files", [])]}

    prompt = query or "파일 내용을 분석하여 핵심 내용을 요약하세요. 숫자/금액이 있으면 정리하세요."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # 파일 내용이 길면 잘라서 전송
        content_chunk = file_content[:12000]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 문서 분석 전문가입니다. 게시글 첨부파일의 텍스트를 분석합니다. 한국어로 답변. 이모지 금지."},
                {"role": "user", "content": f"게시글: {post['title']} ({post.get('date', '')})\n\n[첨부파일 내용]\n{content_chunk}\n\n[분석 요청]\n{prompt}"},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        analysis = response.choices[0].message.content or ""
        file_names = [f.get("name", "") for f in post.get("files", [])]
        return {
            "post_id": post_id,
            "post_title": post["title"],
            "post_date": post.get("date", ""),
            "files": file_names,
            "analysis": analysis,
        }
    except Exception as e:
        return {"error": f"파일 분석 실패: {e}"}


# ========== 웹 도구 ==========

@tool
def fetch_webpage(url: str) -> dict:
    """웹 페이지의 텍스트 내용을 가져옵니다. 행사 장소 정보, 가격, 공지사항 등 외부 웹사이트 내용을 확인할 때 사용합니다.

    Args:
        url: 가져올 웹 페이지 URL (https://...)
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PlanAgent/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = soup.get_text(separator="\n", strip=True)
        # 빈 줄 정리 + 길이 제한
        lines = [l for l in text.split("\n") if l.strip()]
        content = "\n".join(lines)[:6000]

        return {"url": url, "title": title, "content": content}
    except Exception as e:
        return {"error": f"웹 페이지 가져오기 실패: {e}", "url": url}


@tool
def web_search(query: str, limit: int = 5) -> list[dict]:
    """인터넷에서 정보를 검색합니다. 내부 데이터에 없는 외부 정보(장소, 가격, 최신 뉴스 등)를 찾을 때 사용합니다.

    Args:
        query: 검색어 (예: '서울 글램핑 장소 추천', '리조트 단체 할인')
        limit: 결과 수 (기본 5, 최대 10)
    """
    api_key = os.getenv("BRAVE_API_KEY", "")
    n = min(limit, 10)

    # Brave Search API
    if api_key:
        import requests
        try:
            resp = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": api_key},
                params={"q": query, "count": n},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", [])[:n]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", "")[:300],
                })
            return results
        except Exception as e:
            return [{"error": f"검색 실패: {e}"}]

    # fallback: DuckDuckGo (API key 불필요)
    import requests
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; PlanAgent/1.0)"},
            timeout=10,
        )
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result")[:n]:
            title_el = r.select_one(".result__title a")
            snippet_el = r.select_one(".result__snippet")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": title_el.get("href", ""),
                    "description": snippet_el.get_text(strip=True)[:300] if snippet_el else "",
                })
        return results if results else [{"message": "검색 결과가 없습니다.", "query": query}]
    except Exception as e:
        return [{"error": f"검색 실패: {e}"}]


# ========== 노션 DB 읽기 도구 ==========

def _extract_notion_property(prop: dict) -> str:
    """노션 속성 값을 문자열로 변환"""
    ptype = prop.get("type", "")
    if ptype == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if ptype == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if ptype == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "multi_select":
        return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
    if ptype == "date":
        d = prop.get("date")
        if d:
            s = d.get("start", "")
            e = d.get("end", "")
            return f"{s} ~ {e}" if e else s
        return ""
    if ptype == "checkbox":
        return "O" if prop.get("checkbox") else "X"
    if ptype == "status":
        st = prop.get("status")
        return st.get("name", "") if st else ""
    if ptype == "url":
        return prop.get("url", "") or ""
    return ""


@tool
def list_notion_databases() -> list:
    """노션에서 접근 가능한 데이터베이스 목록을 조회합니다. database_id를 확인한 뒤 query_notion_database에서 사용합니다."""
    if not _notion or not _notion.is_connected():
        return [{"error": "노션이 연결되지 않았습니다."}]
    return _notion.list_databases()


@tool
def query_notion_database(database_id: str,
                          status_filter: str = "",
                          category_filter: str = "",
                          limit: int = 20) -> dict:
    """노션 데이터베이스를 쿼리합니다. 행사 DB, 태스크 DB 등에서 항목을 필터링하여 조회합니다.

    Args:
        database_id: 데이터베이스 ID (list_notion_databases로 확인)
        status_filter: 상태 필터 (예: '기획중', '확정', '완료'). 비우면 전체.
        category_filter: 카테고리 필터 (예: '여름', '겨울'). 비우면 전체.
        limit: 최대 결과 수 (기본 20)
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    # 필터 구성
    conditions = []
    if status_filter:
        conditions.append({"property": "상태", "select": {"equals": status_filter}})
    if category_filter:
        conditions.append({"property": "카테고리", "select": {"equals": category_filter}})

    filter_obj = None
    if len(conditions) == 1:
        filter_obj = conditions[0]
    elif len(conditions) > 1:
        filter_obj = {"and": conditions}

    try:
        results = _notion.query_database(database_id, filter_obj=filter_obj)
        items = []
        for page in results[:limit]:
            row = {"id": page.get("id", ""), "url": page.get("url", "")}
            for name, prop in page.get("properties", {}).items():
                val = _extract_notion_property(prop)
                if val:
                    row[name] = val
            items.append(row)
        return {"database_id": database_id, "count": len(items), "items": items}
    except Exception as e:
        return {"error": f"노션 DB 쿼리 실패: {e}"}


@tool
def create_notion_board(title: str,
                        columns: list[str] = None,
                        target: str = "admin",
                        parent_page_id: str = "") -> dict:
    """노션에 칸반보드(데이터베이스)를 생성합니다. 상태 컬럼으로 Board view를 만들 수 있습니다.

    Args:
        title: 보드 제목 (예: '2025 여름행사 준비')
        columns: 상태 컬럼 목록. 기본값 ['대기', '진행중', '완료']
        target: 공개용(public) 또는 운영진용(admin). 기본값 admin
        parent_page_id: 부모 페이지 ID. 비우면 target에 따라 결정
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    if parent_page_id:
        page_id = parent_page_id
        label = "지정 위치"
    else:
        page_id, label = _resolve_notion_target(target)
    if not page_id:
        return {"error": f"{label} 페이지 ID가 설정되지 않았습니다."}

    cols = columns or ["대기", "진행중", "완료"]
    properties = {
        "이름": {"title": {}},
        "상태": {"select": {"options": [{"name": c} for c in cols]}},
        "담당자": {"rich_text": {}},
        "기한": {"date": {}},
        "우선순위": {"select": {"options": [
            {"name": "높음"}, {"name": "보통"}, {"name": "낮음"},
        ]}},
        "메모": {"rich_text": {}},
    }

    try:
        result = _notion.create_database(page_id, title, properties)
        if not result:
            return {"error": "칸반보드 생성 실패"}
        return {
            "status": "created",
            "target": label,
            "title": title,
            "columns": cols,
            "database_id": result.get("id", ""),
            "url": result.get("url", ""),
        }
    except Exception as e:
        return {"error": f"칸반보드 생성 실패: {e}"}


@tool
def update_notion_item(page_id: str,
                       status: str = "",
                       assignee: str = "",
                       priority: str = "",
                       memo: str = "",
                       due_date: str = "") -> dict:
    """노션 데이터베이스 항목의 속성을 변경합니다. 칸반보드에서 상태 이동, 담당자 변경 등에 사용합니다.

    Args:
        page_id: 변경할 항목의 페이지 ID (query_notion_database 결과에서 확인)
        status: 상태 변경 (예: '진행중', '완료'). 비우면 변경 안 함.
        assignee: 담당자 변경. 비우면 변경 안 함.
        priority: 우선순위 변경 (높음/보통/낮음). 비우면 변경 안 함.
        memo: 메모 변경. 비우면 변경 안 함.
        due_date: 기한 변경 (YYYY-MM-DD). 비우면 변경 안 함.
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    props = {}
    if status:
        props["상태"] = _notion.make_select(status)
    if assignee:
        props["담당자"] = _notion.make_rich_text(assignee)
    if priority:
        props["우선순위"] = _notion.make_select(priority)
    if memo:
        props["메모"] = _notion.make_rich_text(memo)
    if due_date:
        try:
            dt = datetime.strptime(due_date, "%Y-%m-%d")
            props["기한"] = _notion.make_date(dt)
        except ValueError:
            return {"error": f"날짜 형식 오류: {due_date} (YYYY-MM-DD 필요)"}

    if not props:
        return {"error": "변경할 속성이 없습니다."}

    try:
        result = _notion.update_page(page_id, props)
        if not result:
            return {"error": "항목 업데이트 실패"}
        return {
            "status": "updated",
            "page_id": page_id,
            "updated_fields": list(props.keys()),
            "url": result.get("url", ""),
        }
    except Exception as e:
        return {"error": f"항목 업데이트 실패: {e}"}


@tool
def update_notion_page_content(page_id: str, content: str) -> dict:
    """기존 노션 페이지에 텍스트 블록을 추가합니다. 회의 내용 추가, 메모 덧붙이기 등에 사용합니다.

    Args:
        page_id: 페이지 ID
        content: 추가할 텍스트 내용
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    blocks = []
    for i in range(0, len(content), 2000):
        blocks.append(_notion.make_paragraph(content[i:i + 2000]))

    try:
        result = _notion.append_block(page_id, blocks)
        if not result:
            return {"error": "블록 추가 실패"}
        return {"status": "appended", "page_id": page_id, "blocks_added": len(blocks)}
    except Exception as e:
        return {"error": f"블록 추가 실패: {e}"}


@tool
def archive_notion_page(page_id: str) -> dict:
    """노션 페이지를 아카이브(삭제)합니다. 실수로 만든 페이지를 정리할 때 사용합니다.

    Args:
        page_id: 삭제할 페이지 ID
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    try:
        result = _notion.archive_page(page_id)
        if not result:
            return {"error": "아카이브 실패"}
        return {"status": "archived", "page_id": page_id}
    except Exception as e:
        return {"error": f"아카이브 실패: {e}"}


@tool
def read_notion_page(page_id: str) -> dict:
    """특정 노션 페이지의 제목과 본문 블록을 읽어옵니다.

    Args:
        page_id: 페이지 ID
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    try:
        page = _notion.get_page(page_id)
        if not page:
            return {"error": "페이지를 찾을 수 없습니다."}

        # 제목 추출
        title = ""
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                break

        # 블록 내용 추출
        blocks = _notion.get_block_children(page_id)
        content_parts = []
        for block in blocks[:30]:
            btype = block.get("type", "")
            rich = block.get(btype, {}).get("rich_text", [])
            text = "".join(r.get("plain_text", "") for r in rich)
            if text.strip():
                content_parts.append({"type": btype, "text": text.strip()})

        return {
            "page_id": page_id,
            "title": title,
            "url": page.get("url", ""),
            "blocks": content_parts,
        }
    except Exception as e:
        return {"error": f"페이지 읽기 실패: {e}"}


@tool
def add_notion_comment(page_id: str, text: str) -> dict:
    """노션 페이지에 댓글을 추가합니다. 피드백, 질문, 메모 등을 남길 때 사용합니다.

    Args:
        page_id: 페이지 ID
        text: 댓글 내용
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    try:
        result = _notion.add_comment(page_id, text)
        if not result:
            return {"error": "댓글 추가 실패"}
        return {"status": "commented", "page_id": page_id, "comment_id": result.get("id", "")}
    except Exception as e:
        return {"error": f"댓글 추가 실패: {e}"}


@tool
def create_notion_checklist(title: str, items: list[str],
                            target: str = "admin",
                            parent_page_id: str = "") -> dict:
    """노션에 체크리스트(할일 목록) 페이지를 생성합니다. 회의 후속 조치, 행사 준비 체크리스트 등에 사용합니다.

    Args:
        title: 페이지 제목 (예: '2025 여름행사 준비 체크리스트')
        items: 할 일 항목 리스트 (예: ['장소 계약서 확인', '예산안 작성', '참가자 모집 공지'])
        target: 공개용(public) 또는 운영진용(admin). 기본값 admin
        parent_page_id: 부모 페이지 ID. 비우면 target에 따라 결정
    """
    if not _notion or not _notion.is_connected():
        return {"error": "노션이 연결되지 않았습니다."}

    if parent_page_id:
        page_id = parent_page_id
        label = "지정 위치"
    else:
        page_id, label = _resolve_notion_target(target)
    if not page_id:
        return {"error": f"{label} 페이지 ID가 설정되지 않았습니다."}

    # to_do 블록 생성
    blocks = []
    for item in items:
        blocks.append({
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": item}}],
                "checked": False,
            }
        })

    try:
        result = _notion.client.pages.create(
            parent={"page_id": page_id},
            properties={"title": [{"text": {"content": title}}]},
            children=blocks,
        )
        return {
            "status": "created",
            "target": label,
            "title": title,
            "items_count": len(items),
            "page_id": result.get("id", ""),
            "url": result.get("url", ""),
        }
    except Exception as e:
        return {"error": f"체크리스트 생성 실패: {e}"}
