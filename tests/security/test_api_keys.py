"""Tests for API Key Manager."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from src.security.api_keys import APIKeyManager, KEY_PREFIX_LIVE, KEY_PREFIX_TEST


class TestAPIKeyManager:
    """Test API key management functionality."""

    @pytest.fixture
    async def manager(self, tmp_path):
        """Create an API key manager with a temporary database."""
        db_path = tmp_path / "test_api_keys.db"
        manager = APIKeyManager(db_path=db_path)
        await manager.init_db()
        return manager

    @pytest.mark.asyncio
    async def test_create_key_returns_full_key_with_live_prefix(self, manager):
        """create_key returns full key with sk_live_ prefix."""
        result = await manager.create_key(
            name="Test Key",
            created_by="admin",
            permissions="read",
        )

        assert "key" in result
        assert result["key"].startswith(KEY_PREFIX_LIVE)
        assert len(result["key"]) > len(KEY_PREFIX_LIVE)
        assert result["name"] == "Test Key"
        assert result["permissions"] == "read"
        assert result["id"] is not None

    @pytest.mark.asyncio
    async def test_create_key_test_mode_returns_test_prefix(self, manager):
        """create_key with test_mode returns sk_test_ prefix."""
        result = await manager.create_key(
            name="Test Mode Key",
            created_by="admin",
            test_mode=True,
        )

        assert result["key"].startswith(KEY_PREFIX_TEST)

    @pytest.mark.asyncio
    async def test_verify_key_returns_metadata_for_valid_key(self, manager):
        """verify_key returns metadata for valid key."""
        created = await manager.create_key(
            name="Valid Key",
            created_by="admin",
            permissions="full",
        )

        result = await manager.verify_key(created["key"])

        assert result is not None
        assert result["id"] == created["id"]
        assert result["name"] == "Valid Key"
        assert result["permissions"] == "full"
        assert result["created_by"] == "admin"

    @pytest.mark.asyncio
    async def test_verify_key_returns_none_for_invalid_key(self, manager):
        """verify_key returns None for invalid key."""
        result = await manager.verify_key("sk_live_invalid_key_that_does_not_exist")

        assert result is None

    @pytest.mark.asyncio
    async def test_revoked_key_fails_verification(self, manager):
        """Revoked key fails verification."""
        created = await manager.create_key(
            name="Key to Revoke",
            created_by="admin",
        )

        # Verify key works before revocation
        assert await manager.verify_key(created["key"]) is not None

        # Revoke the key
        await manager.revoke_key(created["id"])

        # Verify key no longer works
        result = await manager.verify_key(created["key"])
        assert result is None

    @pytest.mark.asyncio
    async def test_expired_key_fails_verification(self, manager):
        """Expired key fails verification."""
        # Create a key that expires in -1 days (already expired)
        created = await manager.create_key(
            name="Expired Key",
            created_by="admin",
            expires_in_days=-1,  # Expired yesterday
        )

        result = await manager.verify_key(created["key"])
        assert result is None

    @pytest.mark.asyncio
    async def test_list_keys_hides_hash(self, manager):
        """list_keys returns keys without the full hash."""
        await manager.create_key(name="Key 1", created_by="admin")
        await manager.create_key(name="Key 2", created_by="admin")

        keys = await manager.list_keys()

        assert len(keys) == 2
        for key in keys:
            # Should have key_prefix but not the full key or hash
            assert "key_prefix" in key
            assert "key" not in key
            assert "key_hash" not in key
            # key_prefix should be truncated
            assert key["key_prefix"].endswith("...")

    @pytest.mark.asyncio
    async def test_list_keys_shows_all_metadata(self, manager):
        """list_keys returns all relevant metadata."""
        await manager.create_key(
            name="Full Key",
            created_by="test_user",
            permissions="read",
            expires_in_days=30,
        )

        keys = await manager.list_keys()

        assert len(keys) == 1
        key = keys[0]
        assert key["name"] == "Full Key"
        assert key["created_by"] == "test_user"
        assert key["permissions"] == "read"
        assert key["expires_at"] is not None
        assert key["revoked_at"] is None
        assert key["is_active"] is True

    @pytest.mark.asyncio
    async def test_log_usage_and_get_key_usage(self, manager):
        """log_usage and get_key_usage work correctly."""
        created = await manager.create_key(name="Usage Key", created_by="admin")

        # Log some usage
        await manager.log_usage(
            key_id=created["id"],
            endpoint="/api/v1/test",
            method="GET",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            response_status=200,
        )
        await manager.log_usage(
            key_id=created["id"],
            endpoint="/api/v1/other",
            method="POST",
            ip_address="192.168.1.2",
            user_agent="TestAgent/1.0",
            response_status=201,
        )

        # Get usage
        usage = await manager.get_key_usage(created["id"])

        assert len(usage) == 2
        # Check that both records are present (order may vary due to timestamp precision)
        endpoints = {u["endpoint"] for u in usage}
        methods = {u["method"] for u in usage}
        statuses = {u["response_status"] for u in usage}

        assert endpoints == {"/api/v1/test", "/api/v1/other"}
        assert methods == {"GET", "POST"}
        assert statuses == {200, 201}

        # Verify individual records have correct associated data
        for u in usage:
            if u["endpoint"] == "/api/v1/test":
                assert u["method"] == "GET"
                assert u["ip_address"] == "192.168.1.1"
                assert u["response_status"] == 200
            else:
                assert u["method"] == "POST"
                assert u["ip_address"] == "192.168.1.2"
                assert u["response_status"] == 201

    @pytest.mark.asyncio
    async def test_get_key_usage_respects_limit(self, manager):
        """get_key_usage respects the limit parameter."""
        created = await manager.create_key(name="Limited Key", created_by="admin")

        # Log many usages
        for i in range(10):
            await manager.log_usage(
                key_id=created["id"],
                endpoint=f"/api/v1/endpoint{i}",
                method="GET",
                response_status=200,
            )

        # Get with limit
        usage = await manager.get_key_usage(created["id"], limit=5)

        assert len(usage) == 5

    @pytest.mark.asyncio
    async def test_create_key_with_expiration(self, manager):
        """create_key with expires_in_days sets correct expiration."""
        result = await manager.create_key(
            name="Expiring Key",
            created_by="admin",
            expires_in_days=30,
        )

        assert result["expires_at"] is not None
        expires_at = datetime.fromisoformat(result["expires_at"])
        expected = datetime.utcnow() + timedelta(days=30)
        # Allow 1 minute tolerance
        assert abs((expires_at - expected).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_key_prefix_format(self, manager):
        """Key prefix is properly truncated."""
        result = await manager.create_key(name="Prefix Test", created_by="admin")

        # Prefix should be first 12 chars + "..."
        expected_prefix = result["key"][:12] + "..."
        assert result["key_prefix"] == expected_prefix

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, tmp_path):
        """init_db creates required tables."""
        import aiosqlite

        db_path = tmp_path / "new_db.db"
        manager = APIKeyManager(db_path=db_path)
        await manager.init_db()

        async with aiosqlite.connect(str(db_path)) as db:
            # Check api_keys table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'"
            )
            assert await cursor.fetchone() is not None

            # Check api_key_usage table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='api_key_usage'"
            )
            assert await cursor.fetchone() is not None

    @pytest.mark.asyncio
    async def test_revoke_key_returns_true(self, manager):
        """revoke_key returns True on success."""
        created = await manager.create_key(name="Revoke Test", created_by="admin")

        result = await manager.revoke_key(created["id"])

        assert result is True

    @pytest.mark.asyncio
    async def test_list_keys_shows_revoked_status(self, manager):
        """list_keys correctly shows revoked keys as inactive."""
        created = await manager.create_key(name="Revoke Status", created_by="admin")
        await manager.revoke_key(created["id"])

        keys = await manager.list_keys()

        assert len(keys) == 1
        assert keys[0]["is_active"] is False
        assert keys[0]["revoked_at"] is not None
