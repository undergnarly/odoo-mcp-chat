"""
Tests for model discovery service.

Tests the dynamic model discovery functionality.
"""
import pytest
from unittest.mock import MagicMock


class TestOdooModelDiscovery:
    """Test OdooModelDiscovery service."""

    def test_discovery_initialization(self, mock_odoo_client):
        """Test discovery service initialization."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)

        assert discovery is not None
        assert discovery.cache_ttl == 60

    def test_discovery_get_all_models(self, mock_odoo_client):
        """Test getting all models."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)
        models = discovery.get_all_models()

        assert models is not None
        assert isinstance(models, dict)
        mock_odoo_client.get_models.assert_called()

    def test_discovery_get_model_fields(self, mock_odoo_client):
        """Test getting fields for a model."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)
        fields = discovery.get_model_fields("res.partner")

        assert fields is not None
        assert isinstance(fields, dict)
        mock_odoo_client.get_model_fields.assert_called_with("res.partner")

    def test_discovery_caching(self, mock_odoo_client):
        """Test that discovery results are cached."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)

        # First call
        fields1 = discovery.get_model_fields("res.partner")
        # Second call should use cache
        fields2 = discovery.get_model_fields("res.partner")

        assert fields1 == fields2
        # Should only call Odoo once due to caching
        assert mock_odoo_client.get_model_fields.call_count == 1

    def test_discovery_get_model_methods(self, mock_odoo_client):
        """Test getting methods for a model."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)
        methods = discovery.get_model_methods("sale.order")

        assert methods is not None
        assert isinstance(methods, list)
        # Should include common methods
        assert "create" in methods
        assert "write" in methods
        # Should include model-specific methods
        assert "action_confirm" in methods

    def test_discovery_search_models_by_keyword(self, mock_odoo_client):
        """Test searching models by keyword."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)
        matching = discovery.search_models_by_keyword("partner")

        assert matching is not None
        assert isinstance(matching, list)

    def test_discovery_get_model_summary(self, mock_odoo_client):
        """Test getting model summary."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)
        # First get models so cache is populated
        discovery.get_all_models()
        summary = discovery.get_model_summary("res.partner")

        assert summary is not None
        assert isinstance(summary, dict)

    def test_discovery_refresh_cache(self, mock_odoo_client):
        """Test cache refresh."""
        from src.extensions.discovery import OdooModelDiscovery

        discovery = OdooModelDiscovery(mock_odoo_client, cache_ttl=60)

        # First call
        discovery.get_model_fields("res.partner")
        # Refresh cache
        discovery.refresh_cache()
        # Call again - should call Odoo again
        discovery.get_model_fields("res.partner")

        assert mock_odoo_client.get_model_fields.call_count == 2


class TestDiscoveryWithRealOdoo:
    """Test discovery with real Odoo connection."""

    def test_real_get_all_models(self, real_discovery_service):
        """Test getting all models from real Odoo."""
        models = real_discovery_service.get_all_models()

        assert models is not None
        assert isinstance(models, dict)
        assert len(models) > 0
        # Check that res.partner is in the keys
        assert "res.partner" in models

    def test_real_get_model_fields(self, real_discovery_service):
        """Test getting fields from real Odoo."""
        fields = real_discovery_service.get_model_fields("res.partner")

        assert fields is not None
        assert isinstance(fields, dict)
        assert "name" in fields
        assert "email" in fields

    def test_real_model_summary(self, real_discovery_service):
        """Test getting model summary from real Odoo."""
        summary = real_discovery_service.get_model_summary("res.partner")

        assert summary is not None
        assert "error" not in summary
        assert summary.get("model") == "res.partner"
        assert summary.get("total_fields") > 0

    def test_real_search_models(self, real_discovery_service):
        """Test searching models in real Odoo."""
        matching = real_discovery_service.search_models_by_keyword("sale")

        assert matching is not None
        assert isinstance(matching, list)
        # Should find at least sale.order
        assert any("sale" in m for m in matching)
