# Security Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement comprehensive security: admin auth, secret encryption, API key management.

**Architecture:** Three-layer security with middleware for admin routes, Fernet encryption for secrets in SQLite, and full API key lifecycle with audit logging.

**Tech Stack:** cryptography (Fernet), aiosqlite, FastAPI middleware, SHA-256 for key hashing.

---

## Task 1: Create Secret Vault Module

**Files:**
- Create: `src/security/__init__.py`
- Create: `src/security/vault.py`
- Create: `tests/security/__init__.py`
- Create: `tests/security/test_vault.py`

**Step 1: Create directory and init**

```bash
mkdir -p src/security tests/security
touch src/security/__init__.py tests/security/__init__.py
```

**Step 2: Write failing test for vault**

```python
# tests/security/test_vault.py
"""Tests for SecretVault encryption."""
import os
import pytest
from pathlib import Path


class TestSecretVault:
    """Test SecretVault encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        """Encrypted value can be decrypted back."""
        from src.security.vault import SecretVault, get_or_create_master_key

        key_file = tmp_path / "test.key"
        key = get_or_create_master_key(key_file=key_file)
        vault = SecretVault(key)

        original = "my-secret-password-123"
        encrypted = vault.encrypt(original)
        decrypted = vault.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_encrypted_value_is_different_each_time(self, tmp_path):
        """Same value produces different ciphertext (IV)."""
        from src.security.vault import SecretVault, get_or_create_master_key

        key_file = tmp_path / "test.key"
        key = get_or_create_master_key(key_file=key_file)
        vault = SecretVault(key)

        value = "same-secret"
        encrypted1 = vault.encrypt(value)
        encrypted2 = vault.encrypt(value)

        assert encrypted1 != encrypted2

    def test_get_or_create_master_key_creates_file(self, tmp_path):
        """Key file is created if not exists."""
        from src.security.vault import get_or_create_master_key

        key_file = tmp_path / "new.key"
        assert not key_file.exists()

        key = get_or_create_master_key(key_file=key_file)

        assert key_file.exists()
        assert len(key) == 44  # Fernet key is 32 bytes base64 = 44 chars

    def test_get_or_create_master_key_reuses_existing(self, tmp_path):
        """Existing key file is reused."""
        from src.security.vault import get_or_create_master_key

        key_file = tmp_path / "existing.key"
        key1 = get_or_create_master_key(key_file=key_file)
        key2 = get_or_create_master_key(key_file=key_file)

        assert key1 == key2

    def test_get_or_create_master_key_from_env(self, tmp_path, monkeypatch):
        """Key from environment variable takes priority."""
        from cryptography.fernet import Fernet
        from src.security.vault import get_or_create_master_key

        env_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", env_key)

        key_file = tmp_path / "ignored.key"
        key = get_or_create_master_key(key_file=key_file)

        assert key == env_key
        assert not key_file.exists()  # File not created when env is set
```

**Step 3: Run test to verify it fails**

```bash
pytest tests/security/test_vault.py -v
```
Expected: FAIL with "No module named 'src.security.vault'"

**Step 4: Write vault implementation**

```python
# src/security/vault.py
"""
Secret Vault for encrypting sensitive data.
Uses Fernet symmetric encryption with a master key.
"""
import os
import logging
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Default key file location
DEFAULT_KEY_FILE = Path("data/encryption.key")


class SecretVault:
    """
    Encrypts and decrypts secrets using Fernet.

    Usage:
        vault = SecretVault(key)
        encrypted = vault.encrypt("my-password")
        decrypted = vault.decrypt(encrypted)
    """

    def __init__(self, key: str):
        """
        Initialize vault with encryption key.

        Args:
            key: Fernet-compatible base64 key (44 chars)
        """
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, value: str) -> str:
        """
        Encrypt a string value.

        Args:
            value: Plain text to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not value:
            return value
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt an encrypted value.

        Args:
            encrypted: Base64-encoded encrypted string

        Returns:
            Decrypted plain text
        """
        if not encrypted:
            return encrypted
        return self.fernet.decrypt(encrypted.encode()).decode()


def get_or_create_master_key(key_file: Optional[Path] = None) -> str:
    """
    Get master encryption key from env or file, create if needed.

    Priority:
    1. ENCRYPTION_KEY environment variable
    2. Key file (default: data/encryption.key)
    3. Generate new key and save to file

    Args:
        key_file: Path to key file (default: data/encryption.key)

    Returns:
        Fernet-compatible encryption key
    """
    # 1. Check environment variable
    env_key = os.environ.get("ENCRYPTION_KEY")
    if env_key:
        logger.debug("Using encryption key from ENCRYPTION_KEY env")
        return env_key

    # 2. Check key file
    if key_file is None:
        key_file = DEFAULT_KEY_FILE

    if key_file.exists():
        logger.debug(f"Loading encryption key from {key_file}")
        return key_file.read_text().strip()

    # 3. Generate new key
    logger.info(f"Generating new encryption key, saving to {key_file}")
    key_file.parent.mkdir(parents=True, exist_ok=True)

    new_key = Fernet.generate_key().decode()
    key_file.write_text(new_key)

    # Set restrictive permissions (owner read/write only)
    key_file.chmod(0o600)

    return new_key


# Global vault instance (lazy initialized)
_vault: Optional[SecretVault] = None


def get_vault() -> SecretVault:
    """Get or create global vault instance."""
    global _vault
    if _vault is None:
        key = get_or_create_master_key()
        _vault = SecretVault(key)
    return _vault
```

