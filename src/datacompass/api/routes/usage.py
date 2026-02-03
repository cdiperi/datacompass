"""Usage Metrics API endpoints."""

from fastapi import APIRouter, Query

from datacompass.api.dependencies import UsageServiceDep
from datacompass.core.models.usage import (
    HotTableItem,
    UsageCollectResult,
    UsageHubSummary,
    UsageMetricDetailResponse,
    UsageMetricResponse,
)

router = APIRouter(prefix="/usage", tags=["usage"])


# =============================================================================
# Collection
# =============================================================================


@router.post("/sources/{source_name}/collect", response_model=UsageCollectResult)
async def collect_usage_metrics(
    source_name: str,
    usage_service: UsageServiceDep,
) -> UsageCollectResult:
    """Collect usage metrics for all objects in a source.

    Triggers a collection run that fetches usage statistics from the
    source database and stores them as historical snapshots.

    Raises:
        404: If source not found.
    """
    return usage_service.collect_metrics(source_name)


# =============================================================================
# Object Metrics
# =============================================================================


@router.get("/objects/{object_id}", response_model=UsageMetricDetailResponse | None)
async def get_object_usage(
    object_id: int,
    usage_service: UsageServiceDep,
) -> UsageMetricDetailResponse | None:
    """Get latest usage metrics for an object.

    Returns the most recently collected usage metrics for the specified object.

    Raises:
        404: If object not found.
    """
    return usage_service.get_object_usage(object_id)


@router.get("/objects/{object_id}/history", response_model=list[UsageMetricResponse])
async def get_object_usage_history(
    object_id: int,
    usage_service: UsageServiceDep,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int | None = Query(None, ge=1, le=1000, description="Maximum number of records"),
) -> list[UsageMetricResponse]:
    """Get historical usage metrics for an object.

    Returns a time series of usage metrics collected over the specified period.

    Raises:
        404: If object not found.
    """
    return usage_service.get_usage_history(
        object_id,
        days=days,
        limit=limit,
    )


# =============================================================================
# Hot Tables
# =============================================================================


@router.get("/hot", response_model=list[HotTableItem])
async def get_hot_tables(
    usage_service: UsageServiceDep,
    source_name: str | None = Query(None, description="Filter by source name"),
    days: int = Query(7, ge=1, le=365, description="Look back period in days"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    order_by: str = Query(
        "read_count",
        description="Metric to order by (read_count, write_count, row_count, size_bytes)",
    ),
) -> list[HotTableItem]:
    """Get the most accessed tables (hot tables).

    Returns a ranked list of tables based on the specified usage metric,
    using the most recent metrics collected within the look-back period.
    """
    return usage_service.get_hot_tables(
        source_name=source_name,
        days=days,
        limit=limit,
        order_by=order_by,
    )


# =============================================================================
# Hub Summary
# =============================================================================


@router.get("/hub/summary", response_model=UsageHubSummary)
async def get_usage_hub_summary(
    usage_service: UsageServiceDep,
    source_name: str | None = Query(None, description="Filter by source name"),
) -> UsageHubSummary:
    """Get usage metrics hub summary.

    Returns aggregated statistics about usage metrics collection,
    including counts and top accessed tables.
    """
    return usage_service.get_hub_summary(source_name=source_name)
