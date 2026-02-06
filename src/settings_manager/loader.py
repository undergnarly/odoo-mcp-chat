"""
Configuration loader
Loads settings from .env and SQLite, applies to os.environ
"""
import logging
import os
from typing import Dict

from src.settings_manager.settings_db import (
    init_settings_db,
    get_all_settings,
    get_config_version,
    SETTINGS_SCHEMA,
)

# Use standard logging to avoid circular import with src.utils.logging
logger = logging.getLogger(__name__)

# Global config version in memory (for hot-reload detection)
CONFIG_VERSION: int = 0


def load_config_from_db() -> Dict[str, str]:
    """
    Load configuration from database and apply to os.environ

    Priority:
    1. .env file (already loaded by dotenv)
    2. SQLite database (overrides .env)

    Returns:
        Dictionary of all settings (from both sources)
    """
    global CONFIG_VERSION

    # Initialize database tables
    init_settings_db()

    # Get settings from database (unmasked)
    db_settings = get_all_settings(mask_secrets=False)

    # Apply database settings to environment
    for key, value in db_settings.items():
        if value:  # Only set non-empty values
            os.environ[key] = value
            logger.debug(f"Applied setting from DB: {key}")

    # Update global config version
    CONFIG_VERSION = get_config_version()
    logger.info(f"Config loaded from DB, version: {CONFIG_VERSION}")

    # Build complete config from environment
    result = {}
    for key in SETTINGS_SCHEMA:
        result[key] = os.environ.get(key, SETTINGS_SCHEMA[key].get("default", ""))

    return result


def get_current_config_version() -> int:
    """Get current config version from memory"""
    return CONFIG_VERSION


def check_config_changed() -> bool:
    """
    Check if config has changed since last load

    Returns:
        True if config version in DB is different from memory
    """
    global CONFIG_VERSION
    db_version = get_config_version()
    return db_version != CONFIG_VERSION


def reload_if_changed() -> bool:
    """
    Reload config if it has changed

    Returns:
        True if config was reloaded
    """
    if check_config_changed():
        load_config_from_db()
        return True
    return False
