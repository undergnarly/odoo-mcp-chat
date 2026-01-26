"""API Key Management."""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import aiosqlite

logger = logging.getLogger(__name__)

KEY_PREFIX_LIVE = "sk_live_"
KEY_PREFIX_TEST = "sk_test_"


class APIKeyManager:
    """Manages API keys with hashing, expiration, and audit logging."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from src.ui.data_layer import get_database_path
            db_path = get_database_path()
        self.db_path = Path(db_path)

    async def init_db(self):
        """Initialize database tables."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    revoked_at TEXT,
                    created_by TEXT,
                    permissions TEXT DEFAULT 'full'
                );
                CREATE TABLE IF NOT EXISTS api_key_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    response_status INTEGER,
                    FOREIGN KEY (key_id) REFERENCES api_keys(id)
                );
                CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
                CREATE INDEX IF NOT EXISTS idx_api_key_usage_key_id ON api_key_usage(key_id);
            """)
            await db.commit()

    def _generate_key(self, test_mode: bool = False) -> str:
        prefix = KEY_PREFIX_TEST if test_mode else KEY_PREFIX_LIVE
        return f"{prefix}{secrets.token_urlsafe(24)}"

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def _get_prefix(self, key: str) -> str:
        return key[:12] + "..."

    async def create_key(
        self,
        name: str,
        created_by: str,
        permissions: str = "full",
        expires_in_days: Optional[int] = None,
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        key_id = str(uuid.uuid4())
        full_key = self._generate_key(test_mode)
        key_hash = self._hash_key(full_key)
        key_prefix = self._get_prefix(full_key)

        expires_at = None
        if expires_in_days is not None:
            expires_at = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO api_keys (id, name, key_hash, key_prefix, created_by, permissions, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (key_id, name, key_hash, key_prefix, created_by, permissions, expires_at)
            )
            await db.commit()

        return {
            "id": key_id,
            "name": name,
            "key": full_key,
            "key_prefix": key_prefix,
            "permissions": permissions,
            "expires_at": expires_at,
        }

    async def verify_key(self, key: str) -> Optional[Dict[str, Any]]:
        key_hash = self._hash_key(key)

        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT id, name, permissions, expires_at, revoked_at, created_by
                   FROM api_keys WHERE key_hash = ?""",
                (key_hash,)
            )
            row = await cursor.fetchone()

            if not row:
                return None
            if row["revoked_at"]:
                return None
            if row["expires_at"]:
                if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
                    return None

            return {
                "id": row["id"],
                "name": row["name"],
                "permissions": row["permissions"],
                "created_by": row["created_by"],
            }

    async def revoke_key(self, key_id: str) -> bool:
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                "UPDATE api_keys SET revoked_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), key_id)
            )
            await db.commit()
        return True

    async def list_keys(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT id, name, key_prefix, created_at, expires_at, revoked_at, created_by, permissions
                   FROM api_keys ORDER BY created_at DESC"""
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "key_prefix": row["key_prefix"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                    "revoked_at": row["revoked_at"],
                    "created_by": row["created_by"],
                    "permissions": row["permissions"],
                    "is_active": row["revoked_at"] is None,
                }
                for row in rows
            ]

    async def log_usage(self, key_id: str, endpoint: str, method: str,
                        ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                        response_status: Optional[int] = None):
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO api_key_usage (key_id, endpoint, method, ip_address, user_agent, response_status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key_id, endpoint, method, ip_address, user_agent, response_status)
            )
            await db.commit()

    async def get_key_usage(self, key_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT endpoint, method, ip_address, user_agent, timestamp, response_status
                   FROM api_key_usage WHERE key_id = ? ORDER BY timestamp DESC LIMIT ?""",
                (key_id, limit)
            )
            return [dict(row) for row in await cursor.fetchall()]


_manager: Optional[APIKeyManager] = None


async def get_api_key_manager() -> APIKeyManager:
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
        await _manager.init_db()
    return _manager
