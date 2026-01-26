"""Admin API keys management page."""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from src.security.auth import require_admin
from src.security.api_keys import get_api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter()
TEMPLATE_PATH = Path(__file__).parent / "templates" / "api_keys.html"


@router.get("/api-keys", response_class=HTMLResponse)
async def api_keys_page(request: Request):
    """Render the API keys management page."""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/api/keys")
async def list_keys(request: Request, admin_user: str = Depends(require_admin)):
    """List all API keys."""
    manager = await get_api_key_manager()
    keys = await manager.list_keys()
    return JSONResponse(content={"keys": keys})


@router.post("/api/keys")
async def create_key(request: Request, admin_user: str = Depends(require_admin)):
    """Create a new API key."""
    data = await request.json()
    name = data.get("name", "").strip()
    permissions = data.get("permissions", "full")
    expires_in_days = data.get("expires_in_days")

    if not name:
        raise HTTPException(400, "Name is required")

    manager = await get_api_key_manager()
    key_data = await manager.create_key(
        name=name,
        created_by=admin_user,
        permissions=permissions,
        expires_in_days=expires_in_days,
    )

    return JSONResponse(content={"success": True, **key_data})


@router.delete("/api/keys/{key_id}")
async def revoke_key(key_id: str, request: Request, admin_user: str = Depends(require_admin)):
    """Revoke an API key."""
    manager = await get_api_key_manager()
    await manager.revoke_key(key_id)
    return JSONResponse(content={"success": True})


@router.get("/api/keys/{key_id}/usage")
async def get_key_usage(key_id: str, request: Request, admin_user: str = Depends(require_admin)):
    """Get API key usage history."""
    manager = await get_api_key_manager()
    usage = await manager.get_key_usage(key_id, limit=100)
    return JSONResponse(content={"usage": usage})
