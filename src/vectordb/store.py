"""
벡터 DB (ChromaDB) 래퍼
게시글 데이터를 임베딩하여 시맨틱 검색 지원
OpenAI text-embedding-3-small 사용
"""
import os
from typing import List, Dict
from datetime import datetime

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction


class VectorStore:
    """ChromaDB 기반 벡터 스토어 (OpenAI 임베딩)"""

    def __init__(self, persist_dir: str = "./data/chroma"):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        api_key = os.getenv("OPENAI_API_KEY", "")
        self._ef = OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small",
        ) if api_key else None

        ef_arg = {"embedding_function": self._ef} if self._ef else {}

        # 컬렉션 초기화
        self.events_collection = self.client.get_or_create_collection(
            name="events_oai",
            metadata={"description": "행사 데이터"},
            **ef_arg,
        )

        self.tasks_collection = self.client.get_or_create_collection(
            name="tasks_oai",
            metadata={"description": "태스크 데이터"},
            **ef_arg,
        )

        self.posts_collection = self.client.get_or_create_collection(
            name="posts_oai",
            metadata={"description": "게시글 데이터 (크롤링 + 첨부파일)"},
            **ef_arg,
        )
    
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
        
        print(f"행사 {len(events)}건 저장됨")
    
    def search_events(self, query: str, n_results: int = 5) -> List[Dict]:
        """행사 시맨틱 검색"""
        results = self.events_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
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
        
        print(f"태스크 {len(tasks)}건 저장됨")
    
    def search_tasks(self, query: str, n_results: int = 5) -> List[Dict]:
        """태스크 시맨틱 검색"""
        results = self.tasks_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
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

        # 배치 단위로 upsert (API rate limit 대비)
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self.posts_collection.upsert(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )

        with_files = sum(1 for p in posts if p.get("file_content"))
        print(f"게시글 {len(posts)}건 저장됨 (파일 내용 포함: {with_files}건)")
    
    def search_posts(self, query: str, n_results: int = 5) -> List[Dict]:
        """게시글 시맨틱 검색"""
        results = self.posts_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
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
    
    def get_stats(self) -> Dict[str, int]:
        """저장된 데이터 통계"""
        return {
            "events": self.events_collection.count(),
            "tasks": self.tasks_collection.count(),
            "posts": self.posts_collection.count()
        }
    
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

    print("첨부파일 파싱 시작...")
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

    print(f"벡터 스토어 초기화 완료: {store.get_stats()}")
    return store


if __name__ == "__main__":
    store = init_vector_store_from_json()

    print("\n=== 검색 테스트 ===")
    results = store.search_posts("겨울행사 예산")
    for r in results:
        print(f"- {r['metadata'].get('title', 'N/A')} (거리: {r['distance']:.3f})")
