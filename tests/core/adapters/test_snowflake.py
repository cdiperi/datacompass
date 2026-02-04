"""Tests for Snowflake adapter."""

import os

import pytest
from pydantic import ValidationError

from datacompass.core.adapters import (
    AdapterRegistry,
    SnowflakeAdapter,
    SnowflakeConfig,
)


class TestSnowflakeConfig:
    """Test cases for SnowflakeConfig."""

    def test_valid_config(self):
        """Test creating valid config."""
        config = SnowflakeConfig(
            account="alxxhtq-tk90121",
            warehouse="COMPUTE_WH",
            database="MY_DATABASE",
            username="my_user",
            password="my_password",
        )
        assert config.account == "alxxhtq-tk90121"
        assert config.warehouse == "COMPUTE_WH"
        assert config.database == "MY_DATABASE"
        assert config.username == "my_user"
        assert config.password.get_secret_value() == "my_password"
        assert config.role is None
        assert config.exclude_schemas == ["INFORMATION_SCHEMA"]

    def test_config_with_role(self):
        """Test config with optional role."""
        config = SnowflakeConfig(
            account="test-account",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
            role="ANALYST",
        )
        assert config.role == "ANALYST"

    def test_config_with_schema_filter(self):
        """Test config with schema filter."""
        config = SnowflakeConfig(
            account="test-account",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
            schema_filter="^(SALES|ANALYTICS)$",
            exclude_schemas=["INFORMATION_SCHEMA", "ACCOUNT_USAGE"],
        )
        assert config.schema_filter == "^(SALES|ANALYTICS)$"
        assert "ACCOUNT_USAGE" in config.exclude_schemas

    def test_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            SnowflakeConfig(
                warehouse="WH",
                database="DB",
                username="user",
                password="pass",
            )

    def test_timeout_validation(self):
        """Test timeout field validation."""
        config = SnowflakeConfig(
            account="test-account",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
            connect_timeout=60,
            query_timeout=600,
        )
        assert config.connect_timeout == 60
        assert config.query_timeout == 600

    def test_invalid_timeout(self):
        """Test that invalid timeout raises ValidationError."""
        with pytest.raises(ValidationError):
            SnowflakeConfig(
                account="test-account",
                warehouse="WH",
                database="DB",
                username="user",
                password="pass",
                connect_timeout=0,  # Must be >= 1
            )


class TestSnowflakeAdapterRegistry:
    """Test Snowflake adapter registration."""

    def test_snowflake_is_registered(self):
        """Test that Snowflake adapter is registered."""
        assert AdapterRegistry.is_registered("snowflake")

    def test_get_adapter_info(self):
        """Test getting adapter info."""
        info = AdapterRegistry.get_adapter_info("snowflake")
        assert info.source_type == "snowflake"
        assert info.display_name == "Snowflake"
        assert info.adapter_class == SnowflakeAdapter
        assert info.config_schema == SnowflakeConfig

    def test_supported_object_types(self):
        """Test that supported object types are correct."""
        info = AdapterRegistry.get_adapter_info("snowflake")
        assert "TABLE" in info.supported_object_types
        assert "VIEW" in info.supported_object_types
        assert "MATERIALIZED VIEW" in info.supported_object_types
        assert "DYNAMIC TABLE" in info.supported_object_types

    def test_get_config_schema(self):
        """Test getting config schema."""
        schema = AdapterRegistry.get_config_schema("snowflake")
        assert schema == SnowflakeConfig

    def test_available_types_includes_snowflake(self):
        """Test that snowflake is in available types."""
        types = AdapterRegistry.available_types()
        assert "snowflake" in types

    def test_get_adapter_validates_config(self):
        """Test that get_adapter validates config against schema."""
        with pytest.raises(ValidationError):
            AdapterRegistry.get_adapter("snowflake", {})

    def test_get_adapter_creates_instance(self):
        """Test that get_adapter creates adapter instance."""
        config = {
            "account": "test-account",
            "warehouse": "COMPUTE_WH",
            "database": "MY_DB",
            "username": "user",
            "password": "secret",
        }
        adapter = AdapterRegistry.get_adapter("snowflake", config)
        assert isinstance(adapter, SnowflakeAdapter)
        assert adapter.config.account == "test-account"


