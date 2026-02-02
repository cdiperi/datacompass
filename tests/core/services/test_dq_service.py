"""Tests for DQService."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.repositories.dq import DQRepository
from datacompass.core.services import ObjectNotFoundError
from datacompass.core.services.dq_service import (
    DQBreachNotFoundError,
    DQConfigExistsError,
    DQConfigNotFoundError,
    DQService,
)


class TestDQService:
    """Test cases for DQService."""

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
        service = DQService(test_db)

        config = service.create_config(
            object_id=catalog_object.id,
            date_column="created_at",
            grain="daily",
        )
        test_db.commit()

        assert config.id is not None
        assert config.object_id == catalog_object.id
        assert config.object_name == "orders"
        assert config.source_name == "demo"

    def test_create_config_object_not_found(self, test_db: Session):
        """Test creating config for non-existent object raises error."""
        service = DQService(test_db)

        with pytest.raises(ObjectNotFoundError):
            service.create_config(object_id=99999)

    def test_create_config_already_exists(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test creating config when one exists raises error."""
        service = DQService(test_db)

        service.create_config(object_id=catalog_object.id)
        test_db.commit()

        with pytest.raises(DQConfigExistsError):
            service.create_config(object_id=catalog_object.id)

    def test_get_config(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test getting a DQ config by ID."""
        service = DQService(test_db)

        created = service.create_config(object_id=catalog_object.id)
        test_db.commit()

        config = service.get_config(created.id)

        assert config.id == created.id
        assert config.object_name == "orders"

    def test_get_config_not_found(self, test_db: Session):
        """Test getting non-existent config raises error."""
        service = DQService(test_db)

        with pytest.raises(DQConfigNotFoundError):
            service.get_config(99999)

    def test_get_config_by_object(
        self, test_db: Session, source: DataSource, catalog_object: CatalogObject
    ):
        """Test getting config by object identifier."""
        service = DQService(test_db)

        service.create_config(object_id=catalog_object.id)
        test_db.commit()

        config = service.get_config_by_object("demo.core.orders")

        assert config.object_name == "orders"

    def test_list_configs(
        self, test_db: Session, source: DataSource
    ):
        """Test listing DQ configs."""
        service = DQService(test_db)
        obj_repo = CatalogObjectRepository(test_db)

        obj1, _ = obj_repo.upsert(source.id, "core", "table1", "TABLE")
        obj2, _ = obj_repo.upsert(source.id, "core", "table2", "TABLE")
        test_db.commit()

        service.create_config(obj1.id)
        service.create_config(obj2.id)
        test_db.commit()

        configs = service.list_configs()

        assert len(configs) == 2
        assert all(c.expectation_count == 0 for c in configs)

    def test_delete_config(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test deleting a DQ config."""
        service = DQService(test_db)

        config = service.create_config(object_id=catalog_object.id)
        test_db.commit()
        config_id = config.id

        result = service.delete_config(config_id)
        test_db.commit()

        assert result is True

        with pytest.raises(DQConfigNotFoundError):
            service.get_config(config_id)

    # =========================================================================
    # Expectation Tests
    # =========================================================================

    def test_create_expectation(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test creating an expectation."""
        service = DQService(test_db)

        config = service.create_config(object_id=catalog_object.id)
        test_db.commit()

        expectation = service.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute", "min": 100},
            priority="high",
        )
        test_db.commit()

        assert expectation.id is not None
        assert expectation.expectation_type == "row_count"

    def test_update_expectation(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test updating an expectation."""
        service = DQService(test_db)

        config = service.create_config(object_id=catalog_object.id)
        expectation = service.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute"},
        )
        test_db.commit()

        updated = service.update_expectation(
            expectation_id=expectation.id,
            priority="critical",
            is_enabled=False,
        )
        test_db.commit()

        assert updated.priority == "critical"
        assert updated.is_enabled is False

    # =========================================================================
    # Threshold Computation Tests
    # =========================================================================

    def test_compute_threshold_absolute(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test absolute threshold computation."""
        service = DQService(test_db)
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute", "min": 100, "max": 1000},
        )
        test_db.commit()

        low, high = service.compute_threshold(expectation, date.today())

        assert low == 100
        assert high == 1000

    def test_compute_threshold_simple_average(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test simple average threshold computation."""
        service = DQService(test_db)
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={
                "type": "simple_average",
                "multiplier": 2.0,
                "lookback_days": 7,
            },
        )
        test_db.commit()

        # Add historical data (consistent values = low std dev)
        today = date.today()
        for i in range(1, 8):
            repo.record_result(
                expectation.id,
                today - timedelta(days=i),
                1000.0,  # All same value
            )
        test_db.commit()

        low, high = service.compute_threshold(expectation, today)

        # With all same values, std dev is 0, so thresholds should be around avg
        assert low is not None
        assert high is not None
        assert low <= 1000 <= high

    def test_compute_threshold_no_history(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test threshold with no historical data falls back to absolute."""
        service = DQService(test_db)
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        expectation = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={
                "type": "simple_average",
                "min": 50,
                "max": 500,
            },
        )
        test_db.commit()

        low, high = service.compute_threshold(expectation, date.today())

        # Falls back to absolute bounds
        assert low == 50
        assert high == 500

    # =========================================================================
    # Execution Tests
    # =========================================================================

    def test_run_expectations(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test running DQ expectations."""
        service = DQService(test_db)

        config = service.create_config(object_id=catalog_object.id)
        service.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute", "min": 100, "max": 50000},
        )
        service.create_expectation(
            config_id=config.id,
            expectation_type="null_count",
            threshold_config={"type": "absolute", "max": 100},
            column_name="customer_id",
        )
        test_db.commit()

        result = service.run_expectations(config.id)
        test_db.commit()

        assert result.config_id == config.id
        assert result.object_name == "orders"
        assert result.total_checks == 2
        assert len(result.results) == 2

    def test_run_expectations_creates_breach(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test that running expectations creates breaches when thresholds violated."""
        service = DQService(test_db)

        config = service.create_config(object_id=catalog_object.id)
        # Create expectation with impossible threshold (max 0 for row_count)
        service.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute", "max": 0},  # Will always breach
            priority="critical",
        )
        test_db.commit()

        result = service.run_expectations(config.id)
        test_db.commit()

        # Should have 1 breach
        assert result.breached >= 1

        breaches = service.list_breaches(status="open")
        assert len(breaches) >= 1

    # =========================================================================
    # Breach Management Tests
    # =========================================================================

    def test_get_breach(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test getting breach details."""
        service = DQService(test_db)
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        exp = repo.create_expectation(
            config_id=config.id,
            expectation_type="row_count",
            threshold_config={"type": "absolute"},
            priority="high",
        )
        result = repo.record_result(exp.id, date.today(), 100)
        breach = repo.create_breach(
            exp.id, result.id, date.today(),
            100, "high", 50, 50, 100,
            {"type": "absolute"},
        )
        test_db.commit()

        detail = service.get_breach(breach.id)

        assert detail.id == breach.id
        assert detail.object_name == "orders"
        assert detail.priority == "high"

    def test_get_breach_not_found(self, test_db: Session):
        """Test getting non-existent breach raises error."""
        service = DQService(test_db)

        with pytest.raises(DQBreachNotFoundError):
            service.get_breach(99999)

    def test_update_breach_status(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test updating breach status."""
        service = DQService(test_db)
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        exp = repo.create_expectation(config.id, "row_count", {})
        result = repo.record_result(exp.id, date.today(), 100)
        breach = repo.create_breach(
            exp.id, result.id, date.today(),
            100, "high", 50, 50, 100, {},
        )
        test_db.commit()

        updated = service.update_breach_status(
            breach_id=breach.id,
            status="acknowledged",
            notes="Investigating the issue",
            updated_by="test_user",
        )
        test_db.commit()

        assert updated.status == "acknowledged"
        assert len(updated.lifecycle_events) == 1
        assert updated.lifecycle_events[0]["notes"] == "Investigating the issue"

    def test_list_breaches(
        self, test_db: Session, catalog_object: CatalogObject
    ):
        """Test listing breaches with filters."""
        service = DQService(test_db)
        repo = DQRepository(test_db)

        config = repo.create_config(object_id=catalog_object.id)
        exp = repo.create_expectation(config.id, "row_count", {}, priority="critical")

        for i in range(3):
            result = repo.record_result(exp.id, date.today() - timedelta(days=i), 100)
            repo.create_breach(
                exp.id, result.id, date.today() - timedelta(days=i),
                100, "high", 50, 50, 100, {},
            )
        test_db.commit()

        breaches = service.list_breaches()
        assert len(breaches) == 3

        breaches = service.list_breaches(priority="critical")
        assert len(breaches) == 3

        breaches = service.list_breaches(priority="low")
        assert len(breaches) == 0

    # =========================================================================
    # Hub Summary Tests
    # =========================================================================

    def test_get_hub_summary(
        self, test_db: Session, source: DataSource
    ):
        """Test getting hub summary."""
        service = DQService(test_db)
        obj_repo = CatalogObjectRepository(test_db)
        repo = DQRepository(test_db)

        # Create 2 objects with configs
        obj1, _ = obj_repo.upsert(source.id, "core", "table1", "TABLE")
        obj2, _ = obj_repo.upsert(source.id, "core", "table2", "TABLE")
        test_db.commit()

        config1 = repo.create_config(obj1.id)
        config2 = repo.create_config(obj2.id)
        config2.is_enabled = False  # Disable one

        exp1 = repo.create_expectation(config1.id, "row_count", {}, priority="critical")
        exp2 = repo.create_expectation(config1.id, "null_count", {}, priority="high")

        # Create one breach
        result = repo.record_result(exp1.id, date.today(), 100)
        repo.create_breach(
            exp1.id, result.id, date.today(),
            100, "high", 50, 50, 100, {},
        )
        test_db.commit()

        summary = service.get_hub_summary()

        assert summary.total_configs == 2
        assert summary.enabled_configs == 1
        assert summary.total_expectations == 2
        assert summary.open_breaches == 1
        assert summary.breaches_by_priority.get("critical", 0) == 1

    # =========================================================================
    # YAML Config Tests
    # =========================================================================

    def test_generate_yaml_template(
        self, test_db: Session, source: DataSource, catalog_object: CatalogObject
    ):
        """Test generating YAML template."""
        service = DQService(test_db)

        template = service.generate_yaml_template("demo.core.orders")

        assert "object: demo.core.orders" in template
        assert "expectations:" in template
        assert "row_count" in template

    def test_create_config_from_yaml(
        self, test_db: Session, source: DataSource, catalog_object: CatalogObject, tmp_path: Path
    ):
        """Test creating config from YAML file."""
        service = DQService(test_db)

        yaml_content = """
object: demo.core.orders
date_column: created_at
grain: daily

expectations:
  - type: row_count
    threshold:
      type: simple_average
      multiplier: 2.0
      lookback_days: 30
    priority: high

  - type: null_count
    column: customer_id
    threshold:
      type: absolute
      max: 0
    priority: critical
"""
        yaml_file = tmp_path / "dq_config.yaml"
        yaml_file.write_text(yaml_content)

        config = service.create_config_from_yaml(yaml_file)
        test_db.commit()

        assert config.object_name == "orders"
        assert config.date_column == "created_at"
        assert config.grain == "daily"
        assert len(config.expectations) == 2

        # Check expectations
        exp_types = {e.expectation_type for e in config.expectations}
        assert exp_types == {"row_count", "null_count"}
