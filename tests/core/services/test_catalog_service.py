"""Tests for CatalogService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import DataSource
from datacompass.core.repositories import DataSourceRepository
from datacompass.core.services import (
    CatalogService,
    ObjectNotFoundError,
    SourceNotFoundError,
)


class TestCatalogService:
    """Test cases for CatalogService."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="test-source",
            source_type="databricks",
            connection_info={
                "host": "test.azuredatabricks.net",
                "http_path": "/sql/1.0/warehouses/abc",
                "catalog": "main",
                "auth_method": "personal_token",
                "access_token": "test-token",
            },
        )
        test_db.commit()
        return source

    def test_scan_source_success(
        self, test_db: Session, source: DataSource, mock_databricks_adapter
    ):
        """Test scanning a source successfully."""
        service = CatalogService(test_db)

        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter

            result = service.scan_source("test-source")
            test_db.commit()

        assert result.status == "success"
        assert result.source_name == "test-source"
        assert result.stats.objects_created == 3  # 2 tables + 1 view from fixture
        assert result.stats.columns_created == 8  # columns from fixture

    def test_scan_source_not_found(self, test_db: Session):
        """Test scanning non-existent source raises error."""
        service = CatalogService(test_db)

        with pytest.raises(SourceNotFoundError):
            service.scan_source("nonexistent")

    def test_scan_source_updates_existing(
        self, test_db: Session, source: DataSource, mock_databricks_adapter
    ):
        """Test that re-scanning updates existing objects."""
        service = CatalogService(test_db)

        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter

            # First scan - creates
            result1 = service.scan_source("test-source")
            test_db.commit()
            assert result1.stats.objects_created == 3

            # Second scan - updates
            result2 = service.scan_source("test-source")
            test_db.commit()
            assert result2.stats.objects_created == 0
            assert result2.stats.objects_updated == 3

    def test_list_objects(
        self, test_db: Session, source: DataSource, mock_databricks_adapter
    ):
        """Test listing catalog objects."""
        service = CatalogService(test_db)

        # First scan to populate
        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter
            service.scan_source("test-source")
            test_db.commit()

        # List all
        objects = service.list_objects()
        assert len(objects) == 3

        # Filter by source
        objects = service.list_objects(source="test-source")
        assert len(objects) == 3

        # Filter by type
        tables = service.list_objects(object_type="TABLE")
        assert len(tables) == 2

        views = service.list_objects(object_type="VIEW")
        assert len(views) == 1

    def test_list_objects_with_limit(
        self, test_db: Session, source: DataSource, mock_databricks_adapter
    ):
        """Test listing objects with limit."""
        service = CatalogService(test_db)

        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter
            service.scan_source("test-source")
            test_db.commit()

        objects = service.list_objects(limit=2)
        assert len(objects) == 2

    def test_get_object_by_id(
        self, test_db: Session, source: DataSource, mock_databricks_adapter
    ):
        """Test getting an object by ID."""
        service = CatalogService(test_db)

        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter
            service.scan_source("test-source")
            test_db.commit()

        # Get first object's ID
        objects = service.list_objects()
        first_id = objects[0].id

        # Get by ID
        obj = service.get_object(str(first_id))
        assert obj.id == first_id

    def test_get_object_by_qualified_name(
        self, test_db: Session, source: DataSource, mock_databricks_adapter
    ):
        """Test getting an object by qualified name."""
        service = CatalogService(test_db)

        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter
            service.scan_source("test-source")
            test_db.commit()

        # Get by qualified name
        obj = service.get_object("test-source.analytics.customers")
        assert obj.object_name == "customers"
        assert obj.schema_name == "analytics"

    def test_get_object_not_found(self, test_db: Session, source: DataSource):
        """Test getting non-existent object raises error."""
        service = CatalogService(test_db)

        with pytest.raises(ObjectNotFoundError):
            service.get_object("999999")

        with pytest.raises(ObjectNotFoundError):
            service.get_object("source.schema.nonexistent")

    def test_get_object_includes_columns(
        self, test_db: Session, source: DataSource, mock_databricks_adapter
    ):
        """Test that get_object includes column information."""
        service = CatalogService(test_db)

        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_databricks_adapter
            service.scan_source("test-source")
            test_db.commit()

        obj = service.get_object("test-source.analytics.customers")
        assert len(obj.columns) == 3
        column_names = [c.column_name for c in obj.columns]
        assert "customer_id" in column_names
        assert "name" in column_names
        assert "email" in column_names

    def test_scan_failure_updates_status(
        self, test_db: Session, source: DataSource
    ):
        """Test that scan failure updates source status."""
        service = CatalogService(test_db)

        mock_adapter = MagicMock()
        mock_adapter.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "datacompass.core.services.catalog_service.AdapterRegistry.get_adapter"
        ) as mock_get:
            mock_get.return_value = mock_adapter

            result = service.scan_source("test-source")
            test_db.commit()

        assert result.status == "failed"
        assert "Connection failed" in result.message

        # Check source status was updated
        test_db.refresh(source)
        assert source.last_scan_status == "failed"
