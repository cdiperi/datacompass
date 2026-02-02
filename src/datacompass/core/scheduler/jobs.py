"""Job executors for scheduled tasks.

Each job type has a corresponding executor function that handles
the actual work and records the results.
"""

import logging
from datetime import datetime
from typing import Any

from datacompass.core.database import get_session
from datacompass.core.events import (
    DeprecationDeadlineEvent,
    ScheduleRunCompletedEvent,
    get_event_bus,
)
from datacompass.core.repositories.scheduling import SchedulingRepository

logger = logging.getLogger(__name__)


def execute_job(schedule_id: int) -> None:
    """Execute a scheduled job.

    This is the main entry point called by APScheduler.
    It dispatches to the appropriate executor based on job type.

    Args:
        schedule_id: ID of the schedule to execute.
    """
    session = get_session()
    try:
        repo = SchedulingRepository(session)
        schedule = repo.get_by_id(schedule_id)

        if schedule is None:
            logger.error(f"Schedule not found: {schedule_id}")
            return

        if not schedule.is_enabled:
            logger.info(f"Schedule {schedule.name} is disabled, skipping")
            return

        logger.info(f"Executing scheduled job: {schedule.name} ({schedule.job_type})")

        # Create run record
        run = repo.create_run(schedule_id)
        session.commit()

        result_summary: dict[str, Any] = {}
        error_message: str | None = None
        status = "success"

        try:
            # Dispatch to appropriate executor
            if schedule.job_type == "scan":
                result_summary = _execute_scan(schedule.target_id)
            elif schedule.job_type == "dq_run":
                result_summary = _execute_dq_run(schedule.target_id)
            elif schedule.job_type == "deprecation_check":
                result_summary = _execute_deprecation_check(schedule.target_id)
            else:
                raise ValueError(f"Unknown job type: {schedule.job_type}")

        except Exception as e:
            logger.exception(f"Job execution failed: {schedule.name}")
            status = "failed"
            error_message = str(e)
            result_summary = {"error": str(e)}

        # Complete run record
        repo.complete_run(
            run_id=run.id,
            status=status,
            result_summary=result_summary,
            error_message=error_message,
        )

        # Update schedule last run info
        repo.update_schedule(
            schedule_id=schedule_id,
            last_run_at=datetime.utcnow(),
            last_run_status=status,
        )

        session.commit()

        # Emit event
        event = ScheduleRunCompletedEvent.create(
            schedule_id=schedule_id,
            schedule_name=schedule.name,
            job_type=schedule.job_type,
            run_id=run.id,
            status=status,
            result_summary=result_summary,
            error_message=error_message,
        )
        get_event_bus().emit(event)

        logger.info(f"Job completed: {schedule.name} ({status})")

    finally:
        session.close()


def _execute_scan(source_id: int | None) -> dict[str, Any]:
    """Execute a catalog scan job.

    Args:
        source_id: ID of the source to scan, or None for all sources.

    Returns:
        Result summary dict.
    """
    from datacompass.core.database import get_session
    from datacompass.core.services import CatalogService, SourceService

    session = get_session()
    try:
        if source_id is not None:
            # Scan specific source
            source_service = SourceService(session)
            source = source_service.get_source_by_id(source_id)

            catalog_service = CatalogService(session)
            result = catalog_service.scan_source(source.name)
            session.commit()

            return {
                "source": source.name,
                "status": result.status,
                "objects_discovered": result.stats.objects_discovered if result.stats else 0,
                "columns_discovered": result.stats.columns_discovered if result.stats else 0,
            }
        else:
            # Scan all sources
            source_service = SourceService(session)
            catalog_service = CatalogService(session)

            sources = source_service.list_sources()
            results = []

            for source in sources:
                if source.is_active:
                    try:
                        result = catalog_service.scan_source(source.name)
                        results.append({
                            "source": source.name,
                            "status": result.status,
                        })
                    except Exception as e:
                        results.append({
                            "source": source.name,
                            "status": "failed",
                            "error": str(e),
                        })

            session.commit()

            return {
                "sources_scanned": len(results),
                "results": results,
            }

    finally:
        session.close()


def _execute_dq_run(config_id: int | None) -> dict[str, Any]:
    """Execute a DQ run job.

    Args:
        config_id: ID of the DQ config to run, or None for all configs.

    Returns:
        Result summary dict.
    """
    from datacompass.core.database import get_session
    from datacompass.core.services.dq_service import DQService

    session = get_session()
    try:
        dq_service = DQService(session)

        if config_id is not None:
            # Run specific config
            result = dq_service.run_expectations(config_id)
            session.commit()

            return {
                "config_id": config_id,
                "object": f"{result.source_name}.{result.schema_name}.{result.object_name}",
                "total_checks": result.total_checks,
                "passed": result.passed,
                "breached": result.breached,
            }
        else:
            # Run all enabled configs
            configs = dq_service.list_configs(enabled_only=True)
            total_checks = 0
            total_passed = 0
            total_breached = 0

            for config in configs:
                try:
                    result = dq_service.run_expectations(config.id)
                    total_checks += result.total_checks
                    total_passed += result.passed
                    total_breached += result.breached
                except Exception as e:
                    logger.warning(f"DQ run failed for config {config.id}: {e}")

            session.commit()

            return {
                "configs_run": len(configs),
                "total_checks": total_checks,
                "total_passed": total_passed,
                "total_breached": total_breached,
            }

    finally:
        session.close()


def _execute_deprecation_check(campaign_id: int | None) -> dict[str, Any]:
    """Execute a deprecation deadline check job.

    Checks for campaigns with approaching deadlines and emits events.

    Args:
        campaign_id: ID of the campaign to check, or None for all campaigns.

    Returns:
        Result summary dict.
    """
    from datacompass.core.database import get_session
    from datacompass.core.services.deprecation_service import DeprecationService

    session = get_session()
    try:
        deprecation_service = DeprecationService(session)

        # Get campaigns to check
        if campaign_id is not None:
            campaigns = [deprecation_service.get_campaign(campaign_id)]
        else:
            campaigns = deprecation_service.list_campaigns(status="active")

        deadlines_approaching = 0
        events_emitted = 0

        for campaign in campaigns:
            # Check if deadline is within threshold (7 days or 14 days)
            days_remaining = campaign.days_remaining

            if days_remaining is not None and days_remaining <= 14:
                deadlines_approaching += 1

                # Emit event for notifications
                event = DeprecationDeadlineEvent.create(
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    source_name=campaign.source_name,
                    target_date=str(campaign.target_date),
                    days_remaining=days_remaining,
                    object_count=len(campaign.deprecations) if hasattr(campaign, 'deprecations') else 0,
                )
                get_event_bus().emit(event)
                events_emitted += 1

        return {
            "campaigns_checked": len(campaigns),
            "deadlines_approaching": deadlines_approaching,
            "events_emitted": events_emitted,
        }

    finally:
        session.close()
