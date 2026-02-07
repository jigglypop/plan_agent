"""
Plan Agent - AI 기반 기획위원회 PM/통계 시스템

프로젝트 공통 유틸리티(예: 로깅 설정)만 포함합니다.
무거운 의존성 import는 피합니다.
"""

from __future__ import annotations

import logging
import os


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
