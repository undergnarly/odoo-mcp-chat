"""Security module for Odoo AI Agent."""
from src.security.vault import (
    SecretVault,
    get_or_create_master_key,
    get_vault,
)

__all__ = [
    "SecretVault",
    "get_or_create_master_key",
    "get_vault",
]
