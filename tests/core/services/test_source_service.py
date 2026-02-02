"""Tests for SourceService."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from datacompass.core.adapters import AdapterNotFoundError
from datacompass.core.services import (
    SourceExistsError,
    SourceNotFoundError,
    SourceService,
)


class TestSourceService:
    """Test cases for SourceService."""

    def test_add_source(self, test_db: Session, sample_config_file: Path):
        """Test adding a data source."""
        service = SourceService(test_db)

        source = service.add_source(
            name="test-prod",
            source_type="databricks",
            config_path=sample_config_file,
            display_name="Production Databricks",
        )
        test_db.commit()

        assert source.name == "test-prod"
        assert source.source_type == "databricks"
        assert source.display_name == "Production Databricks"
        assert source.connection_info["host"] == "test-workspace.azuredatabricks.net"

    def test_add_source_duplicate_raises(self, test_db: Session, sample_config_file: Path):
        """Test that adding duplicate source raises error."""
        service = SourceService(test_db)

        service.add_source(
            name="test",
            source_type="databricks",
            config_path=sample_config_file,
        )
        test_db.commit()

        with pytest.raises(SourceExistsError):
            service.add_source(
                name="test",
                source_type="databricks",
                config_path=sample_config_file,
            )

    def test_add_source_invalid_type_raises(self, test_db: Session, sample_config_file: Path):
        """Test that invalid source type raises error."""
        service = SourceService(test_db)

        with pytest.raises(AdapterNotFoundError):
            service.add_source(
                name="test",
                source_type="nonexistent_type",
                config_path=sample_config_file,
            )

    def test_list_sources(self, test_db: Session, sample_config_file: Path):
        """Test listing all sources."""
        service = SourceService(test_db)

        service.add_source(name="source1", source_type="databricks", config_path=sample_config_file)
        service.add_source(name="source2", source_type="databricks", config_path=sample_config_file)
        test_db.commit()

        sources = service.list_sources()
        assert len(sources) == 2
        names = [s.name for s in sources]
        assert "source1" in names
        assert "source2" in names

    def test_get_source(self, test_db: Session, sample_config_file: Path):
        """Test getting a source by name."""
        service = SourceService(test_db)

        service.add_source(name="my-source", source_type="databricks", config_path=sample_config_file)
        test_db.commit()

        source = service.get_source("my-source")
        assert source.name == "my-source"

    def test_get_source_not_found_raises(self, test_db: Session):
        """Test that getting non-existent source raises error."""
        service = SourceService(test_db)

        with pytest.raises(SourceNotFoundError) as exc_info:
            service.get_source("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_remove_source(self, test_db: Session, sample_config_file: Path):
        """Test removing a source."""
        service = SourceService(test_db)

        service.add_source(name="to-remove", source_type="databricks", config_path=sample_config_file)
        test_db.commit()

        service.remove_source("to-remove")
        test_db.commit()

        with pytest.raises(SourceNotFoundError):
            service.get_source("to-remove")

    def test_test_source_success(self, test_db: Session, sample_config_file: Path):
        """Test testing a source connection (mocked success)."""
        service = SourceService(test_db)

        service.add_source(name="test", source_type="databricks", config_path=sample_config_file)
        test_db.commit()

        # Mock the adapter
        mock_adapter = MagicMock()
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)
        mock_adapter.test_connection = AsyncMock(return_value=True)

        with patch("datacompass.core.services.source_service.AdapterRegistry.get_adapter") as mock_get:
            mock_get.return_value = mock_adapter

            result = service.test_source("test")

        assert result.connected is True
        assert result.source_name == "test"
        assert result.latency_ms is not None

    def test_test_source_failure(self, test_db: Session, sample_config_file: Path):
        """Test testing a source connection (mocked failure)."""
        service = SourceService(test_db)

        service.add_source(name="test", source_type="databricks", config_path=sample_config_file)
        test_db.commit()

        # Mock the adapter to raise
        mock_adapter = MagicMock()
        mock_adapter.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch("datacompass.core.services.source_service.AdapterRegistry.get_adapter") as mock_get:
            mock_get.return_value = mock_adapter

            result = service.test_source("test")

        assert result.connected is False
        assert "Connection refused" in result.message

    def test_get_available_adapters(self, test_db: Session):
        """Test getting list of available adapters."""
        service = SourceService(test_db)

        adapters = service.get_available_adapters()
        assert len(adapters) >= 1

        # Find databricks
        databricks = None
        for adapter in adapters:
            if adapter["type"] == "databricks":
                databricks = adapter
                break

        assert databricks is not None
        assert "TABLE" in databricks["object_types"]
