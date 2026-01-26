"""Tests for admin authentication."""
import pytest


class TestAdminAuth:
    """Test admin role checking."""

    @pytest.mark.asyncio
    async def test_get_user_role_returns_role(self, tmp_path, monkeypatch):
        """Get user role from database."""
        import aiosqlite

        db_path = tmp_path / "test.db"
        monkeypatch.setattr("src.ui.data_layer.get_database_path", lambda: db_path)

        # Create table
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("""
                CREATE TABLE app_users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE,
                    password_hash TEXT,
                    role TEXT DEFAULT 'user'
                )
            """)
            await db.execute("INSERT INTO app_users (username, password_hash, role) VALUES ('admin', 'hash', 'admin')")
            await db.commit()

        from src.security.auth import get_user_role
        role = await get_user_role("admin")
        assert role == "admin"

    @pytest.mark.asyncio
    async def test_is_admin_true_for_admin_role(self, tmp_path, monkeypatch):
        """is_admin returns True for admin users."""
        import aiosqlite

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
            await db.execute("INSERT INTO app_users (username, password_hash, role) VALUES ('admin', 'hash', 'admin')")
            await db.commit()

        from src.security.auth import is_admin
        result = await is_admin("admin")
        assert result is True

    def test_require_admin_dependency(self):
        """require_admin can be used as FastAPI dependency."""
        from src.security.auth import require_admin
        assert callable(require_admin)
