"""
Admin module for Odoo AI Agent
Provides admin pages for audit logs, settings, users, and other management features
"""
from fastapi import APIRouter

from src.admin.audit import router as audit_router
from src.admin.settings import router as settings_router
from src.admin.users import router as users_router
from src.admin.api_keys_routes import router as api_keys_router

# Main admin router
router = APIRouter(prefix="/admin", tags=["admin"])

# Include sub-routers
router.include_router(audit_router)
router.include_router(settings_router)
router.include_router(users_router)
router.include_router(api_keys_router)
