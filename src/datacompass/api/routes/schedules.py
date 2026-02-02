"""API routes for schedule management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from datacompass.api.dependencies import DbSession
from datacompass.core.models.scheduling import (
    ScheduleCreate,
    ScheduleDetailResponse,
    ScheduleResponse,
    ScheduleRunResponse,
    ScheduleUpdate,
    SchedulerHubSummary,
)
from datacompass.core.services.scheduling_service import SchedulingService

router = APIRouter(prefix="/schedules", tags=["schedules"])


def get_scheduling_service(session: DbSession) -> SchedulingService:
    """Get a SchedulingService instance with the current session."""
    return SchedulingService(session)


SchedulingServiceDep = Annotated[SchedulingService, Depends(get_scheduling_service)]


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(
    service: SchedulingServiceDep,
    job_type: str | None = Query(None, description="Filter by job type"),
    enabled_only: bool = Query(False, description="Only return enabled schedules"),
    limit: int | None = Query(None, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number to skip"),
) -> list[ScheduleResponse]:
    """List all schedules."""
    return service.list_schedules(
        job_type=job_type,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ScheduleResponse, status_code=201)
def create_schedule(
    service: SchedulingServiceDep,
    data: ScheduleCreate,
) -> ScheduleResponse:
    """Create a new schedule."""
    return service.create_schedule(
        name=data.name,
        job_type=data.job_type,
        cron_expression=data.cron_expression,
        description=data.description,
        target_id=data.target_id,
        timezone=data.timezone,
    )


@router.get("/hub/summary", response_model=SchedulerHubSummary)
def get_hub_summary(
    service: SchedulingServiceDep,
) -> SchedulerHubSummary:
    """Get scheduler hub summary dashboard data."""
    return service.get_hub_summary()


@router.get("/{schedule_id}", response_model=ScheduleDetailResponse)
def get_schedule(
    service: SchedulingServiceDep,
    schedule_id: int,
) -> ScheduleDetailResponse:
    """Get schedule details with recent runs."""
    return service.get_schedule(schedule_id)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    service: SchedulingServiceDep,
    schedule_id: int,
    data: ScheduleUpdate,
) -> ScheduleResponse:
    """Update a schedule."""
    return service.update_schedule(
        schedule_id=schedule_id,
        name=data.name,
        description=data.description,
        cron_expression=data.cron_expression,
        timezone=data.timezone,
        is_enabled=data.is_enabled,
    )


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    service: SchedulingServiceDep,
    schedule_id: int,
) -> None:
    """Delete a schedule."""
    service.delete_schedule(schedule_id)


@router.post("/{schedule_id}/run", response_model=ScheduleRunResponse, status_code=201)
def run_schedule_now(
    service: SchedulingServiceDep,
    schedule_id: int,
) -> ScheduleRunResponse:
    """Run a scheduled job immediately."""
    from datacompass.core.scheduler.jobs import execute_job

    # Verify schedule exists
    service.get_schedule(schedule_id)

    # Execute job
    execute_job(schedule_id)

    # Return the latest run
    runs = service.get_runs(schedule_id, limit=1)
    return runs[0] if runs else service.start_run(schedule_id)


@router.get("/{schedule_id}/runs", response_model=list[ScheduleRunResponse])
def get_schedule_runs(
    service: SchedulingServiceDep,
    schedule_id: int,
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number to skip"),
) -> list[ScheduleRunResponse]:
    """Get execution history for a schedule."""
    return service.get_runs(
        schedule_id=schedule_id,
        limit=limit,
        offset=offset,
    )
