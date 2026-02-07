"""
에이전트 대화 기억
SQLite 기반 세션별 대화 이력 영속 저장
"""
import sqlite3
from pathlib import Path
from typing import List, Dict

DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.db"


class Memory:

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session
                ON messages(session_id, id)
            """)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save(self, session_id: str, role: str, content: str):
        """메시지 저장 (user, assistant만)"""
        if role not in ("user", "assistant") or not content:
            return
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )

    def load(self, session_id: str, limit: int = 20) -> List[Dict]:
        """최근 대화 로드 (재시작 후 컨텍스트 복원용)"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def clear(self, session_id: str):
        """세션 대화 삭제"""
        with self._conn() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """활성 세션 목록"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT session_id, COUNT(*) as msg_count, MAX(created_at) as last_at "
                "FROM messages GROUP BY session_id ORDER BY last_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"session_id": r[0], "message_count": r[1], "last_active": r[2]}
            for r in rows
        ]
