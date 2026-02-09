"""
Plan Agent - AI 기반 기획위원회 PM/통계 시스템

프로젝트 공통 유틸리티(로깅, 데이터 포맷터)만 포함합니다.
무거운 의존성 import는 피합니다.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional


def configure_logging():
    """표준 로깅 초기화 (이미 설정돼 있으면 유지)."""
    root = logging.getLogger()
    if root.handlers:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


# ========== 게시글 공용 포맷터 ==========


def format_post_item(post: Dict, include_views: bool = False) -> Dict:
    """게시글을 요약 dict로 변환. tools/server/mcp 공용."""
    item = {
        "id": post["id"],
        "title": post["title"],
        "author": post.get("author", ""),
        "date": post.get("date", ""),
        "files_count": len(post.get("files", [])),
    }
    if include_views:
        item["views"] = post.get("views", 0)
    return item


def format_search_item(
    result: Dict,
    post: Optional[Dict] = None,
    *,
    include_relevance: bool = False,
    include_files: bool = False,
    preview_len: int = 500,
) -> Dict:
    """벡터 검색 결과를 dict로 변환. tools/server/mcp 공용."""
    meta = result.get("metadata", {})
    item = {
        "id": result["id"],
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "date": meta.get("date", ""),
        "content_preview": (post.get("content", "")[:preview_len] if post else ""),
    }
    if include_files:
        item["files"] = [f.get("name", "") for f in (post or {}).get("files", [])]
    if include_relevance:
        item["relevance"] = round(1 - result.get("distance", 0), 3)
    return item


def prepare_vdb_payload(posts: List[Dict]) -> List[Dict]:
    """게시글을 VectorStore.add_posts_batch() 형식으로 변환. core/mcp/store 공용."""
    return [
        {
            "id": str(p.get("id", "")),
            "title": p.get("title", ""),
            "content": p.get("content", ""),
            "file_content": p.get("file_content", ""),
            "files": p.get("files", []),
            "author": p.get("author", ""),
            "date": p.get("date", ""),
            "url": p.get("url", ""),
        }
        for p in posts
        if p.get("id") is not None
    ]