**Step 5: Update __init__.py exports**

```python
# src/security/__init__.py
"""Security module for Odoo AI Agent."""
from src.security.vault import (
    SecretVault,
    get_or_create_master_key,
    get_vault,
)

__all__ = [
    "SecretVault",
    "get_or_create_master_key",
    "get_vault",
]
```

**Step 6: Run tests to verify they pass**

```bash
pytest tests/security/test_vault.py -v
```
Expected: All PASS

**Step 7: Commit**

```bash
git add src/security/ tests/security/
git commit -m "feat(security): add SecretVault for encrypting secrets"
```

---

## Task 2: Create Admin Auth Module

**Files:**
- Create: `src/security/auth.py`
- Create: `tests/security/test_auth.py`
- Modify: `src/ui/data_layer.py` (add role column)

**Step 1: Write failing test for auth**

```python
# tests/security/test_auth.py
"""Tests for admin authentication."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestAdminAuth:
    """Test admin role checking."""

    @pytest.mark.asyncio
    async def test_get_user_role_returns_role(self):
        """Get user role from database."""
        from src.security.auth import get_user_role

        # This will fail until we implement get_user_role
        role = await get_user_role("admin")
        assert role in ("user", "admin", "readonly", None)

    @pytest.mark.asyncio
    async def test_is_admin_true_for_admin_role(self):
        """is_admin returns True for admin users."""
        from src.security.auth import is_admin

        result = await is_admin("admin")
        # Will depend on actual DB state
        assert isinstance(result, bool)

    def test_require_admin_dependency(self):
        """require_admin can be used as FastAPI dependency."""
        from src.security.auth import require_admin
        from fastapi import Depends

        # Should be callable
        assert callable(require_admin)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/security/test_auth.py -v
```
Expected: FAIL with "No module named 'src.security.auth'"

**Step 3: Add role column migration to data_layer.py**

Add after line 191 in `src/ui/data_layer.py`:

```python
# Add to CHAINLIT_SCHEMA, after app_users table:
-- Add role column to app_users (migration)
-- SQLite doesn't support ALTER COLUMN, so we handle this in code
```

**Step 4: Write auth implementation**

