"""
Configuration management module
Handles settings storage in SQLite and hot-reload support
"""
from src.settings_manager.settings_db import (
    init_settings_db,
    get_setting,
    get_all_settings,
    save_setting,
    save_settings,
    delete_all_settings,
    get_config_version,
    increment_config_version,
)
from src.settings_manager.loader import (
    load_config_from_db,
    get_current_config_version,
    CONFIG_VERSION,
)

__all__ = [
    "init_settings_db",
    "get_setting",
    "get_all_settings",
    "save_setting",
    "save_settings",
    "delete_all_settings",
    "get_config_version",
    "increment_config_version",
    "load_config_from_db",
    "get_current_config_version",
    "CONFIG_VERSION",
]
