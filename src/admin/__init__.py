"""
Admin module for Odoo AI Agent
Provides admin pages for audit logs and other management features
"""
from fastapi import APIRouter

from src.admin.audit import router as audit_router

# Main admin router
router = APIRouter(prefix="/admin", tags=["admin"])

# Include sub-routers
router.include_router(audit_router)