class TestSnowflakeAdapterUnit:
    """Unit tests for SnowflakeAdapter (no real connection)."""

    def test_normalize_object_type(self):
        """Test object type normalization."""
        config = SnowflakeConfig(
            account="test",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
        )
        adapter = SnowflakeAdapter(config)

        assert adapter._normalize_object_type("BASE TABLE") == "TABLE"
        assert adapter._normalize_object_type("TABLE") == "TABLE"
        assert adapter._normalize_object_type("VIEW") == "VIEW"
        assert adapter._normalize_object_type("MATERIALIZED VIEW") == "MATERIALIZED VIEW"
        assert adapter._normalize_object_type("DYNAMIC TABLE") == "DYNAMIC TABLE"
        assert adapter._normalize_object_type("UNKNOWN") == "UNKNOWN"

    def test_build_schema_filter_empty(self):
        """Test schema filter with no filters."""
        config = SnowflakeConfig(
            account="test",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
            exclude_schemas=[],
            schema_filter=None,
        )
        adapter = SnowflakeAdapter(config)
        assert adapter._build_schema_filter() == ""

    def test_build_schema_filter_exclude_only(self):
        """Test schema filter with exclude only."""
        config = SnowflakeConfig(
            account="test",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
            exclude_schemas=["INFORMATION_SCHEMA", "ACCOUNT_USAGE"],
        )
        adapter = SnowflakeAdapter(config)
        result = adapter._build_schema_filter()
        assert "NOT IN" in result
        assert "INFORMATION_SCHEMA" in result
        assert "ACCOUNT_USAGE" in result

    def test_build_schema_filter_with_regex(self):
        """Test schema filter with regex pattern."""
        config = SnowflakeConfig(
            account="test",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
            schema_filter="^SALES.*",
        )
        adapter = SnowflakeAdapter(config)
        result = adapter._build_schema_filter()
        assert "RLIKE" in result
        assert "^SALES.*" in result

    def test_format_data_type_simple(self):
        """Test data type formatting for simple types."""
        config = SnowflakeConfig(
            account="test",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
        )
        adapter = SnowflakeAdapter(config)

        row = {"DATA_TYPE": "VARCHAR", "CHAR_MAX_LENGTH": None, "NUMERIC_PRECISION": None, "NUMERIC_SCALE": None}
        assert adapter._format_data_type(row) == "VARCHAR"

    def test_format_data_type_with_length(self):
        """Test data type formatting with character length."""
        config = SnowflakeConfig(
            account="test",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
        )
        adapter = SnowflakeAdapter(config)

        row = {"DATA_TYPE": "VARCHAR", "CHAR_MAX_LENGTH": 255, "NUMERIC_PRECISION": None, "NUMERIC_SCALE": None}
        assert adapter._format_data_type(row) == "VARCHAR(255)"

    def test_format_data_type_with_precision_and_scale(self):
        """Test data type formatting with numeric precision and scale."""
        config = SnowflakeConfig(
            account="test",
            warehouse="WH",
            database="DB",
            username="user",
            password="pass",
        )
        adapter = SnowflakeAdapter(config)

        row = {"DATA_TYPE": "NUMBER", "CHAR_MAX_LENGTH": None, "NUMERIC_PRECISION": 10, "NUMERIC_SCALE": 2}
        assert adapter._format_data_type(row) == "NUMBER(10,2)"


# Integration tests - skipped if no Snowflake credentials
SNOWFLAKE_ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.environ.get("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD")
SNOWFLAKE_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
SNOWFLAKE_DATABASE = os.environ.get("SNOWFLAKE_DATABASE", "SNOWFLAKE_SAMPLE_DATA")

HAS_SNOWFLAKE_CREDENTIALS = all([SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD])


@pytest.mark.skipif(
    not HAS_SNOWFLAKE_CREDENTIALS,
    reason="Snowflake credentials not configured (set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD)",
)
class TestSnowflakeAdapterIntegration:
    """Integration tests for Snowflake adapter (requires real connection)."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with test credentials."""
        config = SnowflakeConfig(
            account=SNOWFLAKE_ACCOUNT,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            username=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
        )
        return SnowflakeAdapter(config)

    async def test_connect_and_disconnect(self, adapter):
        """Test connecting and disconnecting."""
        await adapter.connect()
        assert adapter._connection is not None
        await adapter.disconnect()
        assert adapter._connection is None

    async def test_test_connection(self, adapter):
        """Test the test_connection method."""
        await adapter.connect()
        try:
            result = await adapter.test_connection()
            assert result is True
        finally:
            await adapter.disconnect()

    async def test_execute_query(self, adapter):
        """Test executing a simple query."""
        await adapter.connect()
        try:
            results = await adapter.execute_query("SELECT 1 AS test_col")
            assert len(results) == 1
            assert results[0]["TEST_COL"] == 1
        finally:
            await adapter.disconnect()

    async def test_get_objects(self, adapter):
        """Test fetching objects from Snowflake."""
        await adapter.connect()
        try:
            objects = await adapter.get_objects()
            assert isinstance(objects, list)
            # SNOWFLAKE_SAMPLE_DATA should have tables
            if objects:
                obj = objects[0]
                assert "schema_name" in obj
                assert "object_name" in obj
                assert "object_type" in obj
                assert "source_metadata" in obj
        finally:
            await adapter.disconnect()

    async def test_get_columns(self, adapter):
        """Test fetching columns for objects."""
        await adapter.connect()
        try:
            # First get some objects
            objects = await adapter.get_objects(object_types=["TABLE"])
            if objects:
                # Get columns for first object
                obj = objects[0]
                columns = await adapter.get_columns([
                    (obj["schema_name"], obj["object_name"])
                ])
                assert isinstance(columns, list)
                if columns:
                    col = columns[0]
                    assert "schema_name" in col
                    assert "object_name" in col
                    assert "column_name" in col
                    assert "position" in col
                    assert "source_metadata" in col
        finally:
            await adapter.disconnect()

    async def test_context_manager(self, adapter):
        """Test using adapter as async context manager."""
        async with adapter:
            result = await adapter.test_connection()
            assert result is True
        assert adapter._connection is None
