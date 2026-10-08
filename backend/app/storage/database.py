import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..config import settings

logger = logging.getLogger(__name__)

class MemoryDatabase:
    """Manages SQLite persistence for long-term user profile facts and tracked entities."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or settings.SQLITE_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,       -- e.g. 'watchlist', 'preference', 'background', 'constraint'
                    entity_key TEXT NOT NULL,     -- e.g. 'NVDA', 'risk_profile', 'response_format'
                    fact_content TEXT NOT NULL,   -- e.g. 'User actively monitors NVDA and TSM'
                    importance_score REAL DEFAULT 0.8, -- 0.0 to 1.0
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, entity_key)
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_facts_user 
                ON user_facts(user_id);
            """)
            conn.commit()
            logger.info("Initialized Memory SQLite database schema at %s", self.db_path)

    def upsert_fact(self, user_id: str, category: str, entity_key: str, 
                    fact_content: str, importance_score: float = 0.8, 
                    metadata: Optional[Dict[str, Any]] = None) -> int:
        now = datetime.utcnow().isoformat()
        meta_str = json.dumps(metadata or {})
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_facts (user_id, category, entity_key, fact_content, importance_score, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, entity_key) DO UPDATE SET
                    category = excluded.category,
                    fact_content = excluded.fact_content,
                    importance_score = excluded.importance_score,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at;
            """, (user_id, category, entity_key, fact_content, importance_score, meta_str, now, now))
            conn.commit()
            return cursor.lastrowid

    def get_facts_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, category, entity_key, fact_content, importance_score, metadata, created_at, updated_at
                FROM user_facts
                WHERE user_id = ?
                ORDER BY importance_score DESC, updated_at DESC;
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_fact(self, fact_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_facts WHERE id = ?", (fact_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all_facts(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, category, entity_key, fact_content, importance_score, metadata, created_at, updated_at
                FROM user_facts
                ORDER BY updated_at DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

db = MemoryDatabase()
