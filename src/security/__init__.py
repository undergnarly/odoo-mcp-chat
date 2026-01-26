"""Security module for Odoo AI Agent."""
from src.security.auth import (
    get_current_user_from_session,
    get_user_role,
    is_admin,
    require_admin,
    require_admin_or_redirect,
    set_user_role,
)
from src.security.vault import (
    SecretVault,
    get_or_create_master_key,
    get_vault,
)

__all__ = [
    # Auth
    "get_current_user_from_session",
    "get_user_role",
    "is_admin",
    "require_admin",
    "require_admin_or_redirect",
    "set_user_role",
    # Vault
    "SecretVault",
    "get_or_create_master_key",
    "get_vault",
]
