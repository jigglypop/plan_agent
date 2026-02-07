"""
Agent 패키지 엔트리포인트.

주의:
- __init__ 에서 무거운 의존성(chromadb 등)을 즉시 import 하지 않도록 lazy import로 구성합니다.
- `from src.agent import Agent` 사용성은 유지합니다.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Agent as Agent


def __getattr__(name: str):
    if name == "Agent":
        return import_module("src.agent.core").Agent
    raise AttributeError(name)


__all__ = ["Agent"]
