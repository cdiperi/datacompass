"""Tests for AdapterRegistry."""

import pytest

from datacompass.core.adapters import (
    AdapterNotFoundError,
    AdapterRegistry,
    DatabricksAdapter,
    DatabricksConfig,
)


class TestAdapterRegistry:
    """Test cases for AdapterRegistry."""

    def test_databricks_is_registered(self):
        """Test that Databricks adapter is registered."""
        assert AdapterRegistry.is_registered("databricks")

    def test_list_adapters(self):
        """Test listing registered adapters."""
        adapters = AdapterRegistry.list_adapters()
        assert len(adapters) >= 1

        # Find databricks
        databricks = None
        for adapter in adapters:
            if adapter.source_type == "databricks":
                databricks = adapter
                break

        assert databricks is not None
        assert databricks.display_name == "Databricks Unity Catalog"
        assert "TABLE" in databricks.supported_object_types

    def test_get_adapter_info(self):
        """Test getting adapter info."""
        info = AdapterRegistry.get_adapter_info("databricks")
        assert info.source_type == "databricks"
        assert info.adapter_class == DatabricksAdapter
        assert info.config_schema == DatabricksConfig

    def test_get_adapter_not_found(self):
        """Test getting non-existent adapter."""
        with pytest.raises(AdapterNotFoundError) as exc_info:
            AdapterRegistry.get_adapter("nonexistent", {})

        assert "nonexistent" in str(exc_info.value)

    def test_get_config_schema(self):
        """Test getting config schema for adapter."""
        schema = AdapterRegistry.get_config_schema("databricks")
        assert schema == DatabricksConfig

    def test_available_types(self):
        """Test getting available adapter types."""
        types = AdapterRegistry.available_types()
        assert "databricks" in types

    def test_get_adapter_validates_config(self):
        """Test that get_adapter validates config against schema."""
        from pydantic import ValidationError

        # Missing required fields should raise ValidationError
        with pytest.raises(ValidationError):
            AdapterRegistry.get_adapter("databricks", {})

    def test_get_adapter_creates_instance(self):
        """Test that get_adapter creates adapter instance."""
        config = {
            "host": "test.azuredatabricks.net",
            "http_path": "/sql/1.0/warehouses/abc123",
            "catalog": "main",
            "auth_method": "personal_token",
            "access_token": "test-token",
        }
        adapter = AdapterRegistry.get_adapter("databricks", config)
        assert isinstance(adapter, DatabricksAdapter)
        assert adapter.config.host == "test.azuredatabricks.net"
