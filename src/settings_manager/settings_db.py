"""
SQLite-based settings storage
CRUD operations for application settings
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.security.vault import get_vault

# Use standard logging to avoid circular import with src.utils.logging
logger = logging.getLogger(__name__)

# Database path (same as chat history)
DB_PATH = Path("logs/chat_history.db")

# Settings that contain sensitive data (passwords, API keys)
SECRET_KEYS = {
    "ODOO_PASSWORD",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "AGENT_API_KEY",
    "ADMIN_API_KEY",
    "CHAINLIT_AUTH_SECRET",
    "CHAINLIT_AUTH_PASSWORD",
}

# All configurable settings with their types and defaults
SETTINGS_SCHEMA = {
    # Odoo Connection
    "ODOO_URL": {"type": "text", "required": True, "group": "odoo"},
    "ODOO_DB": {"type": "text", "required": True, "group": "odoo"},
    "ODOO_USERNAME": {"type": "text", "required": True, "group": "odoo"},
    "ODOO_PASSWORD": {"type": "password", "required": True, "group": "odoo"},
    "ODOO_TIMEOUT": {"type": "number", "default": "30", "group": "odoo"},
    # LLM
    "LLM_MODEL": {"type": "text", "default": "gpt-4o", "group": "llm"},
    "OPENAI_API_KEY": {"type": "password", "required": True, "group": "llm"},
    "LLM_TEMPERATURE": {"type": "number", "default": "0.1", "group": "llm"},
    # Security
    "AGENT_API_KEY": {"type": "password", "group": "security"},
    "READ_ONLY_MODE": {"type": "boolean", "default": "false", "group": "security"},
    # Logging
    "LOG_LEVEL": {"type": "select", "default": "INFO", "options": ["DEBUG", "INFO", "WARNING", "ERROR"], "group": "logging"},
}


def get_db_connection() -> sqlite3.Connection:
    """Get database connection"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_settings_db():
    """Initialize settings tables in database"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                is_secret BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Meta table for config version
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Initialize config version if not exists
        cursor.execute(
            "INSERT OR IGNORE INTO settings_meta (key, value) VALUES (?, ?)",
            ("config_version", "0")
        )

        conn.commit()
        logger.info("Settings database initialized")
    finally:
        conn.close()


def get_setting(key: str) -> Optional[str]:
    """Get a single setting value"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value, is_secret FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            return None

        value = row["value"]
        is_secret = row["is_secret"]

        # Decrypt secret values
        if is_secret and value:
            try:
                value = get_vault().decrypt(value)
            except Exception:
                # Migration: value might not be encrypted yet
                logger.warning(f"Could not decrypt setting '{key}', returning as-is (migration scenario)")

        return value
    finally:
        conn.close()


def get_all_settings(mask_secrets: bool = True) -> Dict[str, str]:
    """
    Get all settings as a dictionary

    Args:
        mask_secrets: If True, mask secret values with ********
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, is_secret FROM settings")
        rows = cursor.fetchall()

        result = {}
        for row in rows:
            key = row["key"]
            value = row["value"]
            is_secret = row["is_secret"]

            if mask_secrets and is_secret and value:
                result[key] = "********"
            else:
                # Decrypt secret values when not masking
                if is_secret and value:
                    try:
                        value = get_vault().decrypt(value)
                    except Exception:
                        # Migration: value might not be encrypted yet
                        logger.warning(f"Could not decrypt setting '{key}', returning as-is (migration scenario)")
                result[key] = value

        return result
    finally:
        conn.close()


def save_setting(key: str, value: str, is_secret: bool = None):
    """
    Save a single setting

    Args:
        key: Setting key
        value: Setting value
        is_secret: Whether this is a secret (auto-detected if None)
    """
    if is_secret is None:
        is_secret = key in SECRET_KEYS

    # Encrypt secret values before storing
    stored_value = value
    if is_secret and value:
        stored_value = get_vault().encrypt(value)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, is_secret, updated_at)
            VALUES (?, ?, ?, ?)
        """, (key, stored_value, is_secret, datetime.utcnow().isoformat()))
        conn.commit()
        logger.info(f"Setting saved: {key}")
    finally:
        conn.close()


def save_settings(settings: Dict[str, str], skip_masked: bool = True):
    """
    Save multiple settings

    Args:
        settings: Dictionary of key-value pairs
        skip_masked: If True, skip values that are "********" (masked passwords)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()

        for key, value in settings.items():
            # Skip masked values - don't overwrite existing passwords
            if skip_masked and value == "********":
                continue

            is_secret = key in SECRET_KEYS

            # Encrypt secret values before storing
            stored_value = value
            if is_secret and value:
                stored_value = get_vault().encrypt(value)

            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, is_secret, updated_at)
                VALUES (?, ?, ?, ?)
            """, (key, stored_value, is_secret, now))

        conn.commit()
        logger.info(f"Saved {len(settings)} settings")
    finally:
        conn.close()


def delete_all_settings():
    """Delete all settings (reset to .env defaults)"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM settings")
        conn.commit()
        logger.info("All settings deleted")
    finally:
        conn.close()


def get_config_version() -> int:
    """Get current config version from database"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings_meta WHERE key = 'config_version'")
        row = cursor.fetchone()
        return int(row["value"]) if row else 0
    finally:
        conn.close()


def increment_config_version() -> int:
    """Increment config version and return new value"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE settings_meta
            SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
            WHERE key = 'config_version'
        """)
        conn.commit()

        cursor.execute("SELECT value FROM settings_meta WHERE key = 'config_version'")
        row = cursor.fetchone()
        new_version = int(row["value"]) if row else 1
        logger.info(f"Config version incremented to {new_version}")
        return new_version
    finally:
        conn.close()
