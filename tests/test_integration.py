"""
Integration tests for the full system.

These tests verify that all components work together correctly.
Requires valid Odoo credentials and LLM API key.
"""
import pytest


class TestFullSystemIntegration:
    """Test full system integration with real Odoo."""

    @pytest.mark.asyncio
    async def test_agent_processes_query_message(self, odoo_client, check_llm_configured):
        """Test that agent can process a query message end-to-end."""
        from src.extensions.discovery import OdooModelDiscovery
        from src.agent.langchain_agent import OdooAgent

        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        agent = OdooAgent(odoo_client, discovery)

        # Process a simple query
        response = await agent.process_message("Show me contacts")

        assert response is not None
        assert "type" in response
        # Should either return query_result or clarification
        assert response["type"] in ["query_result", "clarification", "error", "default"]

    @pytest.mark.asyncio
    async def test_agent_processes_metadata_request(self, odoo_client, check_llm_configured):
        """Test that agent can handle metadata requests."""
        from src.extensions.discovery import OdooModelDiscovery
        from src.agent.langchain_agent import OdooAgent

        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        agent = OdooAgent(odoo_client, discovery)

        # Process metadata request
        response = await agent.process_message("What can you do?")

        assert response is not None
        assert "type" in response
        # Should mention capabilities or models
        content = response.get("content", "")
        # The response should contain some useful information
        assert len(content) > 50

    @pytest.mark.asyncio
    async def test_agent_conversation_history(self, odoo_client, check_llm_configured):
        """Test that agent maintains conversation history."""
        from src.extensions.discovery import OdooModelDiscovery
        from src.agent.langchain_agent import OdooAgent

        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        agent = OdooAgent(odoo_client, discovery)

        # First message
        await agent.process_message("Hello")

        # Check history
        history = agent.get_history()
        assert len(history) >= 2  # User message + assistant response

        # Second message
        await agent.process_message("Show me models")

        history = agent.get_history()
        assert len(history) >= 4  # Two exchanges


class TestDiscoveryIntegration:
    """Test discovery service integration with real Odoo."""

    def test_discovery_finds_core_models(self, odoo_client):
        """Test that discovery finds core Odoo models."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        models = discovery.get_all_models()

        core_models = ["res.partner", "res.users", "res.company"]
        for model in core_models:
            assert model in models, f"Should find core model: {model}"

    def test_discovery_gets_partner_fields(self, odoo_client):
        """Test that discovery gets fields for res.partner."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        fields = discovery.get_model_fields("res.partner")

        assert fields is not None
        assert "name" in fields
        assert "email" in fields
        assert "phone" in fields

    def test_discovery_model_summary(self, odoo_client):
        """Test that discovery gets model summary."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        summary = discovery.get_model_summary("res.partner")

        assert summary is not None
        assert summary.get("model") == "res.partner"
        assert summary.get("total_fields") > 0


class TestSafetyIntegration:
    """Test safety layer integration."""

    def test_safety_validator_initialization(self):
        """Test that safety validator initializes correctly."""
        from src.extensions.safety import SafetyValidator

        validator = SafetyValidator()

        assert validator is not None

    def test_safety_danger_levels(self):
        """Test danger level classification."""
        from src.extensions.safety import DangerLevel

        # Check all danger levels exist
        assert DangerLevel.SAFE is not None
        assert DangerLevel.LOW is not None
        assert DangerLevel.MEDIUM is not None
        assert DangerLevel.HIGH is not None
        assert DangerLevel.DESTRUCTIVE is not None


class TestAPIIntegration:
    """Test REST API integration."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, odoo_client):
        """Test health check returns correct status."""
        from fastapi.testclient import TestClient
        from src.api.rest import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "odoo_connected" in data
        assert "llm_configured" in data

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """Test root endpoint returns API info."""
        from fastapi.testclient import TestClient
        from src.api.rest import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_models_endpoint_requires_auth(self):
        """Test that models endpoint requires authentication."""
        from fastapi.testclient import TestClient
        from src.api.rest import app

        client = TestClient(app)
        response = client.get("/models")

        # Should require API key
        assert response.status_code in [401, 403]


class TestReadOnlyMode:
    """Test read-only mode functionality."""

    @pytest.mark.asyncio
    async def test_create_blocked_in_readonly(self, mock_odoo_client, discovery_service, monkeypatch):
        """Test that create operations are blocked in read-only mode."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent
        from src.config import get_settings

        settings = get_settings()
        original_read_only = settings.read_only_mode
        settings.read_only_mode = True  # Enable read-only

        try:
            agent = OdooAgent(mock_odoo_client, discovery_service)
            response = await agent._handle_create("res.partner", {"values": {"name": "Test"}}, "Create contact")

            assert response["type"] == "error"
            assert "Read-Only" in response["content"] or "read-only" in response["content"].lower()
        finally:
            settings.read_only_mode = original_read_only

    @pytest.mark.asyncio
    async def test_update_blocked_in_readonly(self, mock_odoo_client, discovery_service, monkeypatch):
        """Test that update operations are blocked in read-only mode."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent
        from src.config import get_settings

        settings = get_settings()
        original_read_only = settings.read_only_mode
        settings.read_only_mode = True

        try:
            agent = OdooAgent(mock_odoo_client, discovery_service)
            response = await agent._handle_update("res.partner", {"record_id": 1, "values": {"name": "Test"}}, "Update contact")

            assert response["type"] == "error"
            assert "Read-Only" in response["content"] or "read-only" in response["content"].lower()
        finally:
            settings.read_only_mode = original_read_only

    @pytest.mark.asyncio
    async def test_delete_blocked_in_readonly(self, mock_odoo_client, discovery_service, monkeypatch):
        """Test that delete operations are blocked in read-only mode."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent
        from src.config import get_settings

        settings = get_settings()
        original_read_only = settings.read_only_mode
        settings.read_only_mode = True

        try:
            agent = OdooAgent(mock_odoo_client, discovery_service)
            response = await agent._handle_delete("res.partner", {"record_id": 1}, "Delete contact")

            assert response["type"] == "error"
            assert "Read-Only" in response["content"] or "read-only" in response["content"].lower()
        finally:
            settings.read_only_mode = original_read_only