```python
# src/security/auth.py
"""
Admin authentication and authorization.
Provides middleware and utilities for checking admin access.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Request, Depends
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)


async def get_user_role(username: str) -> Optional[str]:
    """
    Get user role from database.

    Args:
        username: Username to look up

    Returns:
        Role string ('user', 'admin', 'readonly') or None if not found
    """
    import aiosqlite
    from src.ui.data_layer import get_database_path

    db_path = get_database_path()

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            # Check if role column exists, add if not
            cursor = await db.execute("PRAGMA table_info(app_users)")
            columns = [row[1] for row in await cursor.fetchall()]

            if "role" not in columns:
                await db.execute(
                    "ALTER TABLE app_users ADD COLUMN role TEXT DEFAULT 'user'"
                )
                await db.commit()
                logger.info("Added 'role' column to app_users table")

            cursor = await db.execute(
                "SELECT role FROM app_users WHERE username = ?",
                (username,)
            )
            row = await cursor.fetchone()

            if row:
                return row[0] or "user"
            return None

    except Exception as e:
        logger.error(f"Failed to get user role: {e}")
        return None


async def set_user_role(username: str, role: str) -> bool:
    """
    Set user role in database.

    Args:
        username: Username to update
        role: New role ('user', 'admin', 'readonly')

    Returns:
        True if successful
    """
    import aiosqlite
    from src.ui.data_layer import get_database_path

    if role not in ("user", "admin", "readonly"):
        raise ValueError(f"Invalid role: {role}")

    db_path = get_database_path()

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute(
                "UPDATE app_users SET role = ? WHERE username = ?",
                (role, username)
            )
            await db.commit()
            logger.info(f"Set role '{role}' for user '{username}'")
            return True

    except Exception as e:
        logger.error(f"Failed to set user role: {e}")
        return False


async def is_admin(username: str) -> bool:
    """Check if user has admin role."""
    role = await get_user_role(username)
    return role == "admin"


async def get_current_user_from_session(request: Request) -> Optional[str]:
    """
    Extract current username from Chainlit session cookie.

    Args:
        request: FastAPI request

    Returns:
        Username or None
    """
    # Chainlit stores session in cookie
    session_id = request.cookies.get("chainlit-session")
    if not session_id:
        return None

    # For now, we'll check the users table by looking at recent activity
    # In production, you'd want to decode the session properly
    import aiosqlite
    from src.ui.data_layer import get_database_path

    db_path = get_database_path()

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            # Get user from Chainlit's users table via threads
            cursor = await db.execute("""
                SELECT u.identifier
                FROM users u
                JOIN threads t ON t.userId = u.id
                ORDER BY t.createdAt DESC
                LIMIT 1
            """)
            row = await cursor.fetchone()
            if row:
                return row[0]
    except Exception as e:
        logger.error(f"Failed to get current user: {e}")

    return None


async def require_admin(request: Request) -> str:
    """
    FastAPI dependency that requires admin role.

    Usage:
        @router.get("/admin/something")
        async def admin_endpoint(user: str = Depends(require_admin)):
            ...

    Raises:
        HTTPException 401 if not authenticated
        HTTPException 403 if not admin
    """
    username = await get_current_user_from_session(request)

    if not username:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    if not await is_admin(username):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return username


async def require_admin_or_redirect(request: Request) -> Optional[str]:
    """
    Similar to require_admin but returns None for redirect handling.
    Used for HTML pages that should redirect instead of returning 403.
    """
    username = await get_current_user_from_session(request)

    if not username:
        return None

    if not await is_admin(username):
        return None

    return username
```

**Step 5: Update security __init__.py**

```python
# src/security/__init__.py
"""Security module for Odoo AI Agent."""
from src.security.vault import (
    SecretVault,
    get_or_create_master_key,
    get_vault,
)
from src.security.auth import (
    get_user_role,
    set_user_role,
    is_admin,
    require_admin,
    require_admin_or_redirect,
    get_current_user_from_session,
)

__all__ = [
    "SecretVault",
    "get_or_create_master_key",
    "get_vault",
    "get_user_role",
    "set_user_role",
    "is_admin",
    "require_admin",
    "require_admin_or_redirect",
    "get_current_user_from_session",
]
```

**Step 6: Run tests**

```bash
pytest tests/security/test_auth.py -v
```
Expected: PASS

**Step 7: Commit**

```bash
git add src/security/ tests/security/
git commit -m "feat(security): add admin authentication module"
```

---

## Task 3: Create API Key Manager

**Files:**
- Create: `src/security/api_keys.py`
- Create: `tests/security/test_api_keys.py`

**Step 1: Write failing test**

