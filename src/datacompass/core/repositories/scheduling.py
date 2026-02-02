"""Repository for Scheduling and Notification operations."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from datacompass.core.models.scheduling import (
    NotificationChannel,
    NotificationLog,
    NotificationRule,
    Schedule,
    ScheduleRun,
)
from datacompass.core.repositories.base import BaseRepository


class SchedulingRepository(BaseRepository[Schedule]):
    """Repository for Schedule CRUD operations."""

    model = Schedule

    # =========================================================================
    # Schedule Operations
    # =========================================================================

    def get_by_name(self, name: str) -> Schedule | None:
        """Get schedule by name.

        Args:
            name: Schedule name.

        Returns:
            Schedule instance or None if not found.
        """
        stmt = select(Schedule).where(Schedule.name == name)
        return self.session.scalar(stmt)

    def get_with_runs(self, schedule_id: int, run_limit: int = 10) -> Schedule | None:
        """Get schedule with recent runs loaded.

        Args:
            schedule_id: ID of the schedule.
            run_limit: Maximum number of recent runs to load.

        Returns:
            Schedule with loaded runs or None.
        """
        stmt = (
            select(Schedule)
            .options(joinedload(Schedule.runs))
            .where(Schedule.id == schedule_id)
        )
        schedule = self.session.scalar(stmt)
        if schedule:
            # Sort runs by started_at desc and limit
            schedule.runs = sorted(
                schedule.runs, key=lambda r: r.started_at, reverse=True
            )[:run_limit]
        return schedule

    def list_schedules(
        self,
        job_type: str | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Schedule]:
        """List schedules with optional filters.

        Args:
            job_type: Filter by job type.
            enabled_only: Only return enabled schedules.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of Schedule instances.
        """
        stmt = select(Schedule)

        if job_type is not None:
            stmt = stmt.where(Schedule.job_type == job_type)

        if enabled_only:
            stmt = stmt.where(Schedule.is_enabled == True)  # noqa: E712

        stmt = stmt.order_by(Schedule.name)
        stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt))

    def list_enabled_schedules(self) -> list[Schedule]:
        """Get all enabled schedules.

        Returns:
            List of enabled Schedule instances.
        """
        return self.list_schedules(enabled_only=True)

    def create_schedule(
        self,
        name: str,
        job_type: str,
        cron_expression: str,
        description: str | None = None,
        target_id: int | None = None,
        timezone: str = "UTC",
    ) -> Schedule:
        """Create a new schedule.

        Args:
            name: Unique schedule name.
            job_type: Type of job (scan, dq_run, deprecation_check).
            cron_expression: Cron expression for scheduling.
            description: Optional description.
            target_id: Target ID (source, config, or campaign).
            timezone: Timezone for cron expression.

        Returns:
            Created Schedule instance.
        """
        schedule = Schedule(
            name=name,
            job_type=job_type,
            cron_expression=cron_expression,
            description=description,
            target_id=target_id,
            timezone=timezone,
        )
        self.add(schedule)
        self.flush()
        return schedule

    def update_schedule(
        self,
        schedule_id: int,
        name: str | None = None,
        description: str | None = None,
        cron_expression: str | None = None,
        timezone: str | None = None,
        is_enabled: bool | None = None,
        next_run_at: datetime | None = None,
        last_run_at: datetime | None = None,
        last_run_status: str | None = None,
    ) -> Schedule | None:
        """Update a schedule.

        Args:
            schedule_id: ID of the schedule.
            name: New name.
            description: New description.
            cron_expression: New cron expression.
            timezone: New timezone.
            is_enabled: New enabled status.
            next_run_at: Next scheduled run time.
            last_run_at: Last run time.
            last_run_status: Last run status.

        Returns:
            Updated Schedule or None if not found.
        """
        schedule = self.get_by_id(schedule_id)
        if schedule is None:
            return None

        if name is not None:
            schedule.name = name
        if description is not None:
            schedule.description = description
        if cron_expression is not None:
            schedule.cron_expression = cron_expression
        if timezone is not None:
            schedule.timezone = timezone
        if is_enabled is not None:
            schedule.is_enabled = is_enabled
        if next_run_at is not None:
            schedule.next_run_at = next_run_at
        if last_run_at is not None:
            schedule.last_run_at = last_run_at
        if last_run_status is not None:
            schedule.last_run_status = last_run_status

        schedule.updated_at = datetime.utcnow()
        return schedule

    def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a schedule.

        Args:
            schedule_id: ID of the schedule.

        Returns:
            True if deleted, False if not found.
        """
        schedule = self.get_by_id(schedule_id)
        if schedule is None:
            return False
        self.delete(schedule)
        return True

    # =========================================================================
    # Schedule Run Operations
    # =========================================================================

    def create_run(
        self,
        schedule_id: int,
        started_at: datetime | None = None,
    ) -> ScheduleRun:
        """Create a new schedule run record.

        Args:
            schedule_id: ID of the schedule.
            started_at: Start time (defaults to now).

        Returns:
            Created ScheduleRun instance.
        """
        run = ScheduleRun(
            schedule_id=schedule_id,
            started_at=started_at or datetime.utcnow(),
            status="running",
        )
        self.session.add(run)
        self.flush()
        return run

    def complete_run(
        self,
        run_id: int,
        status: str,
        result_summary: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> ScheduleRun | None:
        """Complete a schedule run.

        Args:
            run_id: ID of the run.
            status: Final status (success, failed).
            result_summary: Optional result summary.
            error_message: Optional error message.

        Returns:
            Updated ScheduleRun or None if not found.
        """
        run = self.session.get(ScheduleRun, run_id)
        if run is None:
            return None

        run.completed_at = datetime.utcnow()
        run.status = status
        run.result_summary = result_summary
        run.error_message = error_message

        return run

    def get_runs_for_schedule(
        self,
        schedule_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ScheduleRun]:
        """Get runs for a schedule.

        Args:
            schedule_id: ID of the schedule.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of ScheduleRun instances.
        """
        stmt = (
            select(ScheduleRun)
            .where(ScheduleRun.schedule_id == schedule_id)
            .order_by(ScheduleRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def get_recent_runs(self, limit: int = 10) -> list[ScheduleRun]:
        """Get recent runs across all schedules.

        Args:
            limit: Maximum results.

        Returns:
            List of recent ScheduleRun instances.
        """
        stmt = (
            select(ScheduleRun)
            .options(joinedload(ScheduleRun.schedule))
            .order_by(ScheduleRun.started_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    # =========================================================================
    # Aggregate Queries
    # =========================================================================

    def count_schedules(self, enabled_only: bool = False) -> int:
        """Count schedules.

        Args:
            enabled_only: Only count enabled schedules.

        Returns:
            Number of schedules.
        """
        stmt = select(func.count(Schedule.id))
        if enabled_only:
            stmt = stmt.where(Schedule.is_enabled == True)  # noqa: E712
        return self.session.scalar(stmt) or 0

    def count_schedules_by_type(self) -> dict[str, int]:
        """Count schedules grouped by job type.

        Returns:
            Dict mapping job type to count.
        """
        stmt = (
            select(Schedule.job_type, func.count(Schedule.id))
            .group_by(Schedule.job_type)
        )
        results = self.session.execute(stmt).all()
        return dict(results)


class NotificationRepository(BaseRepository[NotificationChannel]):
    """Repository for Notification CRUD operations."""

    model = NotificationChannel

    # =========================================================================
    # Channel Operations
    # =========================================================================

    def get_channel_by_name(self, name: str) -> NotificationChannel | None:
        """Get channel by name.

        Args:
            name: Channel name.

        Returns:
            NotificationChannel instance or None.
        """
        stmt = select(NotificationChannel).where(NotificationChannel.name == name)
        return self.session.scalar(stmt)

    def get_channel_with_rules(self, channel_id: int) -> NotificationChannel | None:
        """Get channel with rules loaded.

        Args:
            channel_id: ID of the channel.

        Returns:
            NotificationChannel with loaded rules or None.
        """
        stmt = (
            select(NotificationChannel)
            .options(joinedload(NotificationChannel.rules))
            .where(NotificationChannel.id == channel_id)
        )
        return self.session.scalar(stmt)

    def list_channels(
        self,
        channel_type: str | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[NotificationChannel]:
        """List notification channels.

        Args:
            channel_type: Filter by channel type.
            enabled_only: Only return enabled channels.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of NotificationChannel instances.
        """
        stmt = select(NotificationChannel)

        if channel_type is not None:
            stmt = stmt.where(NotificationChannel.channel_type == channel_type)

        if enabled_only:
            stmt = stmt.where(NotificationChannel.is_enabled == True)  # noqa: E712

        stmt = stmt.order_by(NotificationChannel.name)
        stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt))

    def create_channel(
        self,
        name: str,
        channel_type: str,
        config: dict[str, Any],
    ) -> NotificationChannel:
        """Create a notification channel.

        Args:
            name: Unique channel name.
            channel_type: Channel type (email, slack, webhook).
            config: Channel-specific configuration.

        Returns:
            Created NotificationChannel instance.
        """
        channel = NotificationChannel(
            name=name,
            channel_type=channel_type,
            config=config,
        )
        self.add(channel)
        self.flush()
        return channel

    def update_channel(
        self,
        channel_id: int,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        is_enabled: bool | None = None,
    ) -> NotificationChannel | None:
        """Update a notification channel.

        Args:
            channel_id: ID of the channel.
            name: New name.
            config: New configuration.
            is_enabled: New enabled status.

        Returns:
            Updated NotificationChannel or None.
        """
        channel = self.get_by_id(channel_id)
        if channel is None:
            return None

        if name is not None:
            channel.name = name
        if config is not None:
            channel.config = config
        if is_enabled is not None:
            channel.is_enabled = is_enabled

        channel.updated_at = datetime.utcnow()
        return channel

    def delete_channel(self, channel_id: int) -> bool:
        """Delete a notification channel.

        Args:
            channel_id: ID of the channel.

        Returns:
            True if deleted, False if not found.
        """
        channel = self.get_by_id(channel_id)
        if channel is None:
            return False
        self.delete(channel)
        return True

    # =========================================================================
    # Rule Operations
    # =========================================================================

    def get_rule(self, rule_id: int) -> NotificationRule | None:
        """Get rule by ID.

        Args:
            rule_id: ID of the rule.

        Returns:
            NotificationRule instance or None.
        """
        return self.session.get(NotificationRule, rule_id)

    def get_rule_with_channel(self, rule_id: int) -> NotificationRule | None:
        """Get rule with channel loaded.

        Args:
            rule_id: ID of the rule.

        Returns:
            NotificationRule with loaded channel or None.
        """
        stmt = (
            select(NotificationRule)
            .options(joinedload(NotificationRule.channel))
            .where(NotificationRule.id == rule_id)
        )
        return self.session.scalar(stmt)

    def list_rules(
        self,
        event_type: str | None = None,
        channel_id: int | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[NotificationRule]:
        """List notification rules.

        Args:
            event_type: Filter by event type.
            channel_id: Filter by channel ID.
            enabled_only: Only return enabled rules.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of NotificationRule instances.
        """
        stmt = (
            select(NotificationRule)
            .options(joinedload(NotificationRule.channel))
        )

        if event_type is not None:
            stmt = stmt.where(NotificationRule.event_type == event_type)

        if channel_id is not None:
            stmt = stmt.where(NotificationRule.channel_id == channel_id)

        if enabled_only:
            stmt = stmt.where(NotificationRule.is_enabled == True)  # noqa: E712

        stmt = stmt.order_by(NotificationRule.name)
        stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt).unique())

    def get_rules_for_event(self, event_type: str) -> list[NotificationRule]:
        """Get all enabled rules for an event type.

        Args:
            event_type: Event type to match.

        Returns:
            List of matching enabled rules.
        """
        stmt = (
            select(NotificationRule)
            .options(joinedload(NotificationRule.channel))
            .where(
                and_(
                    NotificationRule.event_type == event_type,
                    NotificationRule.is_enabled == True,  # noqa: E712
                )
            )
        )
        return list(self.session.scalars(stmt).unique())

    def create_rule(
        self,
        name: str,
        event_type: str,
        channel_id: int,
        conditions: dict[str, Any] | None = None,
        template_override: str | None = None,
    ) -> NotificationRule:
        """Create a notification rule.

        Args:
            name: Rule name.
            event_type: Event type to match.
            channel_id: Channel to send notifications to.
            conditions: Optional filtering conditions.
            template_override: Optional custom message template.

        Returns:
            Created NotificationRule instance.
        """
        rule = NotificationRule(
            name=name,
            event_type=event_type,
            channel_id=channel_id,
            conditions=conditions,
            template_override=template_override,
        )
        self.session.add(rule)
        self.flush()
        return rule

    def update_rule(
        self,
        rule_id: int,
        name: str | None = None,
        event_type: str | None = None,
        conditions: dict[str, Any] | None = None,
        channel_id: int | None = None,
        template_override: str | None = None,
        is_enabled: bool | None = None,
    ) -> NotificationRule | None:
        """Update a notification rule.

        Args:
            rule_id: ID of the rule.
            name: New name.
            event_type: New event type.
            conditions: New conditions.
            channel_id: New channel ID.
            template_override: New template.
            is_enabled: New enabled status.

        Returns:
            Updated NotificationRule or None.
        """
        rule = self.get_rule(rule_id)
        if rule is None:
            return None

        if name is not None:
            rule.name = name
        if event_type is not None:
            rule.event_type = event_type
        if conditions is not None:
            rule.conditions = conditions
        if channel_id is not None:
            rule.channel_id = channel_id
        if template_override is not None:
            rule.template_override = template_override
        if is_enabled is not None:
            rule.is_enabled = is_enabled

        rule.updated_at = datetime.utcnow()
        return rule

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a notification rule.

        Args:
            rule_id: ID of the rule.

        Returns:
            True if deleted, False if not found.
        """
        rule = self.get_rule(rule_id)
        if rule is None:
            return False
        self.session.delete(rule)
        return True

    # =========================================================================
    # Notification Log Operations
    # =========================================================================

    def create_log_entry(
        self,
        event_type: str,
        event_payload: dict[str, Any],
        status: str,
        rule_id: int | None = None,
        channel_id: int | None = None,
        error_message: str | None = None,
    ) -> NotificationLog:
        """Create a notification log entry.

        Args:
            event_type: Event type.
            event_payload: Event data.
            status: Notification status (sent, failed, rate_limited).
            rule_id: Associated rule ID.
            channel_id: Associated channel ID.
            error_message: Error message if failed.

        Returns:
            Created NotificationLog instance.
        """
        log_entry = NotificationLog(
            rule_id=rule_id,
            channel_id=channel_id,
            event_type=event_type,
            event_payload=event_payload,
            status=status,
            error_message=error_message,
        )
        self.session.add(log_entry)
        self.flush()
        return log_entry

    def list_log_entries(
        self,
        event_type: str | None = None,
        status: str | None = None,
        channel_id: int | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NotificationLog]:
        """List notification log entries.

        Args:
            event_type: Filter by event type.
            status: Filter by status.
            channel_id: Filter by channel ID.
            since: Filter by sent_at >= since.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of NotificationLog instances.
        """
        stmt = select(NotificationLog)

        if event_type is not None:
            stmt = stmt.where(NotificationLog.event_type == event_type)

        if status is not None:
            stmt = stmt.where(NotificationLog.status == status)

        if channel_id is not None:
            stmt = stmt.where(NotificationLog.channel_id == channel_id)

        if since is not None:
            stmt = stmt.where(NotificationLog.sent_at >= since)

        stmt = stmt.order_by(NotificationLog.sent_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        return list(self.session.scalars(stmt))

    def get_recent_logs(self, limit: int = 10) -> list[NotificationLog]:
        """Get recent notification logs.

        Args:
            limit: Maximum results.

        Returns:
            List of recent NotificationLog instances.
        """
        return self.list_log_entries(limit=limit)

    # =========================================================================
    # Aggregate Queries
    # =========================================================================

    def count_channels(self, enabled_only: bool = False) -> int:
        """Count notification channels.

        Args:
            enabled_only: Only count enabled channels.

        Returns:
            Number of channels.
        """
        stmt = select(func.count(NotificationChannel.id))
        if enabled_only:
            stmt = stmt.where(NotificationChannel.is_enabled == True)  # noqa: E712
        return self.session.scalar(stmt) or 0

    def count_rules(self, enabled_only: bool = False) -> int:
        """Count notification rules.

        Args:
            enabled_only: Only count enabled rules.

        Returns:
            Number of rules.
        """
        stmt = select(func.count(NotificationRule.id))
        if enabled_only:
            stmt = stmt.where(NotificationRule.is_enabled == True)  # noqa: E712
        return self.session.scalar(stmt) or 0

    def count_notifications_by_status(
        self,
        days: int = 7,
    ) -> dict[str, int]:
        """Count notifications by status in recent days.

        Args:
            days: Number of days to look back.

        Returns:
            Dict mapping status to count.
        """
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(NotificationLog.status, func.count(NotificationLog.id))
            .where(NotificationLog.sent_at >= since)
            .group_by(NotificationLog.status)
        )
        results = self.session.execute(stmt).all()
        return dict(results)
