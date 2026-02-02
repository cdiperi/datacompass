"""Service for Schedule operations."""

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from datacompass.core.models.scheduling import (
    Schedule,
    ScheduleCreate,
    ScheduleDetailResponse,
    ScheduleResponse,
    ScheduleRunResponse,
    SchedulerHubSummary,
    YAMLSchedulingConfig,
)
from datacompass.core.repositories.scheduling import (
    NotificationRepository,
    SchedulingRepository,
)


class SchedulingServiceError(Exception):
    """Base exception for scheduling service errors."""

    pass


class ScheduleNotFoundError(SchedulingServiceError):
    """Raised when a schedule is not found."""

    def __init__(self, identifier: str | int) -> None:
        self.identifier = identifier
        super().__init__(f"Schedule not found: {identifier}")


class ScheduleExistsError(SchedulingServiceError):
    """Raised when a schedule with the same name exists."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Schedule already exists: {name}")


class SchedulingService:
    """Service for schedule management and execution.

    Handles:
    - Schedule CRUD operations
    - Schedule run tracking
    - Hub summary aggregation
    """

    def __init__(self, session: Session) -> None:
        """Initialize scheduling service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.scheduling_repo = SchedulingRepository(session)
        self.notification_repo = NotificationRepository(session)

    # =========================================================================
    # Schedule Management
    # =========================================================================

    def get_schedule(self, schedule_id: int) -> ScheduleDetailResponse:
        """Get schedule by ID with recent runs.

        Args:
            schedule_id: ID of the schedule.

        Returns:
            ScheduleDetailResponse with full details.

        Raises:
            ScheduleNotFoundError: If schedule not found.
        """
        schedule = self.scheduling_repo.get_with_runs(schedule_id)
        if schedule is None:
            raise ScheduleNotFoundError(schedule_id)

        return self._schedule_to_detail_response(schedule)

    def get_schedule_by_name(self, name: str) -> ScheduleDetailResponse:
        """Get schedule by name.

        Args:
            name: Schedule name.

        Returns:
            ScheduleDetailResponse with full details.

        Raises:
            ScheduleNotFoundError: If schedule not found.
        """
        schedule = self.scheduling_repo.get_by_name(name)
        if schedule is None:
            raise ScheduleNotFoundError(name)

        # Load runs
        schedule = self.scheduling_repo.get_with_runs(schedule.id)
        return self._schedule_to_detail_response(schedule)

    def list_schedules(
        self,
        job_type: str | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ScheduleResponse]:
        """List schedules.

        Args:
            job_type: Filter by job type.
            enabled_only: Only return enabled schedules.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of ScheduleResponse.
        """
        schedules = self.scheduling_repo.list_schedules(
            job_type=job_type,
            enabled_only=enabled_only,
            limit=limit,
            offset=offset,
        )

        return [ScheduleResponse.model_validate(s) for s in schedules]

    def create_schedule(
        self,
        name: str,
        job_type: str,
        cron_expression: str,
        description: str | None = None,
        target_id: int | None = None,
        timezone: str = "UTC",
    ) -> ScheduleResponse:
        """Create a new schedule.

        Args:
            name: Unique schedule name.
            job_type: Type of job (scan, dq_run, deprecation_check).
            cron_expression: Cron expression for scheduling.
            description: Optional description.
            target_id: Target ID (source, config, or campaign).
            timezone: Timezone for cron expression.

        Returns:
            Created ScheduleResponse.

        Raises:
            ScheduleExistsError: If schedule with name exists.
        """
        # Check for existing
        existing = self.scheduling_repo.get_by_name(name)
        if existing is not None:
            raise ScheduleExistsError(name)

        # Validate cron expression
        self._validate_cron(cron_expression)

        schedule = self.scheduling_repo.create_schedule(
            name=name,
            job_type=job_type,
            cron_expression=cron_expression,
            description=description,
            target_id=target_id,
            timezone=timezone,
        )

        return ScheduleResponse.model_validate(schedule)

    def update_schedule(
        self,
        schedule_id: int,
        name: str | None = None,
        description: str | None = None,
        cron_expression: str | None = None,
        timezone: str | None = None,
        is_enabled: bool | None = None,
    ) -> ScheduleResponse:
        """Update a schedule.

        Args:
            schedule_id: ID of the schedule.
            name: New name.
            description: New description.
            cron_expression: New cron expression.
            timezone: New timezone.
            is_enabled: New enabled status.

        Returns:
            Updated ScheduleResponse.

        Raises:
            ScheduleNotFoundError: If schedule not found.
            ScheduleExistsError: If new name conflicts.
        """
        # Check name conflict if changing name
        if name is not None:
            existing = self.scheduling_repo.get_by_name(name)
            if existing is not None and existing.id != schedule_id:
                raise ScheduleExistsError(name)

        # Validate cron if provided
        if cron_expression is not None:
            self._validate_cron(cron_expression)

        schedule = self.scheduling_repo.update_schedule(
            schedule_id=schedule_id,
            name=name,
            description=description,
            cron_expression=cron_expression,
            timezone=timezone,
            is_enabled=is_enabled,
        )

        if schedule is None:
            raise ScheduleNotFoundError(schedule_id)

        return ScheduleResponse.model_validate(schedule)

    def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a schedule.

        Args:
            schedule_id: ID of the schedule.

        Returns:
            True if deleted.

        Raises:
            ScheduleNotFoundError: If schedule not found.
        """
        if not self.scheduling_repo.delete_schedule(schedule_id):
            raise ScheduleNotFoundError(schedule_id)
        return True

    # =========================================================================
    # Schedule Run Management
    # =========================================================================

    def start_run(self, schedule_id: int) -> ScheduleRunResponse:
        """Start a new schedule run.

        Args:
            schedule_id: ID of the schedule.

        Returns:
            ScheduleRunResponse for the new run.

        Raises:
            ScheduleNotFoundError: If schedule not found.
        """
        schedule = self.scheduling_repo.get_by_id(schedule_id)
        if schedule is None:
            raise ScheduleNotFoundError(schedule_id)

        run = self.scheduling_repo.create_run(schedule_id)
        return ScheduleRunResponse.model_validate(run)

    def complete_run(
        self,
        run_id: int,
        status: str,
        result_summary: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> ScheduleRunResponse:
        """Complete a schedule run.

        Args:
            run_id: ID of the run.
            status: Final status (success, failed).
            result_summary: Optional result summary.
            error_message: Optional error message.

        Returns:
            Updated ScheduleRunResponse.
        """
        run = self.scheduling_repo.complete_run(
            run_id=run_id,
            status=status,
            result_summary=result_summary,
            error_message=error_message,
        )

        # Update schedule's last run info
        if run is not None:
            self.scheduling_repo.update_schedule(
                schedule_id=run.schedule_id,
                last_run_at=run.completed_at,
                last_run_status=status,
            )

        return ScheduleRunResponse.model_validate(run)

    def get_runs(
        self,
        schedule_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ScheduleRunResponse]:
        """Get runs for a schedule.

        Args:
            schedule_id: ID of the schedule.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of ScheduleRunResponse.

        Raises:
            ScheduleNotFoundError: If schedule not found.
        """
        schedule = self.scheduling_repo.get_by_id(schedule_id)
        if schedule is None:
            raise ScheduleNotFoundError(schedule_id)

        runs = self.scheduling_repo.get_runs_for_schedule(
            schedule_id=schedule_id,
            limit=limit,
            offset=offset,
        )

        return [ScheduleRunResponse.model_validate(r) for r in runs]

    # =========================================================================
    # YAML Configuration
    # =========================================================================

    def apply_from_yaml(self, yaml_path: Path) -> dict[str, Any]:
        """Apply scheduling configuration from YAML file.

        Creates or updates schedules defined in the YAML file.

        Args:
            yaml_path: Path to YAML configuration file.

        Returns:
            Summary of applied changes.

        Raises:
            FileNotFoundError: If YAML file not found.
        """
        from datacompass.core.services import load_yaml_config

        if not yaml_path.exists():
            raise FileNotFoundError(yaml_path)

        raw_config = load_yaml_config(yaml_path)
        config = YAMLSchedulingConfig.model_validate(raw_config)

        created = 0
        updated = 0

        for yaml_schedule in config.schedules:
            existing = self.scheduling_repo.get_by_name(yaml_schedule.name)

            if existing:
                self.scheduling_repo.update_schedule(
                    schedule_id=existing.id,
                    description=yaml_schedule.description,
                    cron_expression=yaml_schedule.cron,
                    timezone=yaml_schedule.timezone,
                    is_enabled=yaml_schedule.enabled,
                )
                updated += 1
            else:
                # Resolve target name to ID if provided
                target_id = None
                if yaml_schedule.target:
                    target_id = self._resolve_target(
                        yaml_schedule.job_type, yaml_schedule.target
                    )

                self.scheduling_repo.create_schedule(
                    name=yaml_schedule.name,
                    job_type=yaml_schedule.job_type,
                    cron_expression=yaml_schedule.cron,
                    description=yaml_schedule.description,
                    target_id=target_id,
                    timezone=yaml_schedule.timezone,
                )
                created += 1

        return {
            "schedules_created": created,
            "schedules_updated": updated,
        }

    # =========================================================================
    # Hub Summary
    # =========================================================================

    def get_hub_summary(self) -> SchedulerHubSummary:
        """Get scheduler hub dashboard summary.

        Returns:
            SchedulerHubSummary with aggregated data.
        """
        total_schedules = self.scheduling_repo.count_schedules()
        enabled_schedules = self.scheduling_repo.count_schedules(enabled_only=True)
        total_channels = self.notification_repo.count_channels()
        enabled_channels = self.notification_repo.count_channels(enabled_only=True)
        total_rules = self.notification_repo.count_rules()
        enabled_rules = self.notification_repo.count_rules(enabled_only=True)

        schedules_by_type = self.scheduling_repo.count_schedules_by_type()
        notifications_by_status = self.notification_repo.count_notifications_by_status()

        recent_runs = self.scheduling_repo.get_recent_runs(limit=10)
        recent_logs = self.notification_repo.get_recent_logs(limit=10)

        return SchedulerHubSummary(
            total_schedules=total_schedules,
            enabled_schedules=enabled_schedules,
            total_channels=total_channels,
            enabled_channels=enabled_channels,
            total_rules=total_rules,
            enabled_rules=enabled_rules,
            recent_runs=[ScheduleRunResponse.model_validate(r) for r in recent_runs],
            recent_notifications=[],  # Will be populated by notification service
            schedules_by_type=schedules_by_type,
            notifications_by_status=notifications_by_status,
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _schedule_to_detail_response(self, schedule: Schedule) -> ScheduleDetailResponse:
        """Convert Schedule to ScheduleDetailResponse."""
        return ScheduleDetailResponse(
            id=schedule.id,
            name=schedule.name,
            description=schedule.description,
            job_type=schedule.job_type,
            target_id=schedule.target_id,
            cron_expression=schedule.cron_expression,
            timezone=schedule.timezone,
            is_enabled=schedule.is_enabled,
            next_run_at=schedule.next_run_at,
            last_run_at=schedule.last_run_at,
            last_run_status=schedule.last_run_status,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            recent_runs=[
                ScheduleRunResponse.model_validate(r) for r in schedule.runs
            ],
        )

    def _validate_cron(self, cron_expression: str) -> None:
        """Validate a cron expression.

        Args:
            cron_expression: Cron expression to validate.

        Raises:
            SchedulingServiceError: If cron expression is invalid.
        """
        parts = cron_expression.split()
        if len(parts) != 5:
            raise SchedulingServiceError(
                f"Invalid cron expression: expected 5 fields, got {len(parts)}"
            )

    def _resolve_target(self, job_type: str, target_name: str) -> int | None:
        """Resolve target name to ID.

        Args:
            job_type: Job type (scan, dq_run, deprecation_check).
            target_name: Target name to resolve.

        Returns:
            Target ID or None if not resolvable.
        """
        # Import here to avoid circular imports
        from datacompass.core.services.source_service import SourceService
        from datacompass.core.services.dq_service import DQService
        from datacompass.core.services.deprecation_service import DeprecationService

        if job_type == "scan":
            # Target is a source name
            service = SourceService(self.session)
            source = service.get_source(target_name)
            return source.id

        elif job_type == "dq_run":
            # Target is an object identifier
            service = DQService(self.session)
            config = service.get_config_by_object(target_name)
            return config.id

        elif job_type == "deprecation_check":
            # Target is a campaign ID or name
            service = DeprecationService(self.session)
            try:
                campaign_id = int(target_name)
                campaign = service.get_campaign(campaign_id)
                return campaign.id
            except ValueError:
                # Not an ID, assume it's looked up differently
                return None

        return None
