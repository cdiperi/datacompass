"""APScheduler wrapper for Data Compass scheduling.

Provides a high-level interface for managing scheduled jobs using APScheduler.
Supports cron expressions and persists jobs to the database.
"""

import logging
from datetime import datetime
from typing import Any, Callable

from datacompass.config import get_settings
from datacompass.core.database import get_session, init_database
from datacompass.core.models.scheduling import Schedule
from datacompass.core.repositories.scheduling import SchedulingRepository
from datacompass.core.scheduler.jobs import execute_job

logger = logging.getLogger(__name__)


class DataCompassScheduler:
    """Scheduler wrapper for managing automated jobs.

    Uses APScheduler for job execution with cron triggers.
    Jobs are persisted to the database and can survive restarts.

    Usage:
        scheduler = DataCompassScheduler()
        scheduler.start()
        # ... scheduler runs in background ...
        scheduler.shutdown()
    """

    def __init__(self) -> None:
        """Initialize the scheduler."""
        self._scheduler = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def start(self, blocking: bool = True) -> None:
        """Start the scheduler.

        Args:
            blocking: If True, block the calling thread until shutdown.
                      If False, return immediately (run in background).
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.schedulers.blocking import BlockingScheduler
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        except ImportError:
            logger.error(
                "APScheduler not installed. Install with: "
                "pip install 'datacompass[scheduler]'"
            )
            raise

        # Initialize database
        init_database()

        # Configure job store
        settings = get_settings()
        jobstores = {
            "default": SQLAlchemyJobStore(url=settings.database_url)
        }

        # Create scheduler
        if blocking:
            self._scheduler = BlockingScheduler(jobstores=jobstores)
        else:
            self._scheduler = BackgroundScheduler(jobstores=jobstores)

        # Load schedules from database and add jobs
        self._load_schedules()

        # Start
        logger.info("Starting Data Compass scheduler")
        self._running = True

        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped by user")
            self._running = False

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler.

        Args:
            wait: If True, wait for running jobs to complete.
        """
        if self._scheduler is not None:
            logger.info("Shutting down scheduler")
            self._scheduler.shutdown(wait=wait)
            self._running = False
            self._scheduler = None

    def reload_schedules(self) -> None:
        """Reload schedules from database.

        Useful when schedules are modified through CLI/API.
        """
        if self._scheduler is None:
            return

        # Remove all existing jobs
        self._scheduler.remove_all_jobs()

        # Reload from database
        self._load_schedules()

    def run_job_now(self, schedule_id: int) -> None:
        """Run a scheduled job immediately.

        Args:
            schedule_id: ID of the schedule to run.
        """
        session = get_session()
        try:
            repo = SchedulingRepository(session)
            schedule = repo.get_by_id(schedule_id)

            if schedule is None:
                logger.error(f"Schedule not found: {schedule_id}")
                return

            logger.info(f"Running job immediately: {schedule.name}")
            execute_job(schedule_id)

        finally:
            session.close()

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status.

        Returns:
            Dict with scheduler status information.
        """
        if self._scheduler is None:
            return {
                "running": False,
                "jobs": [],
            }

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            })

        return {
            "running": self._running,
            "jobs": jobs,
            "job_count": len(jobs),
        }

    def _load_schedules(self) -> None:
        """Load schedules from database and add to scheduler."""
        try:
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            return

        session = get_session()
        try:
            repo = SchedulingRepository(session)
            schedules = repo.list_enabled_schedules()

            for schedule in schedules:
                try:
                    trigger = self._create_trigger(schedule)
                    self._scheduler.add_job(
                        func=execute_job,
                        trigger=trigger,
                        args=[schedule.id],
                        id=f"schedule_{schedule.id}",
                        name=schedule.name,
                        replace_existing=True,
                    )

                    # Update next run time in database
                    job = self._scheduler.get_job(f"schedule_{schedule.id}")
                    if job and job.next_run_time:
                        repo.update_schedule(
                            schedule_id=schedule.id,
                            next_run_at=job.next_run_time.replace(tzinfo=None),
                        )

                    logger.info(f"Loaded schedule: {schedule.name}")

                except Exception as e:
                    logger.error(f"Failed to load schedule {schedule.name}: {e}")

            session.commit()

        finally:
            session.close()

    def _create_trigger(self, schedule: Schedule) -> Any:
        """Create APScheduler trigger from schedule.

        Args:
            schedule: Schedule model instance.

        Returns:
            APScheduler CronTrigger instance.
        """
        from apscheduler.triggers.cron import CronTrigger

        # Parse cron expression (5 fields: minute hour day month day_of_week)
        parts = schedule.cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {schedule.cron_expression}")

        minute, hour, day, month, day_of_week = parts

        return CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=schedule.timezone,
        )


# Global scheduler instance
_scheduler: DataCompassScheduler | None = None


def get_scheduler() -> DataCompassScheduler:
    """Get the global scheduler instance.

    Returns:
        DataCompassScheduler instance.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = DataCompassScheduler()
    return _scheduler


def reset_scheduler() -> None:
    """Reset the global scheduler (for testing)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
    _scheduler = None