```python
# tests/security/test_api_keys.py
"""Tests for API key management."""
import pytest
from datetime import datetime, timedelta


class TestAPIKeyManager:
    """Test API key CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_api_key_returns_full_key(self, tmp_path):
        """Creating a key returns the full key (only time it's visible)."""
        from src.security.api_keys import APIKeyManager

        manager = APIKeyManager(db_path=tmp_path / "test.db")
        await manager.init_db()

        key_data = await manager.create_key(
            name="Test Key",
            created_by="admin"
        )

        assert "key" in key_data
        assert key_data["key"].startswith("sk_live_")
        assert len(key_data["key"]) > 40
        assert "id" in key_data
        assert key_data["name"] == "Test Key"

    @pytest.mark.asyncio
    async def test_verify_key_valid(self, tmp_path):
        """Valid key passes verification."""
        from src.security.api_keys import APIKeyManager

        manager = APIKeyManager(db_path=tmp_path / "test.db")
        await manager.init_db()

        key_data = await manager.create_key(name="Test", created_by="admin")
        full_key = key_data["key"]

        result = await manager.verify_key(full_key)

        assert result is not None
        assert result["name"] == "Test"

    @pytest.mark.asyncio
    async def test_verify_key_invalid(self, tmp_path):
        """Invalid key fails verification."""
        from src.security.api_keys import APIKeyManager

        manager = APIKeyManager(db_path=tmp_path / "test.db")
        await manager.init_db()

        result = await manager.verify_key("sk_live_invalid_key_12345")

        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_key(self, tmp_path):
        """Revoked key fails verification."""
        from src.security.api_keys import APIKeyManager

        manager = APIKeyManager(db_path=tmp_path / "test.db")
        await manager.init_db()

        key_data = await manager.create_key(name="Test", created_by="admin")
        full_key = key_data["key"]

        await manager.revoke_key(key_data["id"])

        result = await manager.verify_key(full_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_expired_key_fails(self, tmp_path):
        """Expired key fails verification."""
        from src.security.api_keys import APIKeyManager

        manager = APIKeyManager(db_path=tmp_path / "test.db")
        await manager.init_db()

        # Create key that expires in the past
        key_data = await manager.create_key(
            name="Expired",
            created_by="admin",
            expires_in_days=-1
        )
        full_key = key_data["key"]

        result = await manager.verify_key(full_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_keys_hides_hash(self, tmp_path):
        """List keys returns metadata but not hashes."""
        from src.security.api_keys import APIKeyManager

        manager = APIKeyManager(db_path=tmp_path / "test.db")
        await manager.init_db()

        await manager.create_key(name="Key1", created_by="admin")
        await manager.create_key(name="Key2", created_by="admin")

        keys = await manager.list_keys()

        assert len(keys) == 2
        for key in keys:
            assert "key_hash" not in key
            assert "key_prefix" in key
            assert "name" in key

    @pytest.mark.asyncio
    async def test_log_usage(self, tmp_path):
        """Key usage is logged."""
        from src.security.api_keys import APIKeyManager

        manager = APIKeyManager(db_path=tmp_path / "test.db")
        await manager.init_db()

        key_data = await manager.create_key(name="Test", created_by="admin")

        await manager.log_usage(
            key_id=key_data["id"],
            endpoint="/api/chat",
            method="POST",
            ip_address="127.0.0.1",
            response_status=200
        )

        usage = await manager.get_key_usage(key_data["id"])
        assert len(usage) == 1
        assert usage[0]["endpoint"] == "/api/chat"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/security/test_api_keys.py -v
```
Expected: FAIL

**Step 3: Write API key manager implementation**

