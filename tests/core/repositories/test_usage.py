"""Tests for UsageRepository."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.usage import UsageRepository


class TestUsageRepository:
    """Test cases for UsageRepository."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="demo",
            source_type="postgresql",
            connection_info={},
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
    def repo(self, test_db: Session) -> UsageRepository:
        """Create a usage repository."""
        return UsageRepository(test_db)

    # =========================================================================
    # Record Metrics Tests
    # =========================================================================

    def test_record_metrics(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test recording usage metrics."""
        obj = catalog_objects[0]
        metric = repo.record_metrics(
            object_id=obj.id,
            row_count=1000,
            size_bytes=1024 * 1024,  # 1 MB
            read_count=50,
            write_count=10,
        )
        test_db.commit()

        assert metric.id is not None
        assert metric.object_id == obj.id
        assert metric.row_count == 1000
        assert metric.size_bytes == 1024 * 1024
        assert metric.read_count == 50
        assert metric.write_count == 10
        assert metric.collected_at is not None

    def test_record_metrics_partial(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test recording partial metrics (some fields null)."""
        obj = catalog_objects[0]
        metric = repo.record_metrics(
            object_id=obj.id,
            row_count=500,
            # size_bytes and others are null
        )
        test_db.commit()

        assert metric.row_count == 500
        assert metric.size_bytes is None
        assert metric.read_count is None

    def test_record_metrics_with_source_metrics(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test recording metrics with platform-specific data."""
        obj = catalog_objects[0]
        metric = repo.record_metrics(
            object_id=obj.id,
            row_count=100,
            source_metrics={
                "seq_scan": 10,
                "idx_scan": 40,
                "n_dead_tup": 5,
            },
        )
        test_db.commit()

        assert metric.source_metrics is not None
        assert metric.source_metrics["seq_scan"] == 10
        assert metric.source_metrics["idx_scan"] == 40

    # =========================================================================
    # Get Latest Tests
    # =========================================================================

    def test_get_latest(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test getting the most recent metric."""
        obj = catalog_objects[0]

        # Record multiple metrics at different times
        older_time = datetime.utcnow() - timedelta(hours=1)
        repo.record_metrics(
            object_id=obj.id,
            row_count=100,
            collected_at=older_time,
        )

        recent_time = datetime.utcnow()
        repo.record_metrics(
            object_id=obj.id,
            row_count=200,
            collected_at=recent_time,
        )
        test_db.commit()

        latest = repo.get_latest(obj.id)
        assert latest is not None
        assert latest.row_count == 200

    def test_get_latest_no_metrics(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test get_latest when no metrics exist."""
        obj = catalog_objects[0]
        latest = repo.get_latest(obj.id)
        assert latest is None

    # =========================================================================
    # Get History Tests
    # =========================================================================

    def test_get_history(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test getting historical metrics."""
        obj = catalog_objects[0]

        # Record metrics over several days
        for i in range(5):
            collected_at = datetime.utcnow() - timedelta(days=i)
            repo.record_metrics(
                object_id=obj.id,
                row_count=100 * (i + 1),
                collected_at=collected_at,
            )
        test_db.commit()

        history = repo.get_history(obj.id, days=30)
        assert len(history) == 5
        # Should be in descending order by collected_at
        assert history[0].row_count == 100  # most recent
        assert history[4].row_count == 500  # oldest

    def test_get_history_with_days_filter(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test history filtering by days."""
        obj = catalog_objects[0]

        # Record metrics: 2 within last 7 days, 2 outside
        for i, days_ago in enumerate([1, 5, 10, 20]):
            collected_at = datetime.utcnow() - timedelta(days=days_ago)
            repo.record_metrics(
                object_id=obj.id,
                row_count=100 * (i + 1),
                collected_at=collected_at,
            )
        test_db.commit()

        history = repo.get_history(obj.id, days=7)
        assert len(history) == 2

    def test_get_history_with_limit(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test history with limit."""
        obj = catalog_objects[0]

        for i in range(10):
            repo.record_metrics(object_id=obj.id, row_count=100 * i)
        test_db.commit()

        history = repo.get_history(obj.id, days=30, limit=5)
        assert len(history) == 5

    # =========================================================================
    # Hot Tables Tests
    # =========================================================================

    def test_get_hot_tables(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test getting hot tables."""
        # Record different read counts for each object
        for i, obj in enumerate(catalog_objects):
            repo.record_metrics(
                object_id=obj.id,
                row_count=1000 * (i + 1),
                read_count=100 * (len(catalog_objects) - i),  # highest reads for first object
            )
        test_db.commit()

        hot_tables = repo.get_hot_tables(days=7, limit=10, order_by="read_count")
        assert len(hot_tables) == 3

        # First should have highest read_count
        obj, metric = hot_tables[0]
        assert metric.read_count == 300  # customers

    def test_get_hot_tables_by_size(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test hot tables ordered by size."""
        for i, obj in enumerate(catalog_objects):
            repo.record_metrics(
                object_id=obj.id,
                size_bytes=1024 * 1024 * (i + 1),  # 1MB, 2MB, 3MB
            )
        test_db.commit()

        hot_tables = repo.get_hot_tables(days=7, limit=10, order_by="size_bytes")
        assert len(hot_tables) == 3

        # Largest should be first
        obj, metric = hot_tables[0]
        assert metric.size_bytes == 3 * 1024 * 1024  # products (3MB)

    def test_get_hot_tables_source_filter(
        self,
        test_db: Session,
        source: DataSource,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test hot tables filtered by source."""
        for obj in catalog_objects:
            repo.record_metrics(object_id=obj.id, read_count=100)
        test_db.commit()

        hot_tables = repo.get_hot_tables(
            source_id=source.id,
            days=7,
            limit=10,
        )
        assert len(hot_tables) == 3

        # Non-existent source
        hot_tables = repo.get_hot_tables(
            source_id=99999,
            days=7,
            limit=10,
        )
        assert len(hot_tables) == 0

    def test_get_hot_tables_uses_latest_metrics(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test that hot tables uses only the latest metric per object."""
        obj = catalog_objects[0]

        # Old metric with high read count
        old_time = datetime.utcnow() - timedelta(days=1)
        repo.record_metrics(
            object_id=obj.id,
            read_count=1000,
            collected_at=old_time,
        )

        # Recent metric with lower read count
        recent_time = datetime.utcnow()
        repo.record_metrics(
            object_id=obj.id,
            read_count=100,
            collected_at=recent_time,
        )
        test_db.commit()

        hot_tables = repo.get_hot_tables(days=7, limit=10)
        assert len(hot_tables) == 1
        _, metric = hot_tables[0]
        assert metric.read_count == 100  # Should use latest

    # =========================================================================
    # Count Tests
    # =========================================================================

    def test_count_objects_with_metrics(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test counting objects with metrics."""
        # Only record metrics for first 2 objects
        for obj in catalog_objects[:2]:
            repo.record_metrics(object_id=obj.id, row_count=100)
        test_db.commit()

        count = repo.count_objects_with_metrics()
        assert count == 2

    def test_get_total_metrics_count(
        self,
        test_db: Session,
        catalog_objects: list[CatalogObject],
        repo: UsageRepository,
    ):
        """Test counting total metric records."""
        # Record multiple metrics per object
        for obj in catalog_objects:
            repo.record_metrics(object_id=obj.id, row_count=100)
            repo.record_metrics(object_id=obj.id, row_count=200)
        test_db.commit()

        count = repo.get_total_metrics_count()
        assert count == 6  # 2 metrics per 3 objects
