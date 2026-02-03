"""Tests for UsageService."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.usage import UsageRepository
from datacompass.core.services.usage_service import (
    ObjectNotFoundError,
    UsageService,
)
from datacompass.core.services.source_service import SourceNotFoundError


class TestUsageService:
    """Test cases for UsageService."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="demo",
            source_type="postgresql",
            connection_info={"host": "localhost"},
        )
        test_db.commit()
        return source

    @pytest.fixture
    def catalog_objects(self, test_db: Session, source: DataSource) -> list[CatalogObject]:
        """Create multiple test catalog objects."""
        repo = CatalogObjectRepository(test_db)
        objects = []
        for name in ["customers", "orders", "products"]:
            obj, _ = repo.upsert(source.id, "analytics", name, "TABLE")
            objects.append(obj)
        test_db.commit()
        return objects

    @pytest.fixture
    def service(self, test_db: Session) -> UsageService:
        """Create a usage service."""
        return UsageService(test_db)

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter that returns usage metrics."""
        adapter = MagicMock()
        adapter.__aenter__ = AsyncMock(return_value=adapter)
        adapter.__aexit__ = AsyncMock(return_value=None)
        adapter.get_usage_metrics = AsyncMock(return_value=[
            {
                "schema_name": "analytics",
                "object_name": "customers",
                "row_count": 1000,
                "size_bytes": 1024 * 1024,
                "read_count": 50,
                "write_count": 10,
                "source_metrics": {"seq_scan": 20, "idx_scan": 30},
            },
            {
                "schema_name": "analytics",
                "object_name": "orders",
                "row_count": 5000,
                "size_bytes": 5 * 1024 * 1024,
                "read_count": 200,
                "write_count": 50,
                "source_metrics": {"seq_scan": 100, "idx_scan": 100},
            },
        ])
        return adapter

    # =========================================================================
    # Collect Metrics Tests
    # =========================================================================

    def test_collect_metrics(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: UsageService,
        mock_adapter,
    ):
        """Test collecting metrics from a source."""
        with patch(
            "datacompass.core.services.usage_service.AdapterRegistry.get_adapter",
            return_value=mock_adapter,
        ):
            result = service.collect_metrics(source.name)
            test_db.commit()

        assert result.source_name == source.name
        assert result.collected_count == 2  # customers and orders
        assert result.skipped_count == 1  # products (not in adapter response)
        assert result.collected_at is not None

        # Verify metrics were recorded
        usage_repo = UsageRepository(test_db)
        for obj in catalog_objects[:2]:  # customers and orders
            metric = usage_repo.get_latest(obj.id)
            if obj.object_name == "customers":
                assert metric is not None
                assert metric.row_count == 1000
                assert metric.read_count == 50

    def test_collect_metrics_source_not_found(
        self,
        service: UsageService,
    ):
        """Test collection with non-existent source."""
        with pytest.raises(SourceNotFoundError):
            service.collect_metrics("nonexistent")

    def test_collect_metrics_no_objects(
        self,
        test_db: Session,
        source: DataSource,
        service: UsageService,
    ):
        """Test collection when source has no objects."""
        result = service.collect_metrics(source.name)

        assert result.collected_count == 0
        assert result.skipped_count == 0

    # =========================================================================
    # Get Object Usage Tests
    # =========================================================================

    def test_get_object_usage_by_id(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test getting usage metrics by object ID."""
        obj = catalog_objects[0]

        # Record some metrics
        usage_repo = UsageRepository(test_db)
        usage_repo.record_metrics(
            object_id=obj.id,
            row_count=1000,
            size_bytes=1024 * 1024,
        )
        test_db.commit()

        result = service.get_object_usage(obj.id)

        assert result is not None
        assert result.object_id == obj.id
        assert result.row_count == 1000
        assert result.object_name == "customers"
        assert result.source_name == "demo"

    def test_get_object_usage_by_identifier(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test getting usage metrics by identifier string."""
        obj = catalog_objects[0]

        usage_repo = UsageRepository(test_db)
        usage_repo.record_metrics(object_id=obj.id, row_count=500)
        test_db.commit()

        # Test source.schema.name format
        result = service.get_object_usage("demo.analytics.customers")
        assert result is not None
        assert result.row_count == 500

    def test_get_object_usage_no_metrics(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test getting usage when no metrics exist."""
        result = service.get_object_usage(catalog_objects[0].id)
        assert result is None

    def test_get_object_usage_not_found(
        self,
        service: UsageService,
    ):
        """Test getting usage for non-existent object."""
        with pytest.raises(ObjectNotFoundError):
            service.get_object_usage(99999)

        with pytest.raises(ObjectNotFoundError):
            service.get_object_usage("nonexistent.schema.table")

    # =========================================================================
    # Get Usage History Tests
    # =========================================================================

    def test_get_usage_history(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test getting historical usage metrics."""
        obj = catalog_objects[0]

        # Record multiple metrics
        usage_repo = UsageRepository(test_db)
        for i in range(5):
            collected_at = datetime.utcnow() - timedelta(days=i)
            usage_repo.record_metrics(
                object_id=obj.id,
                row_count=100 * (i + 1),
                collected_at=collected_at,
            )
        test_db.commit()

        history = service.get_usage_history(obj.id, days=30)

        assert len(history) == 5
        # Most recent first
        assert history[0].row_count == 100
        assert history[4].row_count == 500

    def test_get_usage_history_with_limit(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test history with limit."""
        obj = catalog_objects[0]

        usage_repo = UsageRepository(test_db)
        for i in range(10):
            usage_repo.record_metrics(object_id=obj.id, row_count=100 * i)
        test_db.commit()

        history = service.get_usage_history(obj.id, days=30, limit=5)
        assert len(history) == 5

    def test_get_usage_history_object_not_found(
        self,
        service: UsageService,
    ):
        """Test history for non-existent object."""
        with pytest.raises(ObjectNotFoundError):
            service.get_usage_history(99999)

    # =========================================================================
    # Hot Tables Tests
    # =========================================================================

    def test_get_hot_tables(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test getting hot tables."""
        usage_repo = UsageRepository(test_db)

        # Record different read counts
        for i, obj in enumerate(catalog_objects):
            usage_repo.record_metrics(
                object_id=obj.id,
                read_count=100 * (len(catalog_objects) - i),
            )
        test_db.commit()

        hot_tables = service.get_hot_tables(days=7, limit=10)

        assert len(hot_tables) == 3
        # First should have highest read_count
        assert hot_tables[0].read_count == 300
        assert hot_tables[0].object_name == "customers"

    def test_get_hot_tables_with_source_filter(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test hot tables filtered by source."""
        usage_repo = UsageRepository(test_db)
        for obj in catalog_objects:
            usage_repo.record_metrics(object_id=obj.id, read_count=100)
        test_db.commit()

        hot_tables = service.get_hot_tables(source_name=source.name)
        assert len(hot_tables) == 3

    def test_get_hot_tables_source_not_found(
        self,
        service: UsageService,
    ):
        """Test hot tables with non-existent source."""
        with pytest.raises(SourceNotFoundError):
            service.get_hot_tables(source_name="nonexistent")

    def test_get_hot_tables_empty(
        self,
        test_db: Session,
        source: DataSource,
        service: UsageService,
    ):
        """Test hot tables when no metrics exist."""
        hot_tables = service.get_hot_tables()
        assert len(hot_tables) == 0

    # =========================================================================
    # Hub Summary Tests
    # =========================================================================

    def test_get_hub_summary(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test getting hub summary."""
        usage_repo = UsageRepository(test_db)

        # Record metrics for some objects
        for obj in catalog_objects[:2]:
            usage_repo.record_metrics(object_id=obj.id, read_count=100)
        test_db.commit()

        summary = service.get_hub_summary()

        assert summary.total_objects_with_metrics == 2
        assert summary.total_metrics_collected == 2
        assert len(summary.hot_tables) == 2

    def test_get_hub_summary_empty(
        self,
        service: UsageService,
    ):
        """Test hub summary with no metrics."""
        summary = service.get_hub_summary()

        assert summary.total_objects_with_metrics == 0
        assert summary.total_metrics_collected == 0
        assert len(summary.hot_tables) == 0

    # =========================================================================
    # Object Resolution Tests
    # =========================================================================

    def test_resolve_object_by_id(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test resolving object by ID."""
        obj = catalog_objects[0]
        resolved = service._resolve_object(obj.id)
        assert resolved.id == obj.id

    def test_resolve_object_by_full_identifier(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test resolving object by source.schema.name format."""
        resolved = service._resolve_object("demo.analytics.customers")
        assert resolved.object_name == "customers"
        assert resolved.schema_name == "analytics"

    def test_resolve_object_by_short_identifier(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        service: UsageService,
    ):
        """Test resolving object by schema.name format."""
        resolved = service._resolve_object("analytics.customers")
        assert resolved.object_name == "customers"

    def test_resolve_object_invalid_format(
        self,
        service: UsageService,
    ):
        """Test resolving object with invalid identifier format."""
        with pytest.raises(ObjectNotFoundError):
            service._resolve_object("invalid")

        with pytest.raises(ObjectNotFoundError):
            service._resolve_object("too.many.parts.here")