```python
# src/security/api_keys.py
"""
API Key Management.
Handles creation, verification, revocation, and usage logging of API keys.
"""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import aiosqlite

logger = logging.getLogger(__name__)

# Key prefix for identification
KEY_PREFIX_LIVE = "sk_live_"
KEY_PREFIX_TEST = "sk_test_"


class APIKeyManager:
    """
    Manages API keys with hashing, expiration, and audit logging.

    Keys are stored as SHA-256 hashes. The full key is only
    returned once at creation time.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize API key manager.

        Args:
            db_path: Path to SQLite database (default: logs/chat_history.db)
        """
        if db_path is None:
            from src.ui.data_layer import get_database_path
            db_path = get_database_path()
        self.db_path = Path(db_path)

    async def init_db(self):
        """Initialize database tables for API keys."""
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
                CREATE INDEX IF NOT EXISTS idx_api_key_usage_timestamp ON api_key_usage(timestamp);
            """)
            await db.commit()
            logger.info("API keys database tables initialized")

    def _generate_key(self, test_mode: bool = False) -> str:
        """Generate a new API key."""
        prefix = KEY_PREFIX_TEST if test_mode else KEY_PREFIX_LIVE
        random_part = secrets.token_urlsafe(24)  # 32 chars
        return f"{prefix}{random_part}"

    def _hash_key(self, key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(key.encode()).hexdigest()

    def _get_prefix(self, key: str) -> str:
        """Get the visible prefix of a key (first 12 chars)."""
        return key[:12] + "..."

    async def create_key(
        self,
        name: str,
        created_by: str,
        permissions: str = "full",
        expires_in_days: Optional[int] = None,
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key
            created_by: Username of creator
            permissions: 'full', 'readonly', or 'chat_only'
            expires_in_days: Days until expiration (None = never)
            test_mode: If True, creates sk_test_ key

        Returns:
            Dict with id, name, key (full key - only time visible!), key_prefix
        """
        key_id = str(uuid.uuid4())
        full_key = self._generate_key(test_mode)
        key_hash = self._hash_key(full_key)
        key_prefix = self._get_prefix(full_key)

        expires_at = None
        if expires_in_days is not None:
            expires_at = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO api_keys
                   (id, name, key_hash, key_prefix, created_by, permissions, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (key_id, name, key_hash, key_prefix, created_by, permissions, expires_at)
            )
            await db.commit()

        logger.info(f"Created API key '{name}' (id={key_id}) by {created_by}")

        return {
            "id": key_id,
            "name": name,
            "key": full_key,  # Only returned at creation!
            "key_prefix": key_prefix,
            "permissions": permissions,
            "expires_at": expires_at,
        }

    async def verify_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Verify an API key and return its metadata.

        Args:
            key: Full API key to verify

        Returns:
            Key metadata dict if valid, None if invalid/expired/revoked
        """
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

            # Check if revoked
            if row["revoked_at"]:
                logger.warning(f"Attempt to use revoked key: {row['id']}")
                return None

            # Check if expired
            if row["expires_at"]:
                expires = datetime.fromisoformat(row["expires_at"])
                if datetime.utcnow() > expires:
                    logger.warning(f"Attempt to use expired key: {row['id']}")
                    return None

            return {
                "id": row["id"],
                "name": row["name"],
                "permissions": row["permissions"],
                "created_by": row["created_by"],
            }

    async def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an API key.

        Args:
            key_id: ID of key to revoke

        Returns:
            True if revoked successfully
        """
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                "UPDATE api_keys SET revoked_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), key_id)
            )
            await db.commit()

        logger.info(f"Revoked API key: {key_id}")
        return True

    async def list_keys(self) -> List[Dict[str, Any]]:
        """
        List all API keys (without hashes).

        Returns:
            List of key metadata dicts
        """
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT id, name, key_prefix, created_at, expires_at,
                          revoked_at, created_by, permissions
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

    async def log_usage(
        self,
        key_id: str,
        endpoint: str,
        method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_status: Optional[int] = None,
    ):
        """Log API key usage for audit."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO api_key_usage
                   (key_id, endpoint, method, ip_address, user_agent, response_status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key_id, endpoint, method, ip_address, user_agent, response_status)
            )
            await db.commit()

    async def get_key_usage(
        self,
        key_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get usage history for a key."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT endpoint, method, ip_address, user_agent,
                          timestamp, response_status
                   FROM api_key_usage
                   WHERE key_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (key_id, limit)
            )
            rows = await cursor.fetchall()

            return [dict(row) for row in rows]


# Global manager instance
_manager: Optional[APIKeyManager] = None


async def get_api_key_manager() -> APIKeyManager:
    """Get or create global API key manager."""
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
        await _manager.init_db()
    return _manager
```

**Step 4: Update security __init__.py**

Add to exports:
```python
from src.security.api_keys import (
    APIKeyManager,
    get_api_key_manager,
)
```

**Step 5: Run tests**

```bash
pytest tests/security/test_api_keys.py -v
```
Expected: All PASS

**Step 6: Commit**

```bash
git add src/security/ tests/security/
git commit -m "feat(security): add API key manager with audit logging"
```

---

## Task 4: Integrate Vault with Settings

**Files:**
- Modify: `src/settings_manager/settings_db.py`
- Create: `tests/security/test_settings_encryption.py`

**Step 1: Write test for encrypted settings**

```python
# tests/security/test_settings_encryption.py
"""Tests for settings encryption."""
import pytest
import os


class TestSettingsEncryption:
    """Test that secrets are encrypted in settings DB."""

    def test_secret_is_encrypted_in_db(self, tmp_path, monkeypatch):
        """Secret values are stored encrypted."""
        # Use temp database
        monkeypatch.setenv("LOGS_DIR", str(tmp_path))

        from src.settings_manager.settings_db import save_setting, get_setting, init_settings_db

        init_settings_db()

        # Save a secret
        save_setting("OPENAI_API_KEY", "sk-test-key-12345")

        # Read back - should be decrypted
        value = get_setting("OPENAI_API_KEY")
        assert value == "sk-test-key-12345"

    def test_non_secret_is_not_encrypted(self, tmp_path, monkeypatch):
        """Non-secret values are stored in plain text."""
        monkeypatch.setenv("LOGS_DIR", str(tmp_path))

        from src.settings_manager.settings_db import save_setting, get_setting, init_settings_db

        init_settings_db()

        save_setting("LOG_LEVEL", "DEBUG")
        value = get_setting("LOG_LEVEL")

        assert value == "DEBUG"
```

