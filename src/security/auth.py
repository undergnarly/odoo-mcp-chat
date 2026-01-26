"""
Admin authentication and authorization.
Provides middleware and utilities for checking admin access.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


async def get_user_role(username: str) -> Optional[str]:
    """Get user role from database."""
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
    """Set user role in database."""
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
    Extract current username from request.

    Checks in order:
    1. X-User header (for API/testing)
    2. Chainlit access token cookie (contains user identifier)

    Note: For production, consider implementing proper JWT validation.
    """
    import aiosqlite
    from src.ui.data_layer import get_database_path

    # 1. Check X-User header (for testing/internal use)
    x_user = request.headers.get("X-User")
    if x_user:
        logger.debug(f"Using X-User header: {x_user}")
        return x_user

    # 2. Try to get user from Chainlit access token
    # Chainlit stores user identifier in 'access_token' cookie (base64 JSON)
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            import base64
            import json
            # Decode base64 token (may have padding issues)
            padded = access_token + "=" * (4 - len(access_token) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            token_data = json.loads(decoded)
            if "identifier" in token_data:
                logger.debug(f"Got user from access_token: {token_data['identifier']}")
                return token_data["identifier"]
        except Exception as e:
            logger.debug(f"Failed to decode access_token: {e}")

    # 3. Fallback: check if there's a single user (dev/simple setup)
    db_path = get_database_path()
    try:
        async with aiosqlite.connect(str(db_path)) as db:
            # If only one app_user exists, use that (simple single-user setup)
            cursor = await db.execute("SELECT COUNT(*) FROM app_users")
            count = (await cursor.fetchone())[0]

            if count == 1:
                cursor = await db.execute("SELECT username FROM app_users LIMIT 1")
                row = await cursor.fetchone()
                if row:
                    logger.debug(f"Single user mode, using: {row[0]}")
                    return row[0]
    except Exception as e:
        logger.error(f"Failed to get user from DB: {e}")

    return None


async def require_admin(request: Request) -> str:
    """FastAPI dependency that requires admin role."""
    username = await get_current_user_from_session(request)

    if not username:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not await is_admin(username):
        raise HTTPException(status_code=403, detail="Admin access required")

    return username


async def require_admin_or_redirect(request: Request) -> Optional[str]:
    """Similar to require_admin but returns None for redirect handling."""
    username = await get_current_user_from_session(request)

    if not username or not await is_admin(username):
        return None

    return username
