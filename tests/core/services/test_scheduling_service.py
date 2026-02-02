"""Tests for SchedulingService."""

import pytest
from sqlalchemy.orm import Session

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories import CatalogObjectRepository, DataSourceRepository
from datacompass.core.services.scheduling_service import (
    ScheduleExistsError,
    ScheduleNotFoundError,
    SchedulingService,
)


class TestSchedulingService:
    """Test cases for SchedulingService."""

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
    def service(self, test_db: Session) -> SchedulingService:
        """Create a scheduling service."""
        return SchedulingService(test_db)

    # =========================================================================
    # Schedule Tests
    # =========================================================================

    def test_create_schedule(
        self, test_db: Session, source: DataSource, service: SchedulingService
    ):
        """Test creating a schedule."""
        schedule = service.create_schedule(
            name="daily-scan",
            job_type="scan",
            cron_expression="0 6 * * *",
            target_id=source.id,
            description="Daily catalog scan",
            timezone="UTC",
        )
        test_db.commit()

        assert schedule.id is not None
        assert schedule.name == "daily-scan"
        assert schedule.job_type == "scan"
        assert schedule.cron_expression == "0 6 * * *"
        assert schedule.target_id == source.id
        assert schedule.description == "Daily catalog scan"
        assert schedule.timezone == "UTC"
        assert schedule.is_enabled is True

    def test_create_schedule_duplicate_name(
        self, test_db: Session, service: SchedulingService
    ):
        """Test creating schedule with duplicate name raises error."""
        service.create_schedule(
            name="test-schedule",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        test_db.commit()

        with pytest.raises(ScheduleExistsError):
            service.create_schedule(
                name="test-schedule",
                job_type="dq_run",
                cron_expression="0 7 * * *",
            )

    def test_create_schedule_without_target(
        self, test_db: Session, service: SchedulingService
    ):
        """Test creating schedule without target (run all)."""
        schedule = service.create_schedule(
            name="run-all-scans",
            job_type="scan",
            cron_expression="0 8 * * *",
        )
        test_db.commit()

        assert schedule.id is not None
        assert schedule.target_id is None

    def test_get_schedule(
        self, test_db: Session, service: SchedulingService
    ):
        """Test getting schedule by ID."""
        created = service.create_schedule(
            name="test",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        test_db.commit()

        schedule = service.get_schedule(created.id)

        assert schedule.id == created.id
        assert schedule.name == "test"

    def test_get_schedule_not_found(
        self, test_db: Session, service: SchedulingService
    ):
        """Test getting non-existent schedule raises error."""
        with pytest.raises(ScheduleNotFoundError):
            service.get_schedule(9999)

    def test_list_schedules(
        self, test_db: Session, service: SchedulingService
    ):
        """Test listing schedules."""
        service.create_schedule(
            name="scan-1",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        service.create_schedule(
            name="dq-1",
            job_type="dq_run",
            cron_expression="0 7 * * *",
        )
        service.create_schedule(
            name="deprecation-1",
            job_type="deprecation_check",
            cron_expression="0 8 * * *",
        )
        test_db.commit()

        schedules = service.list_schedules()
        assert len(schedules) == 3

    def test_list_schedules_filter_by_type(
        self, test_db: Session, service: SchedulingService
    ):
        """Test listing schedules filtered by job type."""
        service.create_schedule(
            name="scan-1",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        service.create_schedule(
            name="dq-1",
            job_type="dq_run",
            cron_expression="0 7 * * *",
        )
        test_db.commit()

        scans = service.list_schedules(job_type="scan")
        assert len(scans) == 1
        assert scans[0].job_type == "scan"

    def test_list_schedules_filter_by_enabled(
        self, test_db: Session, service: SchedulingService
    ):
        """Test listing schedules filtered by enabled status."""
        schedule1 = service.create_schedule(
            name="enabled-schedule",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        schedule2 = service.create_schedule(
            name="disabled-schedule",
            job_type="scan",
            cron_expression="0 7 * * *",
        )
        test_db.commit()

        # Disable one schedule
        service.update_schedule(schedule2.id, is_enabled=False)
        test_db.commit()

        enabled = service.list_schedules(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].name == "enabled-schedule"

    def test_update_schedule(
        self, test_db: Session, service: SchedulingService
    ):
        """Test updating a schedule."""
        created = service.create_schedule(
            name="test",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        test_db.commit()

        updated = service.update_schedule(
            created.id,
            name="updated-name",
            cron_expression="0 8 * * *",
            is_enabled=False,
        )
        test_db.commit()

        assert updated.name == "updated-name"
        assert updated.cron_expression == "0 8 * * *"
        assert updated.is_enabled is False

    def test_update_schedule_not_found(
        self, test_db: Session, service: SchedulingService
    ):
        """Test updating non-existent schedule raises error."""
        with pytest.raises(ScheduleNotFoundError):
            service.update_schedule(9999, name="new-name")

    def test_delete_schedule(
        self, test_db: Session, service: SchedulingService
    ):
        """Test deleting a schedule."""
        created = service.create_schedule(
            name="test",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        test_db.commit()

        result = service.delete_schedule(created.id)
        test_db.commit()

        assert result is True

        with pytest.raises(ScheduleNotFoundError):
            service.get_schedule(created.id)

    def test_delete_schedule_not_found(
        self, test_db: Session, service: SchedulingService
    ):
        """Test deleting non-existent schedule raises error."""
        with pytest.raises(ScheduleNotFoundError):
            service.delete_schedule(9999)

    # =========================================================================
    # Hub Summary Tests
    # =========================================================================

    def test_get_hub_summary_empty(
        self, test_db: Session, service: SchedulingService
    ):
        """Test hub summary with no schedules."""
        summary = service.get_hub_summary()

        assert summary.total_schedules == 0
        assert summary.enabled_schedules == 0
        assert summary.recent_runs == []

    def test_get_hub_summary_with_schedules(
        self, test_db: Session, service: SchedulingService
    ):
        """Test hub summary with schedules."""
        service.create_schedule(
            name="scan-1",
            job_type="scan",
            cron_expression="0 6 * * *",
        )
        service.create_schedule(
            name="dq-1",
            job_type="dq_run",
            cron_expression="0 7 * * *",
        )
        test_db.commit()

        summary = service.get_hub_summary()

        assert summary.total_schedules == 2
        assert summary.enabled_schedules == 2
        assert "scan" in summary.schedules_by_type
        assert "dq_run" in summary.schedules_by_type
