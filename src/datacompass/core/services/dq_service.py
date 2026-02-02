"""Service for Data Quality operations."""

import random
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from datacompass.core.models.dq import (
    BreachDetailResponse,
    DQBreach,
    DQConfig,
    DQConfigDetailResponse,
    DQConfigListItem,
    DQExpectation,
    DQExpectationResponse,
    DQHubSummary,
    DQResult,
    DQRunResult,
    DQRunResultItem,
    ThresholdConfig,
    YAMLDQConfig,
)
from datacompass.core.events import DQBreachEvent, get_event_bus
from datacompass.core.repositories import CatalogObjectRepository
from datacompass.core.repositories.dq import DQRepository
from datacompass.core.services.catalog_service import CatalogService, ObjectNotFoundError


class DQServiceError(Exception):
    """Base exception for DQ service errors."""

    pass


class DQConfigNotFoundError(DQServiceError):
    """Raised when a DQ config is not found."""

    def __init__(self, identifier: str | int) -> None:
        self.identifier = identifier
        super().__init__(f"DQ config not found: {identifier}")


class DQExpectationNotFoundError(DQServiceError):
    """Raised when an expectation is not found."""

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier
        super().__init__(f"DQ expectation not found: {identifier}")


class DQBreachNotFoundError(DQServiceError):
    """Raised when a breach is not found."""

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier
        super().__init__(f"DQ breach not found: {identifier}")


class DQConfigExistsError(DQServiceError):
    """Raised when a DQ config already exists for an object."""

    def __init__(self, object_id: int) -> None:
        self.object_id = object_id
        super().__init__(f"DQ config already exists for object: {object_id}")


