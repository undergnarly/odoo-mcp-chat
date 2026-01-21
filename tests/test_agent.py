"""
Tests for the LangChain agent and intent routing.

Tests the agent's ability to understand user intent and route to appropriate operations.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestIntentRouter:
    """Test intent routing functionality."""

    def test_router_initialization(self, mock_odoo_client):
        """Test that IntentRouter initializes correctly."""
        from src.agent.langchain_agent import IntentRouter

        mock_llm = MagicMock()
        router = IntentRouter(mock_llm, mock_odoo_client)

        assert router is not None
        assert router.llm == mock_llm
        assert router.odoo == mock_odoo_client

    def test_get_available_models_info(self, mock_odoo_client):
        """Test dynamic model info generation."""
        from src.agent.langchain_agent import IntentRouter

        mock_llm = MagicMock()
        router = IntentRouter(mock_llm, mock_odoo_client)

        models_info = router._get_available_models_info()

        assert models_info is not None
        assert isinstance(models_info, str)
        assert "res.partner" in models_info
        assert "Contact" in models_info

    def test_models_info_caching(self, mock_odoo_client):
        """Test that models info is cached."""
        from src.agent.langchain_agent import IntentRouter

        mock_llm = MagicMock()
        router = IntentRouter(mock_llm, mock_odoo_client)

        # First call
        info1 = router._get_available_models_info()
        # Second call should use cache
        info2 = router._get_available_models_info()

        assert info1 == info2
        # get_models should only be called once due to caching
        assert mock_odoo_client.get_models.call_count == 1


class TestOdooAgent:
    """Test OdooAgent functionality."""

    def test_agent_initialization_requires_llm_key(self, mock_odoo_client, discovery_service, monkeypatch):
        """Test that agent requires LLM API key."""
        from src.agent.langchain_agent import OdooAgent
        from src.config import Settings

        mock_settings = MagicMock(spec=Settings)
        mock_settings.llm_provider = "anthropic"
        mock_settings.anthropic_api_key = None  # No key
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None

        monkeypatch.setattr("src.agent.langchain_agent.get_settings", lambda: mock_settings)

        with pytest.raises(ValueError, match="API_KEY is required"):
            OdooAgent(mock_odoo_client, discovery_service)

    def test_agent_clear_history(self, mock_odoo_client, discovery_service, monkeypatch):
        """Test clearing conversation history."""
        import os
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        agent.history = [{"role": "user", "content": "test"}]

        agent.clear_history()

        assert agent.history == []

    def test_agent_get_history(self, mock_odoo_client, discovery_service, monkeypatch):
        """Test getting conversation history."""
        import os
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        test_history = [{"role": "user", "content": "test"}]
        agent.history = test_history

        assert agent.get_history() == test_history


class TestAgentHandlers:
    """Test agent handler methods."""

    @pytest.mark.asyncio
    async def test_handle_metadata_returns_dynamic_info(self, mock_odoo_client, discovery_service):
        """Test that metadata handler returns dynamic model information."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        response = await agent._handle_metadata()

        assert response is not None
        assert response.get("type") == "metadata"
        assert "content" in response
        assert "10" in response["content"]  # Should mention model count (mock has 10 models)

    @pytest.mark.asyncio
    async def test_handle_query_without_model(self, mock_odoo_client, discovery_service):
        """Test query handler asks for clarification when model is not specified."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        response = await agent._handle_query(None, {}, "show me data")

        assert response is not None
        assert response.get("type") == "clarification"

    @pytest.mark.asyncio
    async def test_handle_query_with_model(self, mock_odoo_client, discovery_service):
        """Test query handler executes search when model is specified."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        response = await agent._handle_query("res.partner", {"limit": 5}, "show me contacts")

        assert response is not None
        assert response.get("type") == "query_result"
        assert response.get("model") == "res.partner"
        mock_odoo_client.search_read.assert_called()


class TestExecuteConfirmedAction:
    """Test action execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_create_action(self, mock_odoo_client, discovery_service):
        """Test executing a create action."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        mock_odoo_client.execute_method.return_value = 123  # New record ID

        agent = OdooAgent(mock_odoo_client, discovery_service)
        result = await agent.execute_confirmed_action({
            "operation": "create",
            "model": "res.partner",
            "values": {"name": "Test Partner"},
        })

        assert result["success"] is True
        assert result["record_id"] == 123
        mock_odoo_client.execute_method.assert_called_with(
            "res.partner", "create", [{"name": "Test Partner"}]
        )

    @pytest.mark.asyncio
    async def test_execute_update_action(self, mock_odoo_client, discovery_service):
        """Test executing an update action."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        result = await agent.execute_confirmed_action({
            "operation": "update",
            "model": "res.partner",
            "record_id": 1,
            "values": {"name": "Updated Name"},
        })

        assert result["success"] is True
        mock_odoo_client.execute_method.assert_called_with(
            "res.partner", "write", [[1], {"name": "Updated Name"}]
        )

    @pytest.mark.asyncio
    async def test_execute_delete_action(self, mock_odoo_client, discovery_service):
        """Test executing a delete action."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        result = await agent.execute_confirmed_action({
            "operation": "delete",
            "model": "res.partner",
            "record_id": 1,
        })

        assert result["success"] is True
        mock_odoo_client.execute_method.assert_called_with(
            "res.partner", "unlink", [[1]]
        )

    @pytest.mark.asyncio
    async def test_execute_workflow_action(self, mock_odoo_client, discovery_service):
        """Test executing a workflow action."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        result = await agent.execute_confirmed_action({
            "operation": "action",
            "model": "sale.order",
            "record_id": 1,
            "method": "action_confirm",
        })

        assert result["success"] is True
        mock_odoo_client.execute_method.assert_called_with(
            "sale.order", "action_confirm", [[1]]
        )

    @pytest.mark.asyncio
    async def test_execute_action_missing_params(self, mock_odoo_client, discovery_service):
        """Test that missing parameters return error."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)

        # Missing model
        result = await agent.execute_confirmed_action({
            "operation": "create",
            "values": {"name": "Test"},
        })
        assert result["success"] is False

        # Missing values for create
        result = await agent.execute_confirmed_action({
            "operation": "create",
            "model": "res.partner",
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_action_unknown_operation(self, mock_odoo_client, discovery_service):
        """Test that unknown operation returns error."""
        from tests.conftest import get_llm_api_key
        if not get_llm_api_key():
            pytest.skip("No LLM API key configured")

        from src.agent.langchain_agent import OdooAgent

        agent = OdooAgent(mock_odoo_client, discovery_service)
        result = await agent.execute_confirmed_action({
            "operation": "unknown_operation",
            "model": "res.partner",
        })

        assert result["success"] is False
        assert "Unknown operation" in result["content"]
