"""Repository for Data Quality operations."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from datacompass.core.models import CatalogObject
from datacompass.core.models.dq import (
    DQBreach,
    DQConfig,
    DQExpectation,
    DQResult,
)
from datacompass.core.repositories.base import BaseRepository


class DQRepository(BaseRepository[DQConfig]):
    """Repository for DQ CRUD operations."""

    model = DQConfig

    # =========================================================================
    # Config Operations
    # =========================================================================

    def get_config_by_object_id(self, object_id: int) -> DQConfig | None:
        """Get DQ config for a catalog object.

        Args:
            object_id: ID of the catalog object.

        Returns:
            DQConfig instance or None if not found.
        """
        stmt = (
            select(DQConfig)
            .options(
                joinedload(DQConfig.expectations),
                joinedload(DQConfig.object).joinedload(CatalogObject.source),
            )
            .where(DQConfig.object_id == object_id)
        )
        return self.session.scalar(stmt)

    def get_config_with_details(self, config_id: int) -> DQConfig | None:
        """Get DQ config with object and expectations eagerly loaded.

        Args:
            config_id: ID of the DQ config.

        Returns:
            DQConfig instance with loaded relationships or None.
        """
        stmt = (
            select(DQConfig)
            .options(
                joinedload(DQConfig.expectations),
                joinedload(DQConfig.object).joinedload(CatalogObject.source),
            )
            .where(DQConfig.id == config_id)
        )
        return self.session.scalar(stmt)

    def list_configs(
        self,
        source_id: int | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DQConfig]:
        """List DQ configs with optional filters.

        Args:
            source_id: Filter by source ID.
            enabled_only: Only return enabled configs.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of DQConfig instances.
        """
        stmt = (
            select(DQConfig)
            .join(CatalogObject)
            .options(
                joinedload(DQConfig.expectations),
                joinedload(DQConfig.object).joinedload(CatalogObject.source),
            )
        )

        if source_id is not None:
            stmt = stmt.where(CatalogObject.source_id == source_id)

        if enabled_only:
            stmt = stmt.where(DQConfig.is_enabled == True)  # noqa: E712

        stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt).unique())

    def create_config(
        self,
        object_id: int,
        date_column: str | None = None,
        grain: str = "daily",
    ) -> DQConfig:
        """Create a new DQ config.

        Args:
            object_id: ID of the catalog object.
            date_column: Column for date partitioning.
            grain: Check granularity (daily, hourly).

        Returns:
            Created DQConfig instance.
        """
        config = DQConfig(
            object_id=object_id,
            date_column=date_column,
            grain=grain,
        )
        self.add(config)
        self.flush()
        return config

    def update_config(
        self,
        config_id: int,
        date_column: str | None = None,
        grain: str | None = None,
        is_enabled: bool | None = None,
    ) -> DQConfig | None:
        """Update a DQ config.

        Args:
            config_id: ID of the DQ config.
            date_column: New date column value.
            grain: New grain value.
            is_enabled: New enabled status.

        Returns:
            Updated DQConfig or None if not found.
        """
        config = self.get_by_id(config_id)
        if config is None:
            return None

        if date_column is not None:
            config.date_column = date_column
        if grain is not None:
            config.grain = grain
        if is_enabled is not None:
            config.is_enabled = is_enabled

        config.updated_at = datetime.utcnow()
        return config

    def delete_config(self, config_id: int) -> bool:
        """Delete a DQ config.

        Args:
            config_id: ID of the DQ config.

        Returns:
            True if deleted, False if not found.
        """
        config = self.get_by_id(config_id)
        if config is None:
            return False
        self.delete(config)
        return True

    # =========================================================================
    # Expectation Operations
    # =========================================================================

    def get_expectation(self, expectation_id: int) -> DQExpectation | None:
        """Get expectation by ID.

        Args:
            expectation_id: ID of the expectation.

        Returns:
            DQExpectation instance or None.
        """
        return self.session.get(DQExpectation, expectation_id)

    def get_expectation_with_config(self, expectation_id: int) -> DQExpectation | None:
        """Get expectation with config and object loaded.

        Args:
            expectation_id: ID of the expectation.

        Returns:
            DQExpectation with loaded relationships or None.
        """
        stmt = (
            select(DQExpectation)
            .options(
                joinedload(DQExpectation.config)
                .joinedload(DQConfig.object)
                .joinedload(CatalogObject.source),
            )
            .where(DQExpectation.id == expectation_id)
        )
        return self.session.scalar(stmt)

    def get_enabled_expectations(self, config_id: int) -> list[DQExpectation]:
        """Get all enabled expectations for a config.

        Args:
            config_id: ID of the DQ config.

        Returns:
            List of enabled DQExpectation instances.
        """
        stmt = (
            select(DQExpectation)
            .where(
                and_(
                    DQExpectation.config_id == config_id,
                    DQExpectation.is_enabled == True,  # noqa: E712
                )
            )
        )
        return list(self.session.scalars(stmt))

    def create_expectation(
        self,
        config_id: int,
        expectation_type: str,
        threshold_config: dict[str, Any],
        column_name: str | None = None,
        priority: str = "medium",
    ) -> DQExpectation:
        """Create a new expectation.

        Args:
            config_id: ID of the DQ config.
            expectation_type: Type of metric (row_count, null_count, etc.).
            threshold_config: Threshold configuration dict.
            column_name: Column for column-level metrics.
            priority: Expectation priority.

        Returns:
            Created DQExpectation instance.
        """
        expectation = DQExpectation(
            config_id=config_id,
            expectation_type=expectation_type,
            column_name=column_name,
            threshold_config=threshold_config,
            priority=priority,
        )
        self.session.add(expectation)
        self.flush()
        return expectation

    def update_expectation(
        self,
        expectation_id: int,
        expectation_type: str | None = None,
        column_name: str | None = None,
        threshold_config: dict[str, Any] | None = None,
        priority: str | None = None,
        is_enabled: bool | None = None,
    ) -> DQExpectation | None:
        """Update an expectation.

        Args:
            expectation_id: ID of the expectation.
            expectation_type: New type.
            column_name: New column name.
            threshold_config: New threshold config.
            priority: New priority.
            is_enabled: New enabled status.

        Returns:
            Updated DQExpectation or None if not found.
        """
        expectation = self.get_expectation(expectation_id)
        if expectation is None:
            return None

        if expectation_type is not None:
            expectation.expectation_type = expectation_type
        if column_name is not None:
            expectation.column_name = column_name
        if threshold_config is not None:
            expectation.threshold_config = threshold_config
        if priority is not None:
            expectation.priority = priority
        if is_enabled is not None:
            expectation.is_enabled = is_enabled

        expectation.updated_at = datetime.utcnow()
        return expectation

    def delete_expectation(self, expectation_id: int) -> bool:
        """Delete an expectation.

        Args:
            expectation_id: ID of the expectation.

        Returns:
            True if deleted, False if not found.
        """
        expectation = self.get_expectation(expectation_id)
        if expectation is None:
            return False
        self.session.delete(expectation)
        return True

    # =========================================================================
    # Result Operations
    # =========================================================================

    def get_result(self, expectation_id: int, snapshot_date: date) -> DQResult | None:
        """Get result for an expectation on a specific date.

        Args:
            expectation_id: ID of the expectation.
            snapshot_date: Date of the result.

        Returns:
            DQResult instance or None.
        """
        stmt = select(DQResult).where(
            and_(
                DQResult.expectation_id == expectation_id,
                DQResult.snapshot_date == snapshot_date,
            )
        )
        return self.session.scalar(stmt)

    def get_historical_results(
        self,
        expectation_id: int,
        days: int = 30,
        end_date: date | None = None,
    ) -> list[DQResult]:
        """Get historical results for threshold computation.

        Args:
            expectation_id: ID of the expectation.
            days: Number of days to look back.
            end_date: End date (defaults to today).

        Returns:
            List of DQResult instances ordered by date desc.
        """
        if end_date is None:
            end_date = date.today()

        from datetime import timedelta
        start_date = end_date - timedelta(days=days)

        stmt = (
            select(DQResult)
            .where(
                and_(
                    DQResult.expectation_id == expectation_id,
                    DQResult.snapshot_date >= start_date,
                    DQResult.snapshot_date < end_date,
                )
            )
            .order_by(DQResult.snapshot_date.desc())
        )
        return list(self.session.scalars(stmt))

    def get_historical_results_for_dow(
        self,
        expectation_id: int,
        target_date: date,
        lookback_days: int = 90,
    ) -> list[DQResult]:
        """Get historical results for the same day of week.

        Args:
            expectation_id: ID of the expectation.
            target_date: Date to match day of week.
            lookback_days: Number of days to look back.

        Returns:
            List of DQResult instances for matching day of week.
        """
        target_dow = target_date.weekday()

        # Get all results in the lookback window
        all_results = self.get_historical_results(
            expectation_id=expectation_id,
            days=lookback_days,
            end_date=target_date,
        )

        # Filter to matching day of week
        return [r for r in all_results if r.snapshot_date.weekday() == target_dow]

    def record_result(
        self,
        expectation_id: int,
        snapshot_date: date,
        metric_value: float,
        computed_threshold_low: float | None = None,
        computed_threshold_high: float | None = None,
        execution_time_ms: int | None = None,
    ) -> DQResult:
        """Record a DQ check result.

        Upserts by (expectation_id, snapshot_date).

        Args:
            expectation_id: ID of the expectation.
            snapshot_date: Date of the check.
            metric_value: Computed metric value.
            computed_threshold_low: Low threshold.
            computed_threshold_high: High threshold.
            execution_time_ms: Execution time in milliseconds.

        Returns:
            Created or updated DQResult instance.
        """
        existing = self.get_result(expectation_id, snapshot_date)

        if existing:
            existing.metric_value = metric_value
            existing.computed_threshold_low = computed_threshold_low
            existing.computed_threshold_high = computed_threshold_high
            existing.execution_time_ms = execution_time_ms
            return existing
        else:
            result = DQResult(
                expectation_id=expectation_id,
                snapshot_date=snapshot_date,
                metric_value=metric_value,
                computed_threshold_low=computed_threshold_low,
                computed_threshold_high=computed_threshold_high,
                execution_time_ms=execution_time_ms,
            )
            self.session.add(result)
            self.flush()
            return result

    # =========================================================================
    # Breach Operations
    # =========================================================================

    def get_breach(self, breach_id: int) -> DQBreach | None:
        """Get breach by ID.

        Args:
            breach_id: ID of the breach.

        Returns:
            DQBreach instance or None.
        """
        return self.session.get(DQBreach, breach_id)

    def get_breach_with_details(self, breach_id: int) -> DQBreach | None:
        """Get breach with full relationship tree.

        Args:
            breach_id: ID of the breach.

        Returns:
            DQBreach with loaded relationships or None.
        """
        stmt = (
            select(DQBreach)
            .options(
                joinedload(DQBreach.expectation)
                .joinedload(DQExpectation.config)
                .joinedload(DQConfig.object)
                .joinedload(CatalogObject.source),
            )
            .where(DQBreach.id == breach_id)
        )
        return self.session.scalar(stmt)

    def get_breach_by_expectation_date(
        self,
        expectation_id: int,
        snapshot_date: date,
    ) -> DQBreach | None:
        """Get breach for an expectation on a specific date.

        Args:
            expectation_id: ID of the expectation.
            snapshot_date: Date of the breach.

        Returns:
            DQBreach instance or None.
        """
        stmt = select(DQBreach).where(
            and_(
                DQBreach.expectation_id == expectation_id,
                DQBreach.snapshot_date == snapshot_date,
            )
        )
        return self.session.scalar(stmt)

    def list_breaches(
        self,
        status: str | None = None,
        priority: str | None = None,
        source_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DQBreach]:
        """List breaches with optional filters.

        Args:
            status: Filter by status (open, acknowledged, etc.).
            priority: Filter by priority.
            source_id: Filter by source ID.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of DQBreach instances.
        """
        stmt = (
            select(DQBreach)
            .join(DQExpectation)
            .join(DQConfig)
            .join(CatalogObject)
            .options(
                joinedload(DQBreach.expectation)
                .joinedload(DQExpectation.config)
                .joinedload(DQConfig.object)
                .joinedload(CatalogObject.source),
            )
        )

        if status is not None:
            stmt = stmt.where(DQBreach.status == status)

        if priority is not None:
            stmt = stmt.where(DQExpectation.priority == priority)

        if source_id is not None:
            stmt = stmt.where(CatalogObject.source_id == source_id)

        stmt = stmt.order_by(DQBreach.detected_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        return list(self.session.scalars(stmt).unique())

    def create_breach(
        self,
        expectation_id: int,
        result_id: int,
        snapshot_date: date,
        metric_value: float,
        breach_direction: str,
        threshold_value: float,
        deviation_value: float,
        deviation_percent: float,
        threshold_snapshot: dict[str, Any],
    ) -> DQBreach:
        """Create a new breach record.

        Args:
            expectation_id: ID of the expectation.
            result_id: ID of the result.
            snapshot_date: Date of the breach.
            metric_value: Actual metric value.
            breach_direction: 'high' or 'low'.
            threshold_value: Threshold that was breached.
            deviation_value: Absolute deviation.
            deviation_percent: Percentage deviation.
            threshold_snapshot: Threshold config at detection time.

        Returns:
            Created DQBreach instance.
        """
        # Check for existing breach
        existing = self.get_breach_by_expectation_date(expectation_id, snapshot_date)
        if existing:
            # Update existing breach
            existing.result_id = result_id
            existing.metric_value = metric_value
            existing.breach_direction = breach_direction
            existing.threshold_value = threshold_value
            existing.deviation_value = deviation_value
            existing.deviation_percent = deviation_percent
            existing.threshold_snapshot = threshold_snapshot
            existing.updated_at = datetime.utcnow()
            return existing

        breach = DQBreach(
            expectation_id=expectation_id,
            result_id=result_id,
            snapshot_date=snapshot_date,
            metric_value=metric_value,
            breach_direction=breach_direction,
            threshold_value=threshold_value,
            deviation_value=deviation_value,
            deviation_percent=deviation_percent,
            threshold_snapshot=threshold_snapshot,
        )
        self.session.add(breach)
        self.flush()
        return breach

    def update_breach_status(
        self,
        breach_id: int,
        status: str,
        notes: str | None = None,
        updated_by: str = "system",
    ) -> DQBreach | None:
        """Update breach status with lifecycle event.

        Args:
            breach_id: ID of the breach.
            status: New status (acknowledged, dismissed, resolved).
            notes: Optional notes for the lifecycle event.
            updated_by: Who made the change.

        Returns:
            Updated DQBreach or None if not found.
        """
        breach = self.get_breach(breach_id)
        if breach is None:
            return None

        # Add lifecycle event
        event = {
            "status": status,
            "by": updated_by,
            "at": datetime.utcnow().isoformat(),
        }
        if notes:
            event["notes"] = notes

        # Update lifecycle events (create new list to trigger JSON update)
        events = list(breach.lifecycle_events) if breach.lifecycle_events else []
        events.append(event)
        breach.lifecycle_events = events

        breach.status = status
        breach.updated_at = datetime.utcnow()

        return breach

    # =========================================================================
    # Aggregate Queries
    # =========================================================================

    def count_configs(self, enabled_only: bool = False) -> int:
        """Count DQ configs.

        Args:
            enabled_only: Only count enabled configs.

        Returns:
            Number of configs.
        """
        stmt = select(func.count(DQConfig.id))
        if enabled_only:
            stmt = stmt.where(DQConfig.is_enabled == True)  # noqa: E712
        return self.session.scalar(stmt) or 0

    def count_expectations(self, enabled_only: bool = False) -> int:
        """Count DQ expectations.

        Args:
            enabled_only: Only count enabled expectations.

        Returns:
            Number of expectations.
        """
        stmt = select(func.count(DQExpectation.id))
        if enabled_only:
            stmt = stmt.where(DQExpectation.is_enabled == True)  # noqa: E712
        return self.session.scalar(stmt) or 0

    def count_breaches_by_status(self) -> dict[str, int]:
        """Count breaches grouped by status.

        Returns:
            Dict mapping status to count.
        """
        stmt = (
            select(DQBreach.status, func.count(DQBreach.id))
            .group_by(DQBreach.status)
        )
        results = self.session.execute(stmt).all()
        return dict(results)

    def count_open_breaches_by_priority(self) -> dict[str, int]:
        """Count open breaches grouped by priority.

        Returns:
            Dict mapping priority to count.
        """
        stmt = (
            select(DQExpectation.priority, func.count(DQBreach.id))
            .join(DQExpectation)
            .where(DQBreach.status == "open")
            .group_by(DQExpectation.priority)
        )
        results = self.session.execute(stmt).all()
        return dict(results)

    def get_open_breach_count_for_config(self, config_id: int) -> int:
        """Get count of open breaches for a config.

        Args:
            config_id: ID of the DQ config.

        Returns:
            Number of open breaches.
        """
        stmt = (
            select(func.count(DQBreach.id))
            .join(DQExpectation)
            .where(
                and_(
                    DQExpectation.config_id == config_id,
                    DQBreach.status == "open",
                )
            )
        )
        return self.session.scalar(stmt) or 0
