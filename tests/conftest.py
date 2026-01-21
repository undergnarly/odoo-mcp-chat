"""
Pytest configuration and fixtures for Odoo AI Agent tests.
"""
import os
import sys
import pytest
from typing import Optional
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


# ============================================
# Environment Fixtures
# ============================================

@pytest.fixture(scope="session")
def check_env_vars():
    """Check if required environment variables are set."""
    required_vars = ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"]
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        pytest.skip(f"Missing environment variables: {', '.join(missing)}")

    return True


@pytest.fixture(scope="session")
def check_llm_configured():
    """Check if LLM API key is configured."""
    has_llm = any([
        os.environ.get("ANTHROPIC_API_KEY"),
        os.environ.get("OPENAI_API_KEY"),
        os.environ.get("GOOGLE_API_KEY"),
    ])

    if not has_llm:
        pytest.skip("No LLM API key configured (ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY)")

    return True


def get_llm_api_key():
    """Get the available LLM API key."""
    return (
        os.environ.get("ANTHROPIC_API_KEY") or
        os.environ.get("OPENAI_API_KEY") or
        os.environ.get("GOOGLE_API_KEY")
    )


# ============================================
# Odoo Client Fixtures
# ============================================

@pytest.fixture(scope="session")
def odoo_client(check_env_vars):
    """Get a real Odoo client instance."""
    from odoo_mcp.odoo_client import get_odoo_client

    try:
        client = get_odoo_client()
        yield client
    except Exception as e:
        pytest.skip(f"Could not connect to Odoo: {e}")


@pytest.fixture
def mock_odoo_client():
    """Create a mock Odoo client for unit tests."""
    mock = MagicMock()
    mock.uid = 1
    mock.url = "http://test-odoo.com"
    mock.db = "test_db"

    # Mock get_models response
    mock.get_models.return_value = {
        "model_names": [
            "res.partner", "res.users", "sale.order", "purchase.order",
            "product.product", "product.template", "account.move",
            "stock.picking", "hr.employee", "crm.lead"
        ],
        "models_details": {
            "res.partner": {"name": "Contact"},
            "res.users": {"name": "Users"},
            "sale.order": {"name": "Sales Order"},
            "purchase.order": {"name": "Purchase Order"},
            "product.product": {"name": "Product"},
            "product.template": {"name": "Product Template"},
            "account.move": {"name": "Journal Entry"},
            "stock.picking": {"name": "Transfer"},
            "hr.employee": {"name": "Employee"},
            "crm.lead": {"name": "Lead/Opportunity"},
        }
    }

    # Mock search_read response
    mock.search_read.return_value = [
        {"id": 1, "name": "Test Record 1", "display_name": "Test Record 1"},
        {"id": 2, "name": "Test Record 2", "display_name": "Test Record 2"},
    ]

    # Mock get_model_info response
    mock.get_model_info.return_value = {
        "name": "Contact",
        "model": "res.partner",
    }

    # Mock get_model_fields response
    mock.get_model_fields.return_value = {
        "id": {"type": "integer", "string": "ID"},
        "name": {"type": "char", "string": "Name", "required": True},
        "email": {"type": "char", "string": "Email"},
        "phone": {"type": "char", "string": "Phone"},
    }

    # Mock execute_method
    mock.execute_method.return_value = True

    return mock


# ============================================
# Discovery Service Fixtures
# ============================================

@pytest.fixture
def discovery_service(mock_odoo_client):
    """Create a discovery service with mock client."""
    from src.extensions.discovery import OdooModelDiscovery
    return OdooModelDiscovery(mock_odoo_client, cache_ttl=60)


@pytest.fixture
def real_discovery_service(odoo_client):
    """Create a discovery service with real Odoo client."""
    from src.extensions.discovery import OdooModelDiscovery
    return OdooModelDiscovery(odoo_client, cache_ttl=300)


# ============================================
# Agent Fixtures
# ============================================

@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    mock = AsyncMock()
    mock.ainvoke.return_value = MagicMock(
        content='{"intent": "QUERY", "model": "res.partner", "confidence": 0.9, "reasoning": "User wants contacts", "parameters": {"filters": [], "limit": 10}}'
    )
    return mock


@pytest.fixture
def agent_with_mocks(mock_odoo_client, discovery_service, monkeypatch):
    """Create an agent with mocked dependencies."""
    from src.agent.langchain_agent import OdooAgent
    from src.config import Settings

    # Mock settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_provider = "anthropic"
    mock_settings.llm_model = "claude-sonnet-4-20250514"
    mock_settings.llm_temperature = 0.0
    mock_settings.anthropic_api_key = "test-key"
    mock_settings.anthropic_base_url = None
    mock_settings.read_only_mode = False
    mock_settings.model_cache_ttl = 300

    monkeypatch.setattr("src.agent.langchain_agent.get_settings", lambda: mock_settings)

    # We can't fully mock the LLM without more complex setup, so we skip if no API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set for agent tests")

    return OdooAgent(mock_odoo_client, discovery_service)


# ============================================
# Settings Fixtures
# ============================================

@pytest.fixture
def settings():
    """Get application settings."""
    from src.config import get_settings
    return get_settings()


@pytest.fixture
def test_settings(monkeypatch):
    """Create test settings with controlled values."""
    monkeypatch.setenv("ODOO_URL", "http://test-odoo.com")
    monkeypatch.setenv("ODOO_DB", "test_db")
    monkeypatch.setenv("ODOO_USERNAME", "admin")
    monkeypatch.setenv("ODOO_PASSWORD", "admin")
    monkeypatch.setenv("READ_ONLY_MODE", "true")

    from src.config import reload_settings
    return reload_settings()
