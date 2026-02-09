"""
벡터 DB (FAISS) 래퍼
부서별 인덱스 분리 + OpenAI text-embedding-3-small 임베딩
"""
import os
import json
import logging
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    faiss = None
    FAISS_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False


logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
DEFAULT_DEPT = "planning"


class _DeptIndex:
    """부서 하나의 FAISS 인덱스 + 메타데이터"""

    def __init__(self, dept: str, base_dir: str):
        self.dept = dept
        self.dir = Path(base_dir) / dept
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "index.faiss"
        self.meta_path = self.dir / "meta.json"
        self.index: Optional[object] = None
        self.metas: List[Dict] = []
        self._load()

    def _load(self):
        if not FAISS_AVAILABLE:
            self.index = None
            self.metas = []
            return
        if self.index_path.exists() and self.meta_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    self.metas = json.load(f)
                logger.info("FAISS index loaded: dept=%s, count=%d", self.dept, self.index.ntotal)
            except Exception as e:
                logger.warning("FAISS index load failed (dept=%s): %s, rebuilding", self.dept, e)
                self.index = faiss.IndexFlatIP(EMBED_DIM)
                self.metas = []
        else:
            self.index = faiss.IndexFlatIP(EMBED_DIM)
            self.metas = []

    def save(self):
        if not FAISS_AVAILABLE or self.index is None:
            return
        try:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(self.metas, f, ensure_ascii=False)
        except Exception as e:
            logger.exception("FAISS index save failed (dept=%s): %s", self.dept, e)

    def count(self) -> int:
        if self.index is None:
            return 0
        return self.index.ntotal

    def clear(self):
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatIP(EMBED_DIM)
        self.metas = []
        self.save()

    def upsert(self, ids: List[str], embeddings: np.ndarray, metas: List[Dict]):
        """기존 ID가 있으면 교체, 없으면 추가"""
        if self.index is None:
            return

        existing_ids = {m["id"]: i for i, m in enumerate(self.metas)}
        keep_mask = np.ones(len(self.metas), dtype=bool)
        for doc_id in ids:
            if doc_id in existing_ids:
                keep_mask[existing_ids[doc_id]] = False

        if not keep_mask.all():
            keep_indices = np.where(keep_mask)[0]
            if len(keep_indices) > 0:
                old_vecs = faiss.rev_swig_ptr(self.index.get_xb(), self.index.ntotal * EMBED_DIM)
                old_vecs = np.array(old_vecs).reshape(-1, EMBED_DIM)
                kept_vecs = old_vecs[keep_indices]
                kept_metas = [self.metas[i] for i in keep_indices]
            else:
                kept_vecs = np.empty((0, EMBED_DIM), dtype=np.float32)
                kept_metas = []

            new_index = faiss.IndexFlatIP(EMBED_DIM)
            if len(kept_vecs) > 0:
                new_index.add(kept_vecs.astype(np.float32))
            self.index = new_index
            self.metas = kept_metas

        self.index.add(embeddings.astype(np.float32))
        self.metas.extend(metas)

    def search(self, query_vec: np.ndarray, n_results: int = 5) -> List[Dict]:
        if self.index is None or self.index.ntotal == 0:
            return []
        k = min(n_results, self.index.ntotal)
        scores, indices = self.index.search(query_vec.reshape(1, -1).astype(np.float32), k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metas):
                continue
            meta = self.metas[idx]
            results.append({
                "id": meta.get("id", ""),
                "metadata": meta,
                "score": float(score),
                "distance": float(1 - score),
            })
        return results


