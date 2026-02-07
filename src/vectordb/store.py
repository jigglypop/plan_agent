"""
벡터 DB (ChromaDB) 래퍼
게시글 데이터를 임베딩하여 시맨틱 검색 지원
OpenAI text-embedding-3-small 사용
"""
import os
import logging
import shutil
import threading
import time
from typing import List, Dict, Optional
from datetime import datetime

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction


logger = logging.getLogger(__name__)


def _is_missing_table_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "no such table" in msg or "no such table: collections" in msg


class VectorStore:
    """ChromaDB 기반 벡터 스토어 (OpenAI 임베딩)"""

    _repair_lock = threading.Lock()

    def __init__(self, persist_dir: str = "./data/chroma"):
        self.persist_dir = persist_dir
        self._last_error: Optional[str] = None
        self._repair_attempts = 0
        self._last_repair_at = 0.0
        self._index_lock = threading.Lock()
        self._index_state: Dict[str, object] = {
            "running": False,
            "kind": "",
            "total": 0,
            "done": 0,
            "started_at": "",
            "updated_at": "",
            "finished_at": "",
            "last_error": "",
        }

        api_key = os.getenv("OPENAI_API_KEY", "")
        self._ef = OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small",
        ) if api_key else None

        self._ef_arg = {"embedding_function": self._ef} if self._ef else {}

        self.client = self._create_client_with_repair()

        # 컬렉션 초기화
        self.events_collection = self.client.get_or_create_collection(
            name="events_oai",
            metadata={"description": "행사 데이터"},
            **self._ef_arg,
        )

        self.tasks_collection = self.client.get_or_create_collection(
            name="tasks_oai",
            metadata={"description": "태스크 데이터"},
            **self._ef_arg,
        )

        self.posts_collection = self.client.get_or_create_collection(
            name="posts_oai",
            metadata={"description": "게시글 데이터 (크롤링 + 첨부파일)"},
            **self._ef_arg,
        )

        # DB 스키마 손상(no such table 등) 대비: 가벼운 검증 후 필요 시 1회 복구
        self._verify_or_repair()

    def _set_index_state(
        self,
        *,
        running: bool,
        kind: str,
        total: int,
        done: int,
        started_at: str = "",
        updated_at: str = "",
        finished_at: str = "",
        last_error: str = "",
    ):
        with self._index_lock:
            state = self._index_state
            state["running"] = bool(running)
            state["kind"] = kind
            state["total"] = int(total)
            state["done"] = int(done)
            if started_at:
                state["started_at"] = started_at
            if updated_at:
                state["updated_at"] = updated_at
            if finished_at:
                state["finished_at"] = finished_at
            if last_error:
                state["last_error"] = last_error

    def get_index_state(self) -> Dict[str, object]:
        with self._index_lock:
            return dict(self._index_state)

    def get_index_status(self, expected_posts: int | None = None) -> Dict[str, object]:
        """색인 진행/정합성 요약."""
        stats = self.get_stats()
        indexed_posts = 0
        if isinstance(stats, dict):
            try:
                indexed_posts = int(stats.get("posts", 0))
            except Exception:
                indexed_posts = 0

        expected = int(expected_posts) if expected_posts is not None else None
        coverage_pct = None
        if expected and expected > 0:
            coverage_pct = round((indexed_posts / expected) * 100, 1)

        state = self.get_index_state()
        progress_pct = None
        try:
            total = int(state.get("total", 0) or 0)
            done = int(state.get("done", 0) or 0)
            if total > 0:
                progress_pct = round((done / total) * 100, 1)
        except Exception:
            progress_pct = None

        return {
            "expected_posts": expected,
            "indexed_posts": indexed_posts,
            "coverage_pct": coverage_pct,
            "indexing": state,
            "indexing_progress_pct": progress_pct,
            "vectordb": stats,
            "last_error": self._last_error,
        }

    def _create_client_with_repair(self) -> chromadb.PersistentClient:
        """PersistentClient 생성. 실패/손상 패턴이면 1회 reset 후 재시도."""
        try:
            return chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
        except ValueError as e:
            # 기존 코드 호환: tenant 초기화/스키마 문제로 ValueError 발생하는 케이스
            logger.warning("VectorDB init ValueError, resetting: %s", e)
            self._last_error = f"{e}"
            self._reset_persist_dir(reason="init_value_error")
            return chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )

    def _reset_persist_dir(self, reason: str = ""):
        """persist_dir를 초기화합니다 (인덱스는 재생성 대상)."""
        with self._repair_lock:
            try:
                shutil.rmtree(self.persist_dir, ignore_errors=True)
                os.makedirs(self.persist_dir, exist_ok=True)
                logger.warning("VectorDB persist dir reset (reason=%s)", reason)
            except Exception as e:
                self._last_error = str(e)
                logger.exception("VectorDB persist dir reset failed (reason=%s): %s", reason, e)

    def _verify_or_repair(self):
        """count() 등에서 스키마 손상 감지 시 reset."""
        try:
            _ = self.posts_collection.count()
        except Exception as e:
            self._last_error = str(e)
            if _is_missing_table_error(e):
                logger.error("VectorDB schema seems corrupted, resetting: %s", e)
                self.repair(reason="missing_table")
            else:
                # 그 외 오류는 상위로 올려서 원인 노출
                raise

    def repair(self, reason: str = "") -> bool:
        """ChromaDB persist_dir reset 후 컬렉션 재생성."""
        max_repairs = int(os.getenv("VDB_MAX_REPAIRS", "2"))
        min_interval = int(os.getenv("VDB_REPAIR_MIN_INTERVAL_SECONDS", "60"))
        now = time.time()

        if self._repair_attempts >= max_repairs:
            return False
        if self._last_repair_at and (now - self._last_repair_at) < min_interval:
            return False

        with self._repair_lock:
            now = time.time()
            if self._repair_attempts >= max_repairs:
                return False
            if self._last_repair_at and (now - self._last_repair_at) < min_interval:
                return False
            self._repair_attempts += 1
            self._last_repair_at = now

            try:
                shutil.rmtree(self.persist_dir, ignore_errors=True)
                os.makedirs(self.persist_dir, exist_ok=True)

                self.client = chromadb.PersistentClient(
                    path=self.persist_dir,
                    settings=Settings(anonymized_telemetry=False),
                )
                self.events_collection = self.client.get_or_create_collection(
                    name="events_oai",
                    metadata={"description": "행사 데이터"},
                    **self._ef_arg,
                )
                self.tasks_collection = self.client.get_or_create_collection(
                    name="tasks_oai",
                    metadata={"description": "태스크 데이터"},
                    **self._ef_arg,
                )
                self.posts_collection = self.client.get_or_create_collection(
                    name="posts_oai",
                    metadata={"description": "게시글 데이터 (크롤링 + 첨부파일)"},
                    **self._ef_arg,
                )
                logger.warning("VectorDB repaired (reason=%s)", reason)
                return True
            except Exception as e:
                self._last_error = str(e)
                logger.exception("VectorDB repair failed (reason=%s): %s", reason, e)
                return False
    
    # ========== 행사 ==========
    
    def add_event(self, event_id: str, title: str, content: str, metadata: Dict = None):
        """행사 추가"""
        doc = f"{title}\n{content}"
        meta = metadata or {}
        meta["type"] = "event"
        meta["created_at"] = datetime.now().isoformat()
        
        self.events_collection.upsert(
            ids=[event_id],
            documents=[doc],
            metadatas=[meta]
        )
    
    def add_events_batch(self, events: List[Dict]):
        """행사 일괄 추가"""
        if not events:
            return
        
        ids = []
        documents = []
        metadatas = []
        
        for e in events:
            ids.append(e["id"])
            documents.append(f"{e['title']}\n{e.get('description', '')}")
            metadatas.append({
                "title": e["title"],
                "category": e.get("category", ""),
                "status": e.get("status", ""),
                "date": e.get("date", ""),
                "location": e.get("location", ""),
                "manager": e.get("manager", ""),
                "type": "event"
            })
        
        self.events_collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info("행사 %d건 저장됨", len(events))
    
    def search_events(self, query: str, n_results: int = 5) -> List[Dict]:
        """행사 시맨틱 검색"""
        try:
            results = self.events_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results)
        except Exception as e:
            self._last_error = str(e)
            if _is_missing_table_error(e):
                self.repair(reason="search_events_missing_table")
            logger.exception("VectorDB search_events failed: %s", e)
            return []
    
    # ========== 태스크 ==========
    
    def add_task(self, task_id: str, title: str, content: str, metadata: Dict = None):
        """태스크 추가"""
        doc = f"{title}\n{content}"
        meta = metadata or {}
        meta["type"] = "task"
        
        self.tasks_collection.upsert(
            ids=[task_id],
            documents=[doc],
            metadatas=[meta]
        )
    
    def add_tasks_batch(self, tasks: List[Dict]):
        """태스크 일괄 추가"""
        if not tasks:
            return
        
        ids = []
        documents = []
        metadatas = []
        
        for t in tasks:
            ids.append(t["id"])
            documents.append(f"{t['title']}\n{t.get('description', '')}")
            metadatas.append({
                "title": t["title"],
                "status": t.get("status", ""),
                "assignee": t.get("assignee", ""),
                "event_id": t.get("event_id", ""),
                "type": "task"
            })
        
        self.tasks_collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info("태스크 %d건 저장됨", len(tasks))
    
    def search_tasks(self, query: str, n_results: int = 5) -> List[Dict]:
        """태스크 시맨틱 검색"""
        try:
            results = self.tasks_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results)
        except Exception as e:
            self._last_error = str(e)
            if _is_missing_table_error(e):
                self.repair(reason="search_tasks_missing_table")
            logger.exception("VectorDB search_tasks failed: %s", e)
            return []
    
    # ========== 게시글 ==========
    
    def add_post(self, post_id: str, title: str, content: str, metadata: Dict = None):
        """게시글 추가"""
        doc = f"{title}\n{content}"
        meta = metadata or {}
        meta["type"] = "post"
        
        self.posts_collection.upsert(
            ids=[post_id],
            documents=[doc],
            metadatas=[meta]
        )
    
    def add_posts_batch(self, posts: List[Dict], batch_size: int = 50):
        """게시글 일괄 추가 (첨부파일 내용 포함)"""
        if not posts:
            return

        started_at = datetime.now().isoformat()
        ids = []
        documents = []
        metadatas = []

        for p in posts:
            # 제목 2회 반복 (가중치) + 본문 + 파일명 + 파일 내용(제한)
            title = p["title"]
            content = p.get("content", "")
            file_content = p.get("file_content", "")
            file_names = ", ".join(f.get("name", "") for f in p.get("files", []) if f.get("name"))

            parts = [title, title]
            if content:
                parts.append(content[:2000])
            if file_names:
                parts.append(f"첨부파일: {file_names}")
            if file_content:
                parts.append(file_content[:3000])
            doc = "\n".join(parts)

            if len(doc) > 6000:
                doc = doc[:6000]

            ids.append(p["id"])
            documents.append(doc)
            metadatas.append({
                "title": p["title"],
                "author": p.get("author", ""),
                "date": p.get("date", ""),
                "url": p.get("url", ""),
                "has_files": "yes" if file_content else "no",
                "type": "post"
            })

        self._set_index_state(
            running=True,
            kind="posts",
            total=len(ids),
            done=0,
            started_at=started_at,
            updated_at=started_at,
            finished_at="",
            last_error="",
        )

        # 배치 단위로 upsert (API rate limit 대비)
        try:
            for i in range(0, len(ids), batch_size):
                end = min(i + batch_size, len(ids))
                self.posts_collection.upsert(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    metadatas=metadatas[i:end],
                )
                self._set_index_state(
                    running=True,
                    kind="posts",
                    total=len(ids),
                    done=end,
                    updated_at=datetime.now().isoformat(),
                )
        except Exception as e:
            self._last_error = str(e)
            self._set_index_state(
                running=False,
                kind="posts",
                total=len(ids),
                done=0,
                finished_at=datetime.now().isoformat(),
                last_error=self._last_error,
            )
            raise
        finally:
            self._set_index_state(
                running=False,
                kind="posts",
                total=len(ids),
                done=len(ids),
                finished_at=datetime.now().isoformat(),
            )

        with_files = sum(1 for p in posts if p.get("file_content"))
        logger.info("게시글 %d건 저장됨 (파일 내용 포함: %d건)", len(posts), with_files)
    
    def search_posts(self, query: str, n_results: int = 5) -> List[Dict]:
        """게시글 시맨틱 검색"""
        try:
            results = self.posts_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results)
        except Exception as e:
            self._last_error = str(e)
            if _is_missing_table_error(e):
                self.repair(reason="search_posts_missing_table")
            logger.exception("VectorDB search_posts failed: %s", e)
            return []
    
    # ========== 통합 검색 ==========
    
    def search_all(self, query: str, n_results: int = 5) -> Dict[str, List[Dict]]:
        """전체 검색"""
        return {
            "events": self.search_events(query, n_results),
            "tasks": self.search_tasks(query, n_results),
            "posts": self.search_posts(query, n_results)
        }
    
    # ========== 유틸리티 ==========
    
    def _format_results(self, results: Dict) -> List[Dict]:
        """검색 결과 포맷"""
        formatted = []
        
        if not results or not results.get("ids"):
            return formatted
        
        ids = results["ids"][0]
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []
        
        for i, id_ in enumerate(ids):
            formatted.append({
                "id": id_,
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "distance": distances[i] if i < len(distances) else 0
            })
        
        return formatted
    
    def get_stats(self) -> Dict[str, int | str]:
        """저장된 데이터 통계"""
        try:
            return {
                "events": self.events_collection.count(),
                "tasks": self.tasks_collection.count(),
                "posts": self.posts_collection.count()
            }
        except Exception as e:
            self._last_error = str(e)
            if _is_missing_table_error(e) and self.repair(reason="get_stats_missing_table"):
                return {"events": 0, "tasks": 0, "posts": 0, "status": "repaired"}
            return {"events": 0, "tasks": 0, "posts": 0, "status": "error", "error": self._last_error}
    
    def clear_all(self):
        """모든 데이터 삭제"""
        for name in ["events_oai", "tasks_oai", "posts_oai"]:
            try:
                self.client.delete_collection(name)
            except Exception:
                pass

        ef_arg = {"embedding_function": self._ef} if self._ef else {}
        self.events_collection = self.client.get_or_create_collection(name="events_oai", **ef_arg)
        self.tasks_collection = self.client.get_or_create_collection(name="tasks_oai", **ef_arg)
        self.posts_collection = self.client.get_or_create_collection(name="posts_oai", **ef_arg)