class DQService:
    """Service for data quality operations.

    Handles:
    - DQ config and expectation management
    - Threshold computation (absolute, simple_average, dow_adjusted)
    - Breach detection and lifecycle management
    - Hub summary aggregation
    """

    def __init__(self, session: Session) -> None:
        """Initialize DQ service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.dq_repo = DQRepository(session)
        self.object_repo = CatalogObjectRepository(session)
        self.catalog_service = CatalogService(session)

    # =========================================================================
    # Config Management
    # =========================================================================

    def get_config(self, config_id: int) -> DQConfigDetailResponse:
        """Get DQ config by ID.

        Args:
            config_id: ID of the DQ config.

        Returns:
            DQConfigDetailResponse with full details.

        Raises:
            DQConfigNotFoundError: If config not found.
        """
        config = self.dq_repo.get_config_with_details(config_id)
        if config is None:
            raise DQConfigNotFoundError(config_id)

        return self._config_to_detail_response(config)

    def get_config_by_object(self, object_identifier: str | int) -> DQConfigDetailResponse:
        """Get DQ config for a catalog object.

        Args:
            object_identifier: Object ID or source.schema.name.

        Returns:
            DQConfigDetailResponse with full details.

        Raises:
            ObjectNotFoundError: If object not found.
            DQConfigNotFoundError: If config not found.
        """
        obj = self.catalog_service.get_object(object_identifier)
        config = self.dq_repo.get_config_by_object_id(obj.id)
        if config is None:
            raise DQConfigNotFoundError(f"object:{object_identifier}")

        return self._config_to_detail_response(config)

    def list_configs(
        self,
        source_id: int | None = None,
        enabled_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DQConfigListItem]:
        """List DQ configs.

        Args:
            source_id: Filter by source.
            enabled_only: Only return enabled configs.
            limit: Maximum results.
            offset: Number of results to skip.

        Returns:
            List of DQConfigListItem.
        """
        configs = self.dq_repo.list_configs(
            source_id=source_id,
            enabled_only=enabled_only,
            limit=limit,
            offset=offset,
        )

        result = []
        for config in configs:
            open_breach_count = self.dq_repo.get_open_breach_count_for_config(config.id)
            result.append(
                DQConfigListItem(
                    id=config.id,
                    object_id=config.object_id,
                    object_name=config.object.object_name,
                    schema_name=config.object.schema_name,
                    source_name=config.object.source.name,
                    date_column=config.date_column,
                    grain=config.grain,
                    is_enabled=config.is_enabled,
                    expectation_count=len(config.expectations),
                    open_breach_count=open_breach_count,
                )
            )
        return result

    def create_config(
        self,
        object_id: int,
        date_column: str | None = None,
        grain: str = "daily",
    ) -> DQConfigDetailResponse:
        """Create a new DQ config.

        Args:
            object_id: ID of the catalog object.
            date_column: Column for date partitioning.
            grain: Check granularity.

        Returns:
            Created DQConfigDetailResponse.

        Raises:
            ObjectNotFoundError: If object not found.
            DQConfigExistsError: If config already exists.
        """
        # Verify object exists
        obj = self.object_repo.get_by_id(object_id)
        if obj is None:
            raise ObjectNotFoundError(str(object_id))

        # Check for existing config
        existing = self.dq_repo.get_config_by_object_id(object_id)
        if existing is not None:
            raise DQConfigExistsError(object_id)

        config = self.dq_repo.create_config(
            object_id=object_id,
            date_column=date_column,
            grain=grain,
        )

        # Reload with relationships
        config = self.dq_repo.get_config_with_details(config.id)
        return self._config_to_detail_response(config)

    def update_config(
        self,
        config_id: int,
        date_column: str | None = None,
        grain: str | None = None,
        is_enabled: bool | None = None,
    ) -> DQConfigDetailResponse:
        """Update a DQ config.

        Args:
            config_id: ID of the DQ config.
            date_column: New date column value.
            grain: New grain value.
            is_enabled: New enabled status.

        Returns:
            Updated DQConfigDetailResponse.

        Raises:
            DQConfigNotFoundError: If config not found.
        """
        config = self.dq_repo.update_config(
            config_id=config_id,
            date_column=date_column,
            grain=grain,
            is_enabled=is_enabled,
        )

        if config is None:
            raise DQConfigNotFoundError(config_id)

        # Reload with relationships
        config = self.dq_repo.get_config_with_details(config_id)
        return self._config_to_detail_response(config)

    def delete_config(self, config_id: int) -> bool:
        """Delete a DQ config.

        Args:
            config_id: ID of the DQ config.

        Returns:
            True if deleted.

        Raises:
            DQConfigNotFoundError: If config not found.
        """
        if not self.dq_repo.delete_config(config_id):
            raise DQConfigNotFoundError(config_id)
        return True

    def create_config_from_yaml(self, yaml_path: Path) -> DQConfigDetailResponse:
        """Create or update DQ config from YAML file.

        Args:
            yaml_path: Path to YAML configuration file.

        Returns:
            Created/updated DQConfigDetailResponse.

        Raises:
            ObjectNotFoundError: If object not found.
            FileNotFoundError: If YAML file not found.
        """
        from datacompass.core.services import load_yaml_config

        if not yaml_path.exists():
            raise FileNotFoundError(yaml_path)

        raw_config = load_yaml_config(yaml_path)
        yaml_config = YAMLDQConfig.model_validate(raw_config)

        # Resolve object
        obj = self.catalog_service.get_object(yaml_config.object)

        # Get or create config
        existing = self.dq_repo.get_config_by_object_id(obj.id)
        if existing:
            config = self.dq_repo.update_config(
                config_id=existing.id,
                date_column=yaml_config.date_column,
                grain=yaml_config.grain,
            )
            # Delete existing expectations to replace with new ones
            for exp in existing.expectations:
                self.dq_repo.delete_expectation(exp.id)
        else:
            config = self.dq_repo.create_config(
                object_id=obj.id,
                date_column=yaml_config.date_column,
                grain=yaml_config.grain,
            )

        # Create expectations
        for yaml_exp in yaml_config.expectations:
            self.dq_repo.create_expectation(
                config_id=config.id,
                expectation_type=yaml_exp.type,
                column_name=yaml_exp.column,
                threshold_config=yaml_exp.threshold.model_dump(),
                priority=yaml_exp.priority,
            )

        # Reload with relationships
        config = self.dq_repo.get_config_with_details(config.id)
        return self._config_to_detail_response(config)

    def generate_yaml_template(self, object_identifier: str | int) -> str:
        """Generate a YAML template for an object.

        Args:
            object_identifier: Object ID or source.schema.name.

        Returns:
            YAML template string.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self.catalog_service.get_object(object_identifier)

        template = f"""# DQ Configuration for {obj.source_name}.{obj.schema_name}.{obj.object_name}
object: {obj.source_name}.{obj.schema_name}.{obj.object_name}
date_column: null  # Set to date column name if applicable
grain: daily

expectations:
  - type: row_count
    threshold:
      type: simple_average
      multiplier: 2.0
      lookback_days: 30
    priority: high

  # Add more expectations as needed:
  # - type: null_count
  #   column: column_name
  #   threshold:
  #     type: absolute
  #     max: 0
  #   priority: critical
"""
        return template

    # =========================================================================
    # Expectation Management
    # =========================================================================

    def create_expectation(
        self,
        config_id: int,
        expectation_type: str,
        threshold_config: dict[str, Any],
        column_name: str | None = None,
        priority: str = "medium",
    ) -> DQExpectationResponse:
        """Create a new expectation.

        Args:
            config_id: ID of the DQ config.
            expectation_type: Type of metric.
            threshold_config: Threshold configuration.
            column_name: Column for column-level metrics.
            priority: Expectation priority.

        Returns:
            Created DQExpectationResponse.

        Raises:
            DQConfigNotFoundError: If config not found.
        """
        config = self.dq_repo.get_by_id(config_id)
        if config is None:
            raise DQConfigNotFoundError(config_id)

        expectation = self.dq_repo.create_expectation(
            config_id=config_id,
            expectation_type=expectation_type,
            threshold_config=threshold_config,
            column_name=column_name,
            priority=priority,
        )

        return DQExpectationResponse.model_validate(expectation)

    def update_expectation(
        self,
        expectation_id: int,
        expectation_type: str | None = None,
        column_name: str | None = None,
        threshold_config: dict[str, Any] | None = None,
        priority: str | None = None,
        is_enabled: bool | None = None,
    ) -> DQExpectationResponse:
        """Update an expectation.

        Args:
            expectation_id: ID of the expectation.
            expectation_type: New type.
            column_name: New column name.
            threshold_config: New threshold config.
            priority: New priority.
            is_enabled: New enabled status.

        Returns:
            Updated DQExpectationResponse.

        Raises:
            DQExpectationNotFoundError: If expectation not found.
        """
        expectation = self.dq_repo.update_expectation(
            expectation_id=expectation_id,
            expectation_type=expectation_type,
            column_name=column_name,
            threshold_config=threshold_config,
            priority=priority,
            is_enabled=is_enabled,
        )

        if expectation is None:
            raise DQExpectationNotFoundError(expectation_id)

        return DQExpectationResponse.model_validate(expectation)

    def delete_expectation(self, expectation_id: int) -> bool:
        """Delete an expectation.

        Args:
            expectation_id: ID of the expectation.

        Returns:
            True if deleted.

        Raises:
            DQExpectationNotFoundError: If expectation not found.
        """
        if not self.dq_repo.delete_expectation(expectation_id):
            raise DQExpectationNotFoundError(expectation_id)
        return True

    # =========================================================================
    # Threshold Computation
    # =========================================================================

    def compute_threshold(
        self,
        expectation: DQExpectation,
        snapshot_date: date,
    ) -> tuple[float | None, float | None]:
        """Compute thresholds for an expectation.

        Args:
            expectation: The expectation to compute thresholds for.
            snapshot_date: Date for the check.

        Returns:
            Tuple of (low_threshold, high_threshold).
        """
        config = ThresholdConfig.model_validate(expectation.threshold_config)

        if config.type == "absolute":
            return self._compute_absolute_threshold(config)
        elif config.type == "simple_average":
            return self._compute_simple_average_threshold(
                expectation.id, config, snapshot_date
            )
        elif config.type == "dow_adjusted":
            return self._compute_dow_adjusted_threshold(
                expectation.id, config, snapshot_date
            )
        else:
            # Unknown type - fall back to no threshold
            return None, None

    def _compute_absolute_threshold(
        self,
        config: ThresholdConfig,
    ) -> tuple[float | None, float | None]:
        """Compute absolute thresholds.

        Args:
            config: Threshold configuration.

        Returns:
            Tuple of (min, max) from config.
        """
        return config.min, config.max

    def _compute_simple_average_threshold(
        self,
        expectation_id: int,
        config: ThresholdConfig,
        snapshot_date: date,
    ) -> tuple[float | None, float | None]:
        """Compute thresholds based on simple historical average.

        Args:
            expectation_id: ID of the expectation.
            config: Threshold configuration.
            snapshot_date: Date for the check.

        Returns:
            Tuple of (low, high) thresholds.
        """
        lookback_days = config.lookback_days or 30
        multiplier = config.multiplier or 2.0

        results = self.dq_repo.get_historical_results(
            expectation_id=expectation_id,
            days=lookback_days,
            end_date=snapshot_date,
        )

        if not results:
            # No historical data - return absolute bounds if set
            return config.min, config.max

        values = [r.metric_value for r in results]
        avg = sum(values) / len(values)
        std = (sum((v - avg) ** 2 for v in values) / len(values)) ** 0.5

        low = avg - (multiplier * std) if std > 0 else avg * 0.5
        high = avg + (multiplier * std) if std > 0 else avg * 1.5

        # Apply absolute bounds if set
        if config.min is not None:
            low = max(low, config.min)
        if config.max is not None:
            high = min(high, config.max)

        return low, high

    def _compute_dow_adjusted_threshold(
        self,
        expectation_id: int,
        config: ThresholdConfig,
        snapshot_date: date,
    ) -> tuple[float | None, float | None]:
        """Compute thresholds adjusted for day of week.

        Args:
            expectation_id: ID of the expectation.
            config: Threshold configuration.
            snapshot_date: Date for the check.

        Returns:
            Tuple of (low, high) thresholds.
        """
        lookback_days = config.lookback_days or 90
        multiplier = config.multiplier or 2.0

        results = self.dq_repo.get_historical_results_for_dow(
            expectation_id=expectation_id,
            target_date=snapshot_date,
            lookback_days=lookback_days,
        )

        if not results:
            # Fall back to simple average
            return self._compute_simple_average_threshold(
                expectation_id, config, snapshot_date
            )

        values = [r.metric_value for r in results]
        avg = sum(values) / len(values)
        std = (sum((v - avg) ** 2 for v in values) / len(values)) ** 0.5

        low = avg - (multiplier * std) if std > 0 else avg * 0.5
        high = avg + (multiplier * std) if std > 0 else avg * 1.5

        # Apply absolute bounds if set
        if config.min is not None:
            low = max(low, config.min)
        if config.max is not None:
            high = min(high, config.max)

        return low, high

    # =========================================================================
    # Execution
    # =========================================================================

    def run_expectations(
        self,
        config_id: int,
        snapshot_date: date | None = None,
    ) -> DQRunResult:
        """Run all enabled expectations for a config.

        Note: In Phase 6.0, this uses mock metric values.
        In a future phase, this will call adapter.execute_dq_query().

        Args:
            config_id: ID of the DQ config.
            snapshot_date: Date for the check (defaults to today).

        Returns:
            DQRunResult with all check results.

        Raises:
            DQConfigNotFoundError: If config not found.
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        config = self.dq_repo.get_config_with_details(config_id)
        if config is None:
            raise DQConfigNotFoundError(config_id)

        expectations = self.dq_repo.get_enabled_expectations(config_id)
        results: list[DQRunResultItem] = []
        passed = 0
        breached = 0

        for expectation in expectations:
            # Compute thresholds
            low, high = self.compute_threshold(expectation, snapshot_date)

            # Get metric value (mock for Phase 6.0)
            metric_value = self._get_mock_metric_value(expectation)

            # Record result
            result = self.dq_repo.record_result(
                expectation_id=expectation.id,
                snapshot_date=snapshot_date,
                metric_value=metric_value,
                computed_threshold_low=low,
                computed_threshold_high=high,
            )

            # Check for breach
            breach = self._detect_breach(expectation, result, low, high)

            if breach:
                breached += 1
                status = "breach"
                breach_id = breach.id
            else:
                passed += 1
                status = "pass"
                breach_id = None

            results.append(
                DQRunResultItem(
                    expectation_id=expectation.id,
                    expectation_type=expectation.expectation_type,
                    column_name=expectation.column_name,
                    metric_value=metric_value,
                    computed_threshold_low=low,
                    computed_threshold_high=high,
                    status=status,
                    breach_id=breach_id,
                )
            )

        return DQRunResult(
            config_id=config_id,
            object_name=config.object.object_name,
            schema_name=config.object.schema_name,
            source_name=config.object.source.name,
            snapshot_date=snapshot_date,
            total_checks=len(expectations),
            passed=passed,
            breached=breached,
            results=results,
        )

    def _get_mock_metric_value(self, expectation: DQExpectation) -> float:
        """Generate a mock metric value for testing.

        In a future phase, this will be replaced with actual
        adapter.execute_dq_query() calls.

        Args:
            expectation: The expectation to generate value for.

        Returns:
            Mock metric value.
        """
        # Generate reasonable mock values based on expectation type
        exp_type = expectation.expectation_type

        if exp_type == "row_count":
            return float(random.randint(10000, 20000))
        elif exp_type == "null_count":
            return float(random.randint(0, 10))
        elif exp_type == "distinct_count":
            return float(random.randint(5, 100))
        elif exp_type == "min":
            return float(random.randint(0, 100))
        elif exp_type == "max":
            return float(random.randint(900, 1000))
        elif exp_type == "mean":
            return float(random.randint(400, 600))
        elif exp_type == "sum":
            return float(random.randint(100000, 200000))
        else:
            return float(random.randint(0, 1000))

    def _detect_breach(
        self,
        expectation: DQExpectation,
        result: DQResult,
        low: float | None,
        high: float | None,
    ) -> DQBreach | None:
        """Detect if a result breaches thresholds.

        Args:
            expectation: The expectation.
            result: The result to check.
            low: Low threshold.
            high: High threshold.

        Returns:
            DQBreach if breach detected, None otherwise.
        """
        value = result.metric_value
        breach_direction = None
        threshold_value = None
        deviation_value = 0.0

        if low is not None and value < low:
            breach_direction = "low"
            threshold_value = low
            deviation_value = low - value
        elif high is not None and value > high:
            breach_direction = "high"
            threshold_value = high
            deviation_value = value - high

        if breach_direction is None:
            return None

        # Calculate deviation percent
        if threshold_value != 0:
            deviation_percent = (deviation_value / abs(threshold_value)) * 100
        else:
            deviation_percent = 100.0 if deviation_value != 0 else 0.0

        # Create breach
        breach = self.dq_repo.create_breach(
            expectation_id=expectation.id,
            result_id=result.id,
            snapshot_date=result.snapshot_date,
            metric_value=value,
            breach_direction=breach_direction,
            threshold_value=threshold_value,
            deviation_value=deviation_value,
            deviation_percent=deviation_percent,
            threshold_snapshot=expectation.threshold_config,
        )

        # Emit DQ breach event for notifications
        config = expectation.config
        obj = config.object
        event = DQBreachEvent.create(
            breach_id=breach.id,
            expectation_id=expectation.id,
            object_name=obj.object_name,
            schema_name=obj.schema_name,
            source_name=obj.source.name,
            expectation_type=expectation.expectation_type,
            column_name=expectation.column_name,
            metric_value=value,
            threshold_value=threshold_value,
            breach_direction=breach_direction,
            deviation_percent=deviation_percent,
            priority=expectation.priority,
            snapshot_date=str(result.snapshot_date),
        )
        get_event_bus().emit(event)

        return breach

    # =========================================================================
    # Breach Management
    # =========================================================================

    def get_breach(self, breach_id: int) -> BreachDetailResponse:
        """Get breach with full details.

        Args:
            breach_id: ID of the breach.

        Returns:
            BreachDetailResponse with full details.

        Raises:
            DQBreachNotFoundError: If breach not found.
        """
        breach = self.dq_repo.get_breach_with_details(breach_id)
        if breach is None:
            raise DQBreachNotFoundError(breach_id)

        return self._breach_to_detail_response(breach)

    def list_breaches(
        self,
        status: str | None = None,
        priority: str | None = None,
        source_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BreachDetailResponse]:
        """List breaches with optional filters.

        Args:
            status: Filter by status.
            priority: Filter by priority.
            source_id: Filter by source.
            limit: Maximum results.
            offset: Number to skip.

        Returns:
            List of BreachDetailResponse.
        """
        breaches = self.dq_repo.list_breaches(
            status=status,
            priority=priority,
            source_id=source_id,
            limit=limit,
            offset=offset,
        )

        return [self._breach_to_detail_response(b) for b in breaches]

    def update_breach_status(
        self,
        breach_id: int,
        status: str,
        notes: str | None = None,
        updated_by: str = "system",
    ) -> BreachDetailResponse:
        """Update breach status.

        Args:
            breach_id: ID of the breach.
            status: New status.
            notes: Optional notes.
            updated_by: Who made the change.

        Returns:
            Updated BreachDetailResponse.

        Raises:
            DQBreachNotFoundError: If breach not found.
        """
        breach = self.dq_repo.update_breach_status(
            breach_id=breach_id,
            status=status,
            notes=notes,
            updated_by=updated_by,
        )

        if breach is None:
            raise DQBreachNotFoundError(breach_id)

        # Reload with full details
        breach = self.dq_repo.get_breach_with_details(breach_id)
        return self._breach_to_detail_response(breach)

    # =========================================================================
    # Hub Summary
    # =========================================================================

    def get_hub_summary(self) -> DQHubSummary:
        """Get DQ hub dashboard summary.

        Returns:
            DQHubSummary with aggregated data.
        """
        total_configs = self.dq_repo.count_configs()
        enabled_configs = self.dq_repo.count_configs(enabled_only=True)
        total_expectations = self.dq_repo.count_expectations()
        enabled_expectations = self.dq_repo.count_expectations(enabled_only=True)

        breaches_by_status = self.dq_repo.count_breaches_by_status()
        open_breaches = breaches_by_status.get("open", 0)
        breaches_by_priority = self.dq_repo.count_open_breaches_by_priority()

        # Get recent open breaches
        recent_breaches = self.list_breaches(status="open", limit=10)

        return DQHubSummary(
            total_configs=total_configs,
            enabled_configs=enabled_configs,
            total_expectations=total_expectations,
            enabled_expectations=enabled_expectations,
            open_breaches=open_breaches,
            breaches_by_priority=breaches_by_priority,
            breaches_by_status=breaches_by_status,
            recent_breaches=recent_breaches,
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _config_to_detail_response(self, config: DQConfig) -> DQConfigDetailResponse:
        """Convert DQConfig to DQConfigDetailResponse."""
        return DQConfigDetailResponse(
            id=config.id,
            object_id=config.object_id,
            object_name=config.object.object_name,
            schema_name=config.object.schema_name,
            source_name=config.object.source.name,
            date_column=config.date_column,
            grain=config.grain,
            is_enabled=config.is_enabled,
            expectations=[
                DQExpectationResponse.model_validate(e) for e in config.expectations
            ],
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    def _breach_to_detail_response(self, breach: DQBreach) -> BreachDetailResponse:
        """Convert DQBreach to BreachDetailResponse."""
        expectation = breach.expectation
        config = expectation.config
        obj = config.object

        return BreachDetailResponse(
            id=breach.id,
            expectation_id=breach.expectation_id,
            result_id=breach.result_id,
            snapshot_date=breach.snapshot_date,
            metric_value=breach.metric_value,
            breach_direction=breach.breach_direction,
            threshold_value=breach.threshold_value,
            deviation_value=breach.deviation_value,
            deviation_percent=breach.deviation_percent,
            status=breach.status,
            detected_at=breach.detected_at,
            created_at=breach.created_at,
            updated_at=breach.updated_at,
            object_id=obj.id,
            object_name=obj.object_name,
            schema_name=obj.schema_name,
            source_name=obj.source.name,
            expectation_type=expectation.expectation_type,
            column_name=expectation.column_name,
            priority=expectation.priority,
            threshold_snapshot=breach.threshold_snapshot,
            lifecycle_events=breach.lifecycle_events or [],
        )
