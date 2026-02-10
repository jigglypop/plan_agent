"""
데이터 로더
crawled.json / council.json 에서 게시글 로드
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_posts(path: str = None) -> List[Dict]:
    """기획위원회 게시판 게시글 로드 (crawled + council 합본)"""
    posts = []

    crawled_path = Path(path) if path else DATA_DIR / "crawled.json"
    if crawled_path.exists():
        with open(crawled_path, "r", encoding="utf-8") as f:
            posts.extend(json.load(f))

    council_path = DATA_DIR / "council.json"
    if council_path.exists():
        with open(council_path, "r", encoding="utf-8") as f:
            council = json.load(f)
            existing_ids = {str(p.get("id")) for p in posts}
            for c in council:
                if str(c.get("id")) not in existing_ids:
                    posts.append(c)

    return posts


def load_council(path: str = None) -> List[Dict]:
    """이사회 게시글 로드"""
    if path is None:
        path = DATA_DIR / "council.json"
    if not Path(path).exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_post_by_id(posts: List[Dict], post_id: str) -> Optional[Dict]:
    """ID로 게시글 조회"""
    for p in posts:
        if str(p.get("id")) == str(post_id):
            return p
    return None


def filter_posts(
    posts: List[Dict],
    year: int = None,
    author: str = None,
    keyword: str = None,
    limit: int = 0,
) -> List[Dict]:
    """게시글 필터링"""
    result = posts

    if year:
        result = [
            p for p in result
            if _extract_year(p.get("date", "")) == year
        ]

    if author:
        result = [
            p for p in result
            if author in p.get("author", "")
        ]

    if keyword:
        kw = keyword.lower()
        result = [
            p for p in result
            if kw in p.get("title", "").lower()
            or kw in p.get("content", "").lower()
        ]

    return result[:limit] if limit > 0 else result


def get_post_stats(posts: List[Dict]) -> Dict:
    """게시글 통계"""
    by_year = defaultdict(int)
    by_author = defaultdict(int)
    file_count = 0

    for p in posts:
        y = _extract_year(p.get("date", ""))
        if y:
            by_year[y] += 1

        author = p.get("author", "").strip()
        if author:
            by_author[author] += 1

        file_count += len(p.get("files", []))

    return {
        "total_posts": len(posts),
        "total_files": file_count,
        "by_year": dict(sorted(by_year.items())),
        "by_author": dict(sorted(by_author.items(), key=lambda x: x[1], reverse=True)),
        "year_range": f"{min(by_year.keys()) if by_year else '?'} ~ {max(by_year.keys()) if by_year else '?'}",
    }


def list_files(posts: List[Dict], keyword: str = None, year: int = None) -> List[Dict]:
    """첨부파일 목록"""
    files = []
    for p in posts:
        if year and _extract_year(p.get("date", "")) != year:
            continue

        for f in p.get("files", []):
            name = f.get("name", "")
            if keyword and keyword.lower() not in name.lower():
                continue
            files.append({
                "post_id": p.get("id"),
                "post_title": p.get("title", ""),
                "file_name": name,
                "file_size": f.get("size", ""),
                "local_path": f.get("local_path", ""),
                "date": p.get("date", ""),
            })
    return files


def _extract_year(date_str: str) -> Optional[int]:
    """날짜 문자열에서 연도 추출"""
    if not date_str:
        return None
    m = re.search(r'(20\d{2})', date_str)
    if m:
        return int(m.group(1))
    return None