def init_vector_store_from_json(json_path: str = None):
    """crawled.json에서 벡터 스토어 초기화 (첨부파일 파싱 포함)"""
    from src.data import load_posts
    from src.data.parser import enrich_posts_with_files

    store = VectorStore()
    posts = load_posts(json_path)

    force = os.getenv("VDB_FORCE_INDEX", "0").strip() in ("1", "true", "True")
    stats = store.get_stats()
    current_posts = int(stats.get("posts", 0)) if isinstance(stats, dict) else 0
    target_posts = sum(1 for p in posts if p.get("id") is not None)

    if not force and target_posts > 0 and current_posts >= target_posts and stats.get("status") != "error":
        logger.warning("VectorDB indexing skipped (already indexed: %d/%d)", current_posts, target_posts)
        return store

    logger.warning("첨부파일 파싱 시작... (posts=%d)", len(posts))
    posts = enrich_posts_with_files(posts)

    store.add_posts_batch([
        {
            "id": p["id"],
            "title": p["title"],
            "content": p.get("content", ""),
            "file_content": p.get("file_content", ""),
            "author": p.get("author", ""),
            "date": p.get("date", ""),
            "url": p.get("url", ""),
        }
        for p in posts
    ])

    logger.warning("벡터 스토어 초기화 완료: %s", store.get_stats())
    return store


if __name__ == "__main__":
    from src import configure_logging
    configure_logging()
    init_vector_store_from_json()
