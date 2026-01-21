"""
Configuration management for Odoo AI Agent
"""
import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Odoo Configuration
    odoo_url: str = Field(default="", alias="ODOO_URL")
    odoo_db: str = Field(default="", alias="ODOO_DB")
    odoo_username: str = Field(default="", alias="ODOO_USERNAME")
    odoo_password: str = Field(default="", alias="ODOO_PASSWORD")
    odoo_timeout: int = Field(default=30, alias="ODOO_TIMEOUT")
    odoo_verify_ssl: bool = Field(default=True, alias="ODOO_VERIFY_SSL")

    # LLM Configuration
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_base_url: Optional[str] = Field(default=None, alias="ANTHROPIC_BASE_URL")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")
    llm_model: str = Field(default="claude-sonnet-4-20250514", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")

    # Service Configuration
    service_host: str = Field(default="0.0.0.0", alias="SERVICE_HOST")
    service_port: int = Field(default=8000, alias="SERVICE_PORT")
    chainlit_port: int = Field(default=8080, alias="CHAINLIT_PORT")

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    model_cache_ttl: int = Field(default=300, alias="MODEL_CACHE_TTL")

    # Security
    api_key_enabled: bool = Field(default=True, alias="API_KEY_ENABLED")
    admin_api_key: Optional[str] = Field(default=None, alias="ADMIN_API_KEY")
    read_only_mode: bool = Field(default=False, alias="READ_ONLY_MODE")
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")

    # Features
    enable_file_uploads: bool = Field(default=True, alias="ENABLE_FILE_UPLOADS")
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/odoo_agent.log", alias="LOG_FILE")
    audit_log: str = Field(default="logs/actions_audit.log", alias="AUDIT_LOG")

    @property
    def logs_dir(self) -> Path:
        """Get logs directory path"""
        return Path(self.log_file).parent

    def ensure_directories(self):
        """Ensure required directories exist"""
        self.logs_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment"""
    global _settings
    _settings = Settings()
    _settings.ensure_directories()
    return _settings
