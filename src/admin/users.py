"""Admin users management page."""
import logging
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from src.security.auth import require_admin, get_user_role, set_user_role

logger = logging.getLogger(__name__)

router = APIRouter()
TEMPLATE_PATH = Path(__file__).parent / "templates" / "users.html"


async def get_all_users() -> List[Dict[str, Any]]:
    """Get all users from app_users table."""
    import aiosqlite
    from src.ui.data_layer import get_database_path

    db_path = get_database_path()
    async with aiosqlite.connect(str(db_path)) as db:
        # Ensure role column exists
        cursor = await db.execute("PRAGMA table_info(app_users)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "role" not in columns:
            await db.execute("ALTER TABLE app_users ADD COLUMN role TEXT DEFAULT 'user'")
            await db.commit()

        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, email, role, created_at, is_active FROM app_users ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """Render the users management page."""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/api/users")
async def list_users(request: Request, admin_user: str = Depends(require_admin)):
    """List all users."""
    users = await get_all_users()
    return JSONResponse(content={"users": users})


@router.put("/api/users/{username}/role")
async def update_user_role(username: str, request: Request, admin_user: str = Depends(require_admin)):
    """Update user role."""
    data = await request.json()
    new_role = data.get("role")

    if new_role not in ("user", "admin", "readonly"):
        raise HTTPException(400, "Invalid role")

    if username == admin_user and new_role != "admin":
        raise HTTPException(400, "Cannot remove your own admin role")

    success = await set_user_role(username, new_role)
    if not success:
        raise HTTPException(500, "Failed to update role")

    return JSONResponse(content={"success": True, "role": new_role})
