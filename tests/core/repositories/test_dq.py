"""Tests for DQRepository."""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.dq import DQRepository


class TestDQRepository:
    """Test cases for DQRepository."""

    @pytest.fixture
    def source(self, test_db: Session) -> DataSource:
        """Create a test data source."""
        repo = DataSourceRepository(test_db)
        source = repo.create(
            name="demo",
            source_type="databricks",
            connection_info={},
        )
        test_db.commit()
        return source

    @pytest.fixture
    def catalog_object(self, test_db: Session, source: DataSource) -> CatalogObject:
        """Create a test catalog object."""
        repo = CatalogObjectRepository(test_db)
        obj, _ = repo.upsert(source.id, "core", "orders", "TABLE")
        test_db.commit()
        return obj

    # =========================================================================
    # Config Tests
    # =========================================================================

    def test_create_config(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test creating a DQ config."""
        repo = DQRepository(test_db)

        config = repo.create_config(
            object_id=catalog_object.id,
            date_column="created_at",
            grain="daily",
        )
        test_db.commit()

        assert config.id is not None
        assert config.object_id == catalog_object.id
        assert config.date_column == "created_at"
        assert config.grain == "daily"
        assert config.is_enabled is True

    def test_get_config_by_object_id(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test getting config by object ID."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        test_db.commit()

        retrieved = repo.get_config_by_object_id(catalog_object.id)
        assert retrieved is not None
        assert retrieved.id == config.id

    def test_get_config_by_object_id_not_found(
        self, test_db: Session
    ):
        """Test getting config for non-existent object returns None."""
        repo = DQRepository(test_db)

        result = repo.get_config_by_object_id(99999)
        assert result is None

    def test_update_config(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test updating a DQ config."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        test_db.commit()

        updated = repo.update_config(
            config.id,
            date_column="updated_at",
            grain="hourly",
            is_enabled=False,
        )
        test_db.commit()

        assert updated.date_column == "updated_at"
        assert updated.grain == "hourly"
        assert updated.is_enabled is False

    def test_delete_config(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test deleting a DQ config."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        test_db.commit()
        config_id = config.id

        result = repo.delete_config(config_id)
        test_db.commit()

        assert result is True
        assert repo.get_by_id(config_id) is None

    # =========================================================================
    # Expectation Tests
    # =========================================================================

    def test_create_expectation(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test creating a DQ expectation."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        test_db.commit()

        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute", "min": 100, "max": 10000},
            priority="high",
        )
        test_db.commit()

        assert expectation.id is not None
        assert expectation.config_id == config.id
        assert expectation.expectation_type == "row_count"
        assert expectation.threshold_config["type"] == "absolute"
        assert expectation.priority == "high"

    def test_create_column_expectation(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test creating a column-level expectation."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        test_db.commit()

        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="null_count",
            column_name="customer_id",
            threshold_config={"type": "absolute", "max": 0},
            priority="critical",
        )
        test_db.commit()

        assert expectation.column_name == "customer_id"
        assert expectation.expectation_type == "null_count"

    def test_get_enabled_expectations(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test getting enabled expectations."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        test_db.commit()

        # Create 3 expectations, disable 1
        for i, enabled in enumerate([(True,), (True,), (False,)]):
            exp = repo.create_expectation(
                config_id=config.id,
                expectation_type=f"metric_{i}",
                threshold_config={"type": "absolute"},
            )
            exp.is_enabled = enabled[0]
        test_db.commit()

        enabled = repo.get_enabled_expectations(config.id)
        assert len(enabled) == 2

    # =========================================================================
    # Result Tests
    # =========================================================================

    def test_record_result(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test recording a DQ result."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute"},
        )
        test_db.commit()

        snapshot_date = date.today()
        result = repo.record_result(
            expectation_id=expectation.id,
            snapshot_date=snapshot_date,
            metric_value=15000.0,
            computed_threshold_low=10000.0,
            computed_threshold_high=20000.0,
            execution_time_ms=150,
        )
        test_db.commit()

        assert result.id is not None
        assert result.metric_value == 15000.0
        assert result.computed_threshold_low == 10000.0

    def test_record_result_upsert(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test that recording result for same date updates existing."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute"},
        )
        test_db.commit()

        snapshot_date = date.today()

        # First record
        result1 = repo.record_result(
            expectation_id=expectation.id,
            snapshot_date=snapshot_date,
            metric_value=15000.0,
        )
        test_db.commit()
        result1_id = result1.id

        # Second record (should update)
        result2 = repo.record_result(
            expectation_id=expectation.id,
            snapshot_date=snapshot_date,
            metric_value=16000.0,
        )
        test_db.commit()

        assert result2.id == result1_id
        assert result2.metric_value == 16000.0

    def test_get_historical_results(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test getting historical results."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute"},
        )
        test_db.commit()

        # Create results for last 5 days
        today = date.today()
        for i in range(1, 6):
            repo.record_result(
                expectation_id=expectation.id,
                snapshot_date=today - timedelta(days=i),
                metric_value=10000.0 + i * 100,
            )
        test_db.commit()

        # Get last 3 days
        results = repo.get_historical_results(
            expectation_id=expectation.id,
            days=3,
            end_date=today,
        )

        assert len(results) == 3
        # Results should be ordered by date desc
        assert results[0].snapshot_date > results[1].snapshot_date

    # =========================================================================
    # Breach Tests
    # =========================================================================

    def test_create_breach(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test creating a breach."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute", "min": 100},
        )
        test_db.commit()

        snapshot_date = date.today()
        result = repo.record_result(
            expectation_id=expectation.id,
            snapshot_date=snapshot_date,
            metric_value=50.0,
            computed_threshold_low=100.0,
        )
        test_db.commit()

        breach = repo.create_breach(
            expectation_id=expectation.id,
            result_id=result.id,
            snapshot_date=snapshot_date,
            metric_value=50.0,
            breach_direction="low",
            threshold_value=100.0,
            deviation_value=50.0,
            deviation_percent=50.0,
            threshold_snapshot={"type": "absolute", "min": 100},
        )
        test_db.commit()

        assert breach.id is not None
        assert breach.status == "open"
        assert breach.breach_direction == "low"
        assert breach.deviation_percent == 50.0

    def test_update_breach_status(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test updating breach status."""
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute"},
        )
        result = repo.record_result(
            expectation_id=expectation.id,
            snapshot_date=date.today(),
            metric_value=50.0,
        )
        breach = repo.create_breach(
            expectation_id=expectation.id,
            result_id=result.id,
            snapshot_date=date.today(),
            metric_value=50.0,
            breach_direction="low",
            threshold_value=100.0,
            deviation_value=50.0,
            deviation_percent=50.0,
            threshold_snapshot={},
        )
        test_db.commit()

        updated = repo.update_breach_status(
            breach_id=breach.id,
            status="acknowledged",
            notes="Looking into it",
            updated_by="test_user",
        )
        test_db.commit()

        assert updated.status == "acknowledged"
        assert len(updated.lifecycle_events) == 1
        assert updated.lifecycle_events[0]["status"] == "acknowledged"
        assert updated.lifecycle_events[0]["by"] == "test_user"
        assert updated.lifecycle_events[0]["notes"] == "Looking into it"

    def test_list_breaches_with_filters(
        self, test_db: Session, source: DataSource
    ):
        """Test listing breaches with filters."""
        repo = DQRepository(test_db)
        obj_repo = CatalogObjectRepository(test_db)

        # Create 2 objects with different configs
        obj1, _ = obj_repo.upsert(source.id, "core", "table1", "TABLE")
        obj2, _ = obj_repo.upsert(source.id, "core", "table2", "TABLE")
        test_db.commit()

        # Create configs and expectations
        config1 = repo.create_config(object_id=obj1.id)
        config2 = repo.create_config(object_id=obj2.id)

        exp1 = repo.create_expectation(
            config_id=config1.id,
            expectation_type="row_count",
            threshold_config={},
            priority="critical",
        )
        exp2 = repo.create_expectation(
            config_id=config2.id,
            expectation_type="null_count",
            threshold_config={},
            priority="low",
        )

        result1 = repo.record_result(exp1.id, date.today(), 100)
        result2 = repo.record_result(exp2.id, date.today(), 200)

        breach1 = repo.create_breach(
            exp1.id, result1.id, date.today(), 100, "high", 50, 50, 100, {}
        )
        breach2 = repo.create_breach(
            exp2.id, result2.id, date.today(), 200, "low", 250, 50, 20, {}
        )
        test_db.commit()

        # Update one breach
        repo.update_breach_status(breach1.id, "acknowledged")
        test_db.commit()

        # Filter by status
        open_breaches = repo.list_breaches(status="open")
        assert len(open_breaches) == 1
        assert open_breaches[0].id == breach2.id

        # Filter by priority
        critical_breaches = repo.list_breaches(priority="critical")
        assert len(critical_breaches) == 1
        assert critical_breaches[0].id == breach1.id

    # =========================================================================
    # Aggregate Tests
    # =========================================================================

    def test_count_configs(
        self, test_db: Session, source: DataSource
    ):
        """Test counting configs."""
        repo = DQRepository(test_db)
        obj_repo = CatalogObjectRepository(test_db)

        obj1, _ = obj_repo.upsert(source.id, "core", "table1", "TABLE")
        obj2, _ = obj_repo.upsert(source.id, "core", "table2", "TABLE")
        test_db.commit()

        config1 = repo.create_config(obj1.id)
        config2 = repo.create_config(obj2.id)
        config2.is_enabled = False
        test_db.commit()

        total = repo.count_configs()
        enabled = repo.count_configs(enabled_only=True)

        assert total == 2
        assert enabled == 1

    def test_count_breaches_by_status(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test counting breaches by status."""
        repo = DQRepository(test_db)

        config = repo.create_config(catalog_object.id)
        exp = repo.create_expectation(config.id, "row_count", {})

        # Create breaches with different statuses
        for i, status in enumerate(["open", "open", "acknowledged", "resolved"]):
            result = repo.record_result(exp.id, date.today() - timedelta(days=i), 100)
            breach = repo.create_breach(
                exp.id, result.id, date.today() - timedelta(days=i),
                100, "high", 50, 50, 100, {}
            )
            if status != "open":
                repo.update_breach_status(breach.id, status)
        test_db.commit()

        counts = repo.count_breaches_by_status()

        assert counts.get("open", 0) == 2
        assert counts.get("acknowledged", 0) == 1
        assert counts.get("resolved", 0) == 1
