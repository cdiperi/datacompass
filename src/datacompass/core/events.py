"""Event system for cross-service communication.

Simple in-process pub/sub for emitting events when significant things happen
(DQ breaches, scan completions, etc.) that can trigger notifications.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Event Types
# =============================================================================


@dataclass
class Event:
    """Base event class.

    All events have a type, timestamp, and payload.
    """

    event_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }


@dataclass
class DQBreachEvent(Event):
    """Event emitted when a DQ threshold is breached."""

    event_type: str = "dq_breach"

    @classmethod
    def create(
        cls,
        breach_id: int,
        expectation_id: int,
        object_name: str,
        schema_name: str,
        source_name: str,
        expectation_type: str,
        column_name: str | None,
        metric_value: float,
        threshold_value: float,
        breach_direction: str,
        deviation_percent: float,
        priority: str,
        snapshot_date: str,
    ) -> "DQBreachEvent":
        """Create a DQ breach event.

        Args:
            breach_id: ID of the breach record.
            expectation_id: ID of the expectation.
            object_name: Name of the object.
            schema_name: Schema name.
            source_name: Source name.
            expectation_type: Type of expectation (row_count, etc.).
            column_name: Column name for column-level metrics.
            metric_value: Actual metric value.
            threshold_value: Threshold that was breached.
            breach_direction: 'high' or 'low'.
            deviation_percent: Percentage deviation from threshold.
            priority: Priority level.
            snapshot_date: Date of the snapshot.

        Returns:
            DQBreachEvent instance.
        """
        return cls(
            payload={
                "breach_id": breach_id,
                "expectation_id": expectation_id,
                "object_name": object_name,
                "schema_name": schema_name,
                "source_name": source_name,
                "full_name": f"{source_name}.{schema_name}.{object_name}",
                "expectation_type": expectation_type,
                "column_name": column_name,
                "metric_value": metric_value,
                "threshold_value": threshold_value,
                "breach_direction": breach_direction,
                "deviation_percent": deviation_percent,
                "priority": priority,
                "snapshot_date": snapshot_date,
            }
        )


@dataclass
class ScanCompletedEvent(Event):
    """Event emitted when a source scan completes successfully."""

    event_type: str = "scan_completed"

    @classmethod
    def create(
        cls,
        source_name: str,
        source_id: int,
        objects_discovered: int,
        objects_updated: int,
        objects_deleted: int,
        columns_discovered: int,
        duration_seconds: float,
    ) -> "ScanCompletedEvent":
        """Create a scan completed event.

        Args:
            source_name: Name of the source.
            source_id: ID of the source.
            objects_discovered: Number of objects found.
            objects_updated: Number of objects updated.
            objects_deleted: Number of objects soft-deleted.
            columns_discovered: Number of columns found.
            duration_seconds: Scan duration in seconds.

        Returns:
            ScanCompletedEvent instance.
        """
        return cls(
            payload={
                "source_name": source_name,
                "source_id": source_id,
                "objects_discovered": objects_discovered,
                "objects_updated": objects_updated,
                "objects_deleted": objects_deleted,
                "columns_discovered": columns_discovered,
                "duration_seconds": duration_seconds,
            }
        )


@dataclass
class ScanFailedEvent(Event):
    """Event emitted when a source scan fails."""

    event_type: str = "scan_failed"

    @classmethod
    def create(
        cls,
        source_name: str,
        source_id: int,
        error_message: str,
        error_type: str | None = None,
    ) -> "ScanFailedEvent":
        """Create a scan failed event.

        Args:
            source_name: Name of the source.
            source_id: ID of the source.
            error_message: Error message.
            error_type: Type of error (optional).

        Returns:
            ScanFailedEvent instance.
        """
        return cls(
            payload={
                "source_name": source_name,
                "source_id": source_id,
                "error_message": error_message,
                "error_type": error_type,
            }
        )


@dataclass
class DeprecationDeadlineEvent(Event):
    """Event emitted when a deprecation deadline is approaching."""

    event_type: str = "deprecation_deadline"

    @classmethod
    def create(
        cls,
        campaign_id: int,
        campaign_name: str,
        source_name: str,
        target_date: str,
        days_remaining: int,
        object_count: int,
    ) -> "DeprecationDeadlineEvent":
        """Create a deprecation deadline event.

        Args:
            campaign_id: ID of the campaign.
            campaign_name: Name of the campaign.
            source_name: Source name.
            target_date: Target deprecation date.
            days_remaining: Days until deadline.
            object_count: Number of objects in campaign.

        Returns:
            DeprecationDeadlineEvent instance.
        """
        return cls(
            payload={
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "source_name": source_name,
                "target_date": target_date,
                "days_remaining": days_remaining,
                "object_count": object_count,
            }
        )


@dataclass
class ScheduleRunCompletedEvent(Event):
    """Event emitted when a scheduled job completes."""

    event_type: str = "schedule_run_completed"

    @classmethod
    def create(
        cls,
        schedule_id: int,
        schedule_name: str,
        job_type: str,
        run_id: int,
        status: str,
        result_summary: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> "ScheduleRunCompletedEvent":
        """Create a schedule run completed event.

        Args:
            schedule_id: ID of the schedule.
            schedule_name: Name of the schedule.
            job_type: Type of job.
            run_id: ID of the run.
            status: Run status (success, failed).
            result_summary: Optional result summary.
            error_message: Optional error message.

        Returns:
            ScheduleRunCompletedEvent instance.
        """
        return cls(
            payload={
                "schedule_id": schedule_id,
                "schedule_name": schedule_name,
                "job_type": job_type,
                "run_id": run_id,
                "status": status,
                "result_summary": result_summary,
                "error_message": error_message,
            }
        )


# =============================================================================
# Event Bus
# =============================================================================

# Type alias for event handlers
EventHandler = Callable[[Event], None]


class EventBus:
    """Simple in-process event bus for pub/sub.

    Supports subscribing handlers to event types and emitting events.
    Handlers are called synchronously in the order they were registered.

    Usage:
        bus = EventBus()
        bus.subscribe("dq_breach", my_handler)
        bus.emit(DQBreachEvent.create(...))
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: Event type to subscribe to.
            handler: Callable that takes an Event.
        """
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to event type: {event_type}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to all events.

        Args:
            handler: Callable that takes an Event.
        """
        self._global_handlers.append(handler)
        logger.debug("Handler subscribed to all events")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: Event type to unsubscribe from.
            handler: Handler to remove.

        Returns:
            True if handler was found and removed.
        """
        handlers = self._handlers[event_type]
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    def unsubscribe_all(self, handler: EventHandler) -> bool:
        """Unsubscribe a handler from all events.

        Args:
            handler: Handler to remove.

        Returns:
            True if handler was found and removed.
        """
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)
            return True
        return False

    def emit(self, event: Event) -> None:
        """Emit an event to all subscribed handlers.

        Handlers are called synchronously. Exceptions in handlers are
        logged but do not prevent other handlers from being called.

        Args:
            event: Event to emit.
        """
        logger.debug(f"Emitting event: {event.event_type}")

        # Call type-specific handlers
        for handler in self._handlers[event.event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.exception(f"Error in event handler for {event.event_type}: {e}")

        # Call global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.exception(f"Error in global event handler: {e}")

    def clear(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()
        self._global_handlers.clear()


# =============================================================================
# Global Event Bus Instance
# =============================================================================

# Singleton event bus instance for application-wide use
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Returns:
        The global EventBus instance.
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _event_bus
    if _event_bus is not None:
        _event_bus.clear()
    _event_bus = None
