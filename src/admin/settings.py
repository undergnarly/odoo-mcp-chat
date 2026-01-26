"""
Admin settings page
Configure Odoo connection, API keys, and other parameters
"""
import os
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from src.security.auth import require_admin

from src.settings_manager.settings_db import (
    get_all_settings,
    save_settings,
    delete_all_settings,
    increment_config_version,
    SETTINGS_SCHEMA,
    SECRET_KEYS,
)
from src.settings_manager.loader import load_config_from_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Path to template
TEMPLATE_PATH = Path(__file__).parent / "templates" / "settings.html"


def get_env_settings() -> Dict[str, str]:
    """Get settings from environment variables (.env file)"""
    result = {}
    for key in SETTINGS_SCHEMA:
        result[key] = os.environ.get(key, SETTINGS_SCHEMA[key].get("default", ""))
    return result


def mask_secrets(settings: Dict[str, str]) -> Dict[str, str]:
    """Mask secret values in settings dict"""
    result = {}
    for key, value in settings.items():
        if key in SECRET_KEYS and value:
            result[key] = "********"
        else:
            result[key] = value
    return result


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the settings page"""
    # TODO: Add Chainlit session authentication check
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@router.get("/api/settings")
async def get_settings(request: Request):
    """
    Get all current settings

    Returns settings from both .env and database, with secrets masked
    """
    # Get settings from environment (includes .env and DB overrides)
    env_settings = get_env_settings()

    # Get settings from database
    db_settings = get_all_settings(mask_secrets=False)

    # Merge: DB overrides ENV
    merged = {**env_settings}
    for key, value in db_settings.items():
        if value:
            merged[key] = value

    # Mask secrets before sending
    masked = mask_secrets(merged)

    # Add metadata
    return JSONResponse(content={
        "settings": masked,
        "schema": SETTINGS_SCHEMA,
    })


@router.post("/api/settings")
async def save_settings_endpoint(request: Request, admin_user: str = Depends(require_admin)):
    """
    Save settings to database

    Masked values (********) are skipped to preserve existing passwords
    """
    try:
        data = await request.json()
        settings = data.get("settings", {})

        if not settings:
            raise HTTPException(status_code=400, detail="No settings provided")

        # Filter to only known settings
        filtered = {}
        for key in SETTINGS_SCHEMA:
            if key in settings:
                value = settings[key]
                # Skip masked values
                if value != "********":
                    filtered[key] = value

        # Save to database
        save_settings(filtered, skip_masked=True)

        # Increment config version for hot-reload
        new_version = increment_config_version()

        # Reload config into environment
        load_config_from_db()

        logger.info(f"Settings saved, new config version: {new_version}")

        return JSONResponse(content={
            "success": True,
            "message": "Settings saved successfully",
            "config_version": new_version,
        })

    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/settings")
async def reset_settings(request: Request, admin_user: str = Depends(require_admin)):
    """
    Reset all settings to .env defaults

    Deletes all settings from database, reverting to .env values
    """
    try:
        delete_all_settings()
        new_version = increment_config_version()

        logger.info("Settings reset to .env defaults")

        return JSONResponse(content={
            "success": True,
            "message": "Settings reset to .env defaults",
            "config_version": new_version,
        })

    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/settings/test-odoo")
async def test_odoo_connection(request: Request, admin_user: str = Depends(require_admin)):
    """
    Test Odoo connection with provided credentials

    Uses current settings (from form, not saved yet)
    """
    try:
        data = await request.json()
        settings = data.get("settings", {})

        url = settings.get("ODOO_URL", os.environ.get("ODOO_URL"))
        db = settings.get("ODOO_DB", os.environ.get("ODOO_DB"))
        username = settings.get("ODOO_USERNAME", os.environ.get("ODOO_USERNAME"))
        password = settings.get("ODOO_PASSWORD")

        # If password is masked, use existing
        if password == "********":
            password = os.environ.get("ODOO_PASSWORD")

        if not all([url, db, username, password]):
            return JSONResponse(content={
                "success": False,
                "message": "Missing required Odoo connection parameters",
            })

        # Try to connect
        from src.odoo_mcp.odoo_client import OdooClient

        client = OdooClient(
            url=url,
            db=db,
            username=username,
            password=password,
        )

        # Try a simple operation
        uid = client.uid
        if uid:
            return JSONResponse(content={
                "success": True,
                "message": f"Connection successful! Authenticated as user ID: {uid}",
            })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "Authentication failed",
            })

    except Exception as e:
        logger.error(f"Odoo connection test failed: {e}")
        return JSONResponse(content={
            "success": False,
            "message": f"Connection failed: {str(e)}",
        })