class VectorStore:
    """FAISS 기반 부서별 벡터 스토어"""

    def __init__(self, persist_dir: str = "./data/vectordb"):
        self.persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._last_error: Optional[str] = None
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

        self._openai = None
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key and OPENAI_AVAILABLE:
            self._openai = OpenAI(api_key=api_key)

        self._depts: Dict[str, _DeptIndex] = {}
        self._ensure_dept(DEFAULT_DEPT)

    def _ensure_dept(self, dept: str) -> _DeptIndex:
        if dept not in self._depts:
            self._depts[dept] = _DeptIndex(dept, self.persist_dir)
        return self._depts[dept]

    def list_depts(self) -> List[str]:
        base = Path(self.persist_dir)
        depts = set(self._depts.keys())
        if base.exists():
            for d in base.iterdir():
                if d.is_dir() and (d / "index.faiss").exists():
                    depts.add(d.name)
        return sorted(depts)

    # ========== 임베딩 ==========

    def _embed(self, texts: List[str]) -> Optional[np.ndarray]:
        if not self._openai:
            self._last_error = "OpenAI client not available"
            return None
        try:
            resp = self._openai.embeddings.create(model=EMBED_MODEL, input=texts)
            vecs = [d.embedding for d in resp.data]
            arr = np.array(vecs, dtype=np.float32)
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1
            return arr / norms
        except Exception as e:
            self._last_error = str(e)
            logger.exception("Embedding failed: %s", e)
            return None

    def _embed_single(self, text: str) -> Optional[np.ndarray]:
        result = self._embed([text])
        return result[0:1] if result is not None else None

    # ========== 인덱스 상태 ==========

    def _set_index_state(self, **kwargs):
        with self._index_lock:
            for k, v in kwargs.items():
                if k in self._index_state and v is not None:
                    self._index_state[k] = v

    def get_index_state(self) -> Dict[str, object]:
        with self._index_lock:
            return dict(self._index_state)

    def get_index_status(self, expected_posts: int | None = None) -> Dict[str, object]:
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

    # ========== 행사 ==========

    def add_event(self, event_id: str, title: str, content: str, metadata: Dict = None, dept: str = DEFAULT_DEPT):
        doc = f"{title}\n{content}"
        vec = self._embed_single(doc)
        if vec is None:
            return
        meta = metadata or {}
        meta.update({"id": event_id, "type": "event", "title": title, "created_at": datetime.now().isoformat()})
        di = self._ensure_dept(dept)
        di.upsert([event_id], vec, [meta])
        di.save()

    def add_events_batch(self, events: List[Dict], dept: str = DEFAULT_DEPT):
        if not events:
            return
        docs = [f"{e['title']}\n{e.get('description', '')}" for e in events]
        vecs = self._embed(docs)
        if vecs is None:
            return
        ids = [e["id"] for e in events]
        metas = [{
            "id": e["id"], "title": e["title"],
            "category": e.get("category", ""), "status": e.get("status", ""),
            "date": e.get("date", ""), "location": e.get("location", ""),
            "manager": e.get("manager", ""), "type": "event",
        } for e in events]
        di = self._ensure_dept(dept)
        di.upsert(ids, vecs, metas)
        di.save()
        logger.info("행사 %d건 저장됨 (dept=%s)", len(events), dept)

    def search_events(self, query: str, n_results: int = 5, dept: str = DEFAULT_DEPT) -> List[Dict]:
        vec = self._embed_single(query)
        if vec is None:
            return []
        di = self._ensure_dept(dept)
        return di.search(vec, n_results)

    # ========== 태스크 ==========

    def add_task(self, task_id: str, title: str, content: str, metadata: Dict = None, dept: str = DEFAULT_DEPT):
        doc = f"{title}\n{content}"
        vec = self._embed_single(doc)
        if vec is None:
            return
        meta = metadata or {}
        meta.update({"id": task_id, "type": "task", "title": title})
        di = self._ensure_dept(dept)
        di.upsert([task_id], vec, [meta])
        di.save()

    def add_tasks_batch(self, tasks: List[Dict], dept: str = DEFAULT_DEPT):
        if not tasks:
            return
        docs = [f"{t['title']}\n{t.get('description', '')}" for t in tasks]
        vecs = self._embed(docs)
        if vecs is None:
            return
        ids = [t["id"] for t in tasks]
        metas = [{
            "id": t["id"], "title": t["title"],
            "status": t.get("status", ""), "assignee": t.get("assignee", ""),
            "event_id": t.get("event_id", ""), "type": "task",
        } for t in tasks]
        di = self._ensure_dept(dept)
        di.upsert(ids, vecs, metas)
        di.save()
        logger.info("태스크 %d건 저장됨 (dept=%s)", len(tasks), dept)

    def search_tasks(self, query: str, n_results: int = 5, dept: str = DEFAULT_DEPT) -> List[Dict]:
        vec = self._embed_single(query)
        if vec is None:
            return []
        di = self._ensure_dept(dept)
        return di.search(vec, n_results)

    # ========== 게시글 ==========

    def add_post(self, post_id: str, title: str, content: str, metadata: Dict = None, dept: str = DEFAULT_DEPT):
        doc = f"{title}\n{content}"
        vec = self._embed_single(doc)
        if vec is None:
            return
        meta = metadata or {}
        meta.update({"id": post_id, "type": "post", "title": title})
        di = self._ensure_dept(dept)
        di.upsert([post_id], vec, [meta])
        di.save()

    def add_posts_batch(self, posts: List[Dict], batch_size: int = 50, dept: str = DEFAULT_DEPT):
        if not posts:
            return

        started_at = datetime.now().isoformat()
        ids = []
        documents = []
        metas = []

        for p in posts:
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
            metas.append({
                "id": p["id"], "title": p["title"],
                "author": p.get("author", ""), "date": p.get("date", ""),
                "url": p.get("url", ""),
                "has_files": "yes" if file_content else "no",
                "type": "post",
            })

        self._set_index_state(
            running=True, kind="posts", total=len(ids), done=0,
            started_at=started_at, updated_at=started_at,
            finished_at="", last_error="",
        )

        di = self._ensure_dept(dept)
        try:
            for i in range(0, len(ids), batch_size):
                end = min(i + batch_size, len(ids))
                batch_docs = documents[i:end]
                vecs = self._embed(batch_docs)
                if vecs is None:
                    raise RuntimeError("Embedding failed for batch")
                di.upsert(ids[i:end], vecs, metas[i:end])
                self._set_index_state(
                    running=True, kind="posts", total=len(ids), done=end,
                    updated_at=datetime.now().isoformat(),
                )
            di.save()
        except Exception as e:
            self._last_error = str(e)
            self._set_index_state(
                running=False, kind="posts", total=len(ids), done=0,
                finished_at=datetime.now().isoformat(), last_error=str(e),
            )
            raise
        finally:
            self._set_index_state(
                running=False, kind="posts", total=len(ids), done=len(ids),
                finished_at=datetime.now().isoformat(),
            )

        with_files = sum(1 for p in posts if p.get("file_content"))
        logger.info("게시글 %d건 저장됨 (파일 포함: %d건, dept=%s)", len(posts), with_files, dept)

    def search_posts(self, query: str, n_results: int = 5, dept: str = DEFAULT_DEPT) -> List[Dict]:
        vec = self._embed_single(query)
        if vec is None:
            return []
        di = self._ensure_dept(dept)
        return di.search(vec, n_results)

    # ========== 통합 검색 ==========

    def search_all(self, query: str, n_results: int = 5, dept: str = DEFAULT_DEPT) -> Dict[str, List[Dict]]:
        return {
            "events": self.search_events(query, n_results, dept),
            "tasks": self.search_tasks(query, n_results, dept),
            "posts": self.search_posts(query, n_results, dept),
        }

    def search_all_depts(self, query: str, n_results: int = 5) -> Dict[str, List[Dict]]:
        """전 부서 통합 검색 (관리자용)"""
        vec = self._embed_single(query)
        if vec is None:
            return {}
        results = {}
        for dept_name in self.list_depts():
            di = self._ensure_dept(dept_name)
            results[dept_name] = di.search(vec, n_results)
        return results

    # ========== 유틸리티 ==========

    def get_stats(self, dept: str = None) -> Dict[str, int | str]:
        """저장된 데이터 통계. dept 지정 시 해당 부서만, 미지정 시 기본 부서."""
        target = dept or DEFAULT_DEPT
        di = self._ensure_dept(target)
        total = di.count()
        events = sum(1 for m in di.metas if m.get("type") == "event")
        tasks = sum(1 for m in di.metas if m.get("type") == "task")
        posts = sum(1 for m in di.metas if m.get("type") == "post")
        return {"events": events, "tasks": tasks, "posts": posts, "total": total, "dept": target}

    def get_all_stats(self) -> Dict[str, Dict]:
        """전 부서 통계"""
        return {dept: self.get_stats(dept) for dept in self.list_depts()}

    def clear_all(self, dept: str = None):
        """데이터 삭제. dept 지정 시 해당 부서만, 미지정 시 전체."""
        if dept:
            di = self._ensure_dept(dept)
            di.clear()
        else:
            for d in self.list_depts():
                self._ensure_dept(d).clear()


