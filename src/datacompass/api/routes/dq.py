"""Data Quality API endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from datacompass.api.dependencies import DQServiceDep
from datacompass.core.models.dq import (
    BreachDetailResponse,
    BreachStatusUpdate,
    DQConfigCreate,
    DQConfigDetailResponse,
    DQConfigListItem,
    DQExpectationCreate,
    DQExpectationResponse,
    DQExpectationUpdate,
    DQHubSummary,
    DQRunResult,
)

router = APIRouter(prefix="/dq", tags=["data-quality"])


# =============================================================================
# Configs
# =============================================================================


@router.get("/configs", response_model=list[DQConfigListItem])
async def list_configs(
    dq_service: DQServiceDep,
    source_id: int | None = Query(None, description="Filter by source ID"),
    enabled_only: bool = Query(False, description="Only show enabled configs"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> list[DQConfigListItem]:
    """List DQ configurations.

    Returns a list of DQ configs with summary information including
    expectation counts and open breach counts.
    """
    return dq_service.list_configs(
        source_id=source_id,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )


@router.post("/configs", response_model=DQConfigDetailResponse, status_code=201)
async def create_config(
    data: DQConfigCreate,
    dq_service: DQServiceDep,
) -> DQConfigDetailResponse:
    """Create a new DQ configuration.

    Creates a DQ config for a catalog object. Each object can have
    at most one DQ config.

    Raises:
        404: If object not found.
        409: If config already exists for object.
    """
    return dq_service.create_config(
        object_id=data.object_id,
        date_column=data.date_column,
        grain=data.grain,
    )


@router.get("/configs/{config_id}", response_model=DQConfigDetailResponse)
async def get_config(
    config_id: int,
    dq_service: DQServiceDep,
) -> DQConfigDetailResponse:
    """Get DQ configuration by ID.

    Returns the full config with all expectations.

    Raises:
        404: If config not found.
    """
    return dq_service.get_config(config_id)


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(
    config_id: int,
    dq_service: DQServiceDep,
) -> None:
    """Delete a DQ configuration.

    Deletes the config and all associated expectations, results,
    and breaches.

    Raises:
        404: If config not found.
    """
    dq_service.delete_config(config_id)


# =============================================================================
# Expectations
# =============================================================================


@router.post("/expectations", response_model=DQExpectationResponse, status_code=201)
async def create_expectation(
    data: DQExpectationCreate,
    dq_service: DQServiceDep,
) -> DQExpectationResponse:
    """Create a new DQ expectation.

    Adds an expectation to an existing DQ config. Each expectation
    defines a metric to check and threshold for breach detection.

    Raises:
        404: If config not found.
    """
    return dq_service.create_expectation(
        config_id=data.config_id,
        expectation_type=data.expectation_type,
        threshold_config=data.threshold_config.model_dump(),
        column_name=data.column_name,
        priority=data.priority,
    )


@router.patch("/expectations/{expectation_id}", response_model=DQExpectationResponse)
async def update_expectation(
    expectation_id: int,
    data: DQExpectationUpdate,
    dq_service: DQServiceDep,
) -> DQExpectationResponse:
    """Update a DQ expectation.

    Partially updates an expectation. Only provided fields are updated.

    Raises:
        404: If expectation not found.
    """
    return dq_service.update_expectation(
        expectation_id=expectation_id,
        expectation_type=data.expectation_type,
        column_name=data.column_name,
        threshold_config=data.threshold_config.model_dump() if data.threshold_config else None,
        priority=data.priority,
        is_enabled=data.is_enabled,
    )


@router.delete("/expectations/{expectation_id}", status_code=204)
async def delete_expectation(
    expectation_id: int,
    dq_service: DQServiceDep,
) -> None:
    """Delete a DQ expectation.

    Deletes the expectation and all associated results and breaches.

    Raises:
        404: If expectation not found.
    """
    dq_service.delete_expectation(expectation_id)


# =============================================================================
# Execution
# =============================================================================


@router.post("/configs/{config_id}/run", response_model=DQRunResult)
async def run_config(
    config_id: int,
    dq_service: DQServiceDep,
    snapshot_date: Annotated[
        date | None,
        Query(description="Date for the check (defaults to today)"),
    ] = None,
) -> DQRunResult:
    """Run DQ checks for a configuration.

    Executes all enabled expectations for the config and records
    results and any breaches detected.

    Note: In Phase 6.0, this uses mock metric values. In a future
    phase, this will use actual adapter queries.

    Raises:
        404: If config not found.
    """
    return dq_service.run_expectations(config_id, snapshot_date)


# =============================================================================
# Breaches
# =============================================================================


@router.get("/breaches", response_model=list[BreachDetailResponse])
async def list_breaches(
    dq_service: DQServiceDep,
    status: str | None = Query(None, description="Filter by status"),
    priority: str | None = Query(None, description="Filter by priority"),
    source_id: int | None = Query(None, description="Filter by source ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> list[BreachDetailResponse]:
    """List DQ breaches.

    Returns breaches with full details including object and
    expectation information.
    """
    return dq_service.list_breaches(
        status=status,
        priority=priority,
        source_id=source_id,
        limit=limit,
        offset=offset,
    )


@router.get("/breaches/{breach_id}", response_model=BreachDetailResponse)
async def get_breach(
    breach_id: int,
    dq_service: DQServiceDep,
) -> BreachDetailResponse:
    """Get breach details.

    Returns full breach information including lifecycle events.

    Raises:
        404: If breach not found.
    """
    return dq_service.get_breach(breach_id)


@router.patch("/breaches/{breach_id}/status", response_model=BreachDetailResponse)
async def update_breach_status(
    breach_id: int,
    data: BreachStatusUpdate,
    dq_service: DQServiceDep,
) -> BreachDetailResponse:
    """Update breach status.

    Updates the status and adds a lifecycle event. Valid statuses
    are: acknowledged, dismissed, resolved.

    Raises:
        404: If breach not found.
    """
    return dq_service.update_breach_status(
        breach_id=breach_id,
        status=data.status,
        notes=data.notes,
        updated_by="api",
    )


# =============================================================================
# Hub
# =============================================================================


@router.get("/hub/summary", response_model=DQHubSummary)
async def get_hub_summary(
    dq_service: DQServiceDep,
) -> DQHubSummary:
    """Get DQ hub dashboard summary.

    Returns aggregated statistics including config counts,
    breach counts by priority and status, and recent breaches.
    """
    return dq_service.get_hub_summary()
