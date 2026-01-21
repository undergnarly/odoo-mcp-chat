"""
Tests for configuration management.

Tests the settings and configuration loading.
"""
import pytest
import os


class TestSettings:
    """Test Settings class."""

    def test_settings_loads(self):
        """Test that settings can be loaded."""
        from src.config import get_settings

        settings = get_settings()

        assert settings is not None

    def test_settings_has_odoo_fields(self):
        """Test that settings has Odoo configuration fields."""
        from src.config import Settings

        # Check that the class has expected fields
        assert hasattr(Settings, 'model_fields')
        fields = Settings.model_fields

        odoo_fields = ['odoo_url', 'odoo_db', 'odoo_username', 'odoo_password']
        for field in odoo_fields:
            assert field in fields, f"Settings should have {field} field"

    def test_settings_has_llm_fields(self):
        """Test that settings has LLM configuration fields."""
        from src.config import Settings

        fields = Settings.model_fields

        llm_fields = ['anthropic_api_key', 'openai_api_key', 'google_api_key', 'llm_provider', 'llm_model']
        for field in llm_fields:
            assert field in fields, f"Settings should have {field} field"

    def test_settings_has_security_fields(self):
        """Test that settings has security configuration fields."""
        from src.config import Settings

        fields = Settings.model_fields

        security_fields = ['api_key_enabled', 'admin_api_key', 'read_only_mode', 'rate_limit_per_minute']
        for field in security_fields:
            assert field in fields, f"Settings should have {field} field"

    def test_settings_defaults(self, monkeypatch):
        """Test that settings has reasonable defaults."""
        # Clear environment variables that would override defaults
        env_vars_to_clear = [
            "LLM_PROVIDER", "LLM_TEMPERATURE", "SERVICE_PORT",
            "CHAINLIT_PORT", "MODEL_CACHE_TTL"
        ]
        for var in env_vars_to_clear:
            monkeypatch.delenv(var, raising=False)

        from src.config import Settings

        # Create settings without any env vars (using test isolation)
        settings = Settings(
            _env_file=None,  # Don't load .env file
        )

        # Check defaults
        assert settings.llm_provider == "anthropic"
        assert settings.llm_temperature == 0.0
        assert settings.service_port == 8000
        assert settings.chainlit_port == 8080
        assert settings.model_cache_ttl == 300

    def test_settings_reload(self, monkeypatch):
        """Test that settings can be reloaded."""
        from src.config import reload_settings

        monkeypatch.setenv("ODOO_URL", "http://test-reload.com")

        settings = reload_settings()

        assert settings.odoo_url == "http://test-reload.com"

    def test_settings_logs_directory(self, test_settings):
        """Test that logs directory is created."""
        from pathlib import Path

        logs_dir = test_settings.logs_dir

        assert logs_dir is not None
        assert isinstance(logs_dir, Path)


class TestSettingsFromEnv:
    """Test settings loaded from environment."""

    def test_odoo_url_from_env(self, monkeypatch):
        """Test ODOO_URL loaded from environment."""
        from src.config import reload_settings

        monkeypatch.setenv("ODOO_URL", "https://my-odoo.example.com")
        settings = reload_settings()

        assert settings.odoo_url == "https://my-odoo.example.com"

    def test_llm_provider_from_env(self, monkeypatch):
        """Test LLM_PROVIDER loaded from environment."""
        from src.config import reload_settings

        monkeypatch.setenv("LLM_PROVIDER", "openai")
        settings = reload_settings()

        assert settings.llm_provider == "openai"

    def test_read_only_mode_from_env(self, monkeypatch):
        """Test READ_ONLY_MODE loaded from environment."""
        from src.config import reload_settings

        monkeypatch.setenv("READ_ONLY_MODE", "true")
        settings = reload_settings()

        assert settings.read_only_mode is True

    def test_rate_limits_from_env(self, monkeypatch):
        """Test rate limits loaded from environment."""
        from src.config import reload_settings

        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "50")
        monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "500")
        settings = reload_settings()

        assert settings.rate_limit_per_minute == 50
        assert settings.rate_limit_per_hour == 500