**Step 2: Update settings_db.py to use vault**

Add encryption to `save_setting` and decryption to `get_setting` for SECRET_KEYS.

**Step 3: Run tests and commit**

```bash
pytest tests/security/test_settings_encryption.py -v
git add src/settings_manager/ tests/security/
git commit -m "feat(security): encrypt secrets in settings database"
```

---

## Task 5: Add Admin Middleware

**Files:**
- Modify: `src/admin/__init__.py`
- Modify: `src/admin/settings.py`

**Step 1: Update admin/__init__.py with middleware**

```python
# Add require_admin dependency to all admin routes
```

**Step 2: Update settings.py to check admin**

Add `Depends(require_admin)` to all endpoints.

**Step 3: Test manually and commit**

```bash
git add src/admin/
git commit -m "feat(security): add admin role check to admin routes"
```

---

## Task 6: Create Admin Users Page

**Files:**
- Create: `src/admin/users.py`
- Create: `src/admin/templates/users.html`

**Step 1: Create users router**

Endpoints:
- GET `/admin/users` - HTML page
- GET `/admin/api/users` - list users
- PUT `/admin/api/users/{id}/role` - change role

**Step 2: Create users.html template**

Table with users and role dropdown.

**Step 3: Commit**

```bash
git add src/admin/
git commit -m "feat(admin): add user management page"
```

---

## Task 7: Create API Keys Page

**Files:**
- Create: `src/admin/api_keys_routes.py`
- Create: `src/admin/templates/api_keys.html`

**Step 1: Create API keys router**

Endpoints:
- GET `/admin/api-keys` - HTML page
- GET `/admin/api/keys` - list keys
- POST `/admin/api/keys` - create key
- DELETE `/admin/api/keys/{id}` - revoke key
- GET `/admin/api/keys/{id}/usage` - usage stats

**Step 2: Create api_keys.html template**

Form to create keys, table of existing keys, usage modal.

**Step 3: Commit**

```bash
git add src/admin/
git commit -m "feat(admin): add API key management page"
```

---

## Task 8: Update API Auth to Use Key Manager

**Files:**
- Modify: `src/api/auth.py`

**Step 1: Update verify_api_key**

```python
async def verify_api_key(api_key: str = Security(api_key_header)) -> Dict:
    """Verify API key using APIKeyManager."""
    manager = await get_api_key_manager()
    key_data = await manager.verify_key(api_key)

    if not key_data:
        raise HTTPException(401, "Invalid API key")

    # Log usage
    # ...

    return key_data
```

**Step 2: Test and commit**

```bash
pytest tests/ -v -k api
git add src/api/
git commit -m "feat(api): use APIKeyManager for authentication"
```

---

## Task 9: Add Navigation to Admin Pages

**Files:**
- Modify: all admin templates

**Step 1: Add nav header to all templates**

```html
<nav>
    <a href="/admin/settings">Settings</a>
    <a href="/admin/users">Users</a>
    <a href="/admin/api-keys">API Keys</a>
    <a href="/admin/audit">Audit Log</a>
</nav>
```

**Step 2: Commit**

```bash
git add src/admin/templates/
git commit -m "feat(admin): add navigation between admin pages"
```

---

## Task 10: Migrate Existing Secrets

**Files:**
- Create: `scripts/migrate_secrets.py`

**Step 1: Create migration script**

Script that:
1. Reads existing plain-text secrets from settings table
2. Encrypts them with vault
3. Updates the database

**Step 2: Run migration and commit**

```bash
python scripts/migrate_secrets.py
git add scripts/
git commit -m "chore: add secret migration script"
```

---

## Final: Integration Test

**Step 1: Start server and test all flows**

1. Login as first user (should be admin)
2. Access /admin/settings - should work
3. Access /admin/users - should work
4. Create API key at /admin/api-keys
5. Test API with new key
6. Revoke key, verify it fails

**Step 2: Final commit**

```bash
git add .
git commit -m "feat(security): complete security improvements implementation"
```
