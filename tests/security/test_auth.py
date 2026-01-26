"""Tests for admin authentication."""
import pytest
import aiosqlite
from unittest.mock import MagicMock


@pytest.fixture
async def test_db(tmp_path, monkeypatch):
    """Create a test database with app_users table."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("src.ui.data_layer.get_database_path", lambda: db_path)

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("""
            CREATE TABLE app_users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT DEFAULT 'user'
            )
        """)
        await db.commit()

    return db_path


class TestGetUserRole:
    """Test get_user_role function."""

    @pytest.mark.asyncio
    async def test_returns_admin_role(self, test_db):
        """Returns admin role for admin user."""
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('admin', 'hash', 'admin')"
            )
            await db.commit()

        from src.security.auth import get_user_role
        role = await get_user_role("admin")
        assert role == "admin"

    @pytest.mark.asyncio
    async def test_returns_user_role_default(self, test_db):
        """Returns user role when role is null."""
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('user1', 'hash', NULL)"
            )
            await db.commit()

        from src.security.auth import get_user_role
        role = await get_user_role("user1")
        assert role == "user"

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_user(self, test_db):
        """Returns None for user that doesn't exist."""
        from src.security.auth import get_user_role
        role = await get_user_role("nonexistent")
        assert role is None


class TestSetUserRole:
    """Test set_user_role function."""

    @pytest.mark.asyncio
    async def test_sets_role_successfully(self, test_db):
        """Successfully sets user role."""
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('user1', 'hash', 'user')"
            )
            await db.commit()

        from src.security.auth import set_user_role, get_user_role
        result = await set_user_role("user1", "admin")
        assert result is True

        role = await get_user_role("user1")
        assert role == "admin"

    @pytest.mark.asyncio
    async def test_rejects_invalid_role(self, test_db):
        """Raises error for invalid role."""
        from src.security.auth import set_user_role

        with pytest.raises(ValueError, match="Invalid role"):
            await set_user_role("user1", "superadmin")


class TestIsAdmin:
    """Test is_admin function."""

    @pytest.mark.asyncio
    async def test_returns_true_for_admin(self, test_db):
        """Returns True for admin user."""
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('admin', 'hash', 'admin')"
            )
            await db.commit()

        from src.security.auth import is_admin
        assert await is_admin("admin") is True

    @pytest.mark.asyncio
    async def test_returns_false_for_user(self, test_db):
        """Returns False for regular user."""
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('user1', 'hash', 'user')"
            )
            await db.commit()

        from src.security.auth import is_admin
        assert await is_admin("user1") is False

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent(self, test_db):
        """Returns False for nonexistent user."""
        from src.security.auth import is_admin
        assert await is_admin("nonexistent") is False


class TestGetCurrentUserFromSession:
    """Test get_current_user_from_session function."""

    @pytest.mark.asyncio
    async def test_returns_x_user_header(self, test_db):
        """Returns user from X-User header."""
        from src.security.auth import get_current_user_from_session

        request = MagicMock()
        request.headers.get.return_value = "testuser"
        request.cookies.get.return_value = None

        user = await get_current_user_from_session(request)
        assert user == "testuser"

    @pytest.mark.asyncio
    async def test_returns_single_user_fallback(self, test_db):
        """Returns single user when only one exists."""
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('onlyuser', 'hash', 'admin')"
            )
            await db.commit()

        from src.security.auth import get_current_user_from_session

        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = None

        user = await get_current_user_from_session(request)
        assert user == "onlyuser"

    @pytest.mark.asyncio
    async def test_returns_none_no_auth(self, test_db):
        """Returns None when no auth info available and multiple users."""
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash) VALUES ('user1', 'hash')"
            )
            await db.execute(
                "INSERT INTO app_users (username, password_hash) VALUES ('user2', 'hash')"
            )
            await db.commit()

        from src.security.auth import get_current_user_from_session

        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = None

        user = await get_current_user_from_session(request)
        assert user is None


class TestRequireAdmin:
    """Test require_admin dependency."""

    def test_is_callable(self):
        """require_admin can be used as FastAPI dependency."""
        from src.security.auth import require_admin
        assert callable(require_admin)

    @pytest.mark.asyncio
    async def test_raises_401_no_user(self, test_db):
        """Raises 401 when no user found."""
        from fastapi import HTTPException
        from src.security.auth import require_admin

        request = MagicMock()
        request.headers.get.return_value = None
        request.cookies.get.return_value = None

        # Multiple users so fallback doesn't work
        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash) VALUES ('u1', 'h')"
            )
            await db.execute(
                "INSERT INTO app_users (username, password_hash) VALUES ('u2', 'h')"
            )
            await db.commit()

        with pytest.raises(HTTPException) as exc:
            await require_admin(request)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_403_not_admin(self, test_db):
        """Raises 403 when user is not admin."""
        from fastapi import HTTPException
        from src.security.auth import require_admin

        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('user1', 'h', 'user')"
            )
            await db.commit()

        request = MagicMock()
        request.headers.get.return_value = "user1"
        request.cookies.get.return_value = None

        with pytest.raises(HTTPException) as exc:
            await require_admin(request)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_username_for_admin(self, test_db):
        """Returns username when user is admin."""
        from src.security.auth import require_admin

        async with aiosqlite.connect(str(test_db)) as db:
            await db.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES ('admin', 'h', 'admin')"
            )
            await db.commit()

        request = MagicMock()
        request.headers.get.return_value = "admin"
        request.cookies.get.return_value = None

        result = await require_admin(request)
        assert result == "admin"
