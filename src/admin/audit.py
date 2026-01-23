"""
Audit log admin page
Displays all database changes made by the AI agent
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.utils.logging import (
    read_audit_log,
    get_audit_models,
    count_audit_entries,
)

router = APIRouter()

# Path to template
TEMPLATE_PATH = Path(__file__).parent / "templates" / "audit.html"


@router.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    """Render the audit log page"""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@router.get("/api/audit")
async def get_audit_entries(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    """
    Get audit log entries with filtering and pagination

    Query params:
        limit: Number of entries to return (1-500, default 50)
        offset: Number of entries to skip
        action: Filter by action type (create/update/delete)
        model: Filter by model name
        date_from: Filter from date (YYYY-MM-DD)
        date_to: Filter to date (YYYY-MM-DD)
    """
    entries = read_audit_log(
        limit=limit,
        offset=offset,
        action_filter=action,
        model_filter=model,
        date_from=date_from,
        date_to=date_to,
    )

    total = count_audit_entries(
        action_filter=action,
        model_filter=model,
        date_from=date_from,
        date_to=date_to,
    )

    return JSONResponse(content={
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/api/audit/models")
async def get_models():
    """Get list of unique models in audit log for filter dropdown"""
    models = get_audit_models()
    return JSONResponse(content={"models": models})