def init_vector_store_from_json(json_path: str = None, dept: str = DEFAULT_DEPT):
    """crawled.json에서 벡터 스토어 초기화"""
    from src import prepare_vdb_payload
    from src.data import load_posts
    from src.data.parser import enrich_posts_with_files

    store = VectorStore()
    try:
        posts = load_posts(json_path)
    except Exception as e:
        logger.exception("데이터 로드 실패: %s", e)
        return store

    force = os.getenv("VDB_FORCE_INDEX", "0").strip() in ("1", "true", "True")
    stats = store.get_stats(dept)
    current_posts = int(stats.get("posts", 0))
    target_posts = sum(1 for p in posts if p.get("id") is not None)

    if not force and target_posts > 0 and current_posts >= target_posts:
        logger.warning("VectorDB indexing skipped (already indexed: %d/%d, dept=%s)", current_posts, target_posts, dept)
        return store

    logger.warning("첨부파일 파싱 시작... (posts=%d, dept=%s)", len(posts), dept)
    try:
        posts = enrich_posts_with_files(posts)
    except Exception as e:
        logger.exception("첨부파일 파싱 실패: %s", e)

    store.add_posts_batch(prepare_vdb_payload(posts), dept=dept)

    logger.warning("벡터 스토어 초기화 완료 (dept=%s): %s", dept, store.get_stats(dept))
    return store


if __name__ == "__main__":
    from src import configure_logging
    configure_logging()
    init_vector_store_from_json()
