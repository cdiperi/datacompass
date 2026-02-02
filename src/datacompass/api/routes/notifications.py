"""API routes for notification management."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from datacompass.api.dependencies import DbSession
from datacompass.core.models.scheduling import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationLogResponse,
    NotificationRuleCreate,
    NotificationRuleDetailResponse,
    NotificationRuleResponse,
    NotificationRuleUpdate,
)
from datacompass.core.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(session: DbSession) -> NotificationService:
    """Get a NotificationService instance with the current session."""
    return NotificationService(session)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


# =============================================================================
# Channel Routes
# =============================================================================


@router.get("/channels", response_model=list[NotificationChannelResponse])
def list_channels(
    service: NotificationServiceDep,
    channel_type: str | None = Query(None, description="Filter by channel type"),
    enabled_only: bool = Query(False, description="Only return enabled channels"),
    limit: int | None = Query(None, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number to skip"),
) -> list[NotificationChannelResponse]:
    """List all notification channels."""
    return service.list_channels(
        channel_type=channel_type,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
def create_channel(
    service: NotificationServiceDep,
    data: NotificationChannelCreate,
) -> NotificationChannelResponse:
    """Create a notification channel."""
    return service.create_channel(
        name=data.name,
        channel_type=data.channel_type,
        config=data.config,
    )


@router.get("/channels/{channel_id}", response_model=NotificationChannelResponse)
def get_channel(
    service: NotificationServiceDep,
    channel_id: int,
) -> NotificationChannelResponse:
    """Get notification channel details."""
    return service.get_channel(channel_id)


@router.patch("/channels/{channel_id}", response_model=NotificationChannelResponse)
def update_channel(
    service: NotificationServiceDep,
    channel_id: int,
    data: NotificationChannelUpdate,
) -> NotificationChannelResponse:
    """Update a notification channel."""
    return service.update_channel(
        channel_id=channel_id,
        name=data.name,
        config=data.config,
        is_enabled=data.is_enabled,
    )


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(
    service: NotificationServiceDep,
    channel_id: int,
) -> None:
    """Delete a notification channel."""
    service.delete_channel(channel_id)


class ChannelTestResult(BaseModel):
    """Result of channel connection test."""

    success: bool
    error_message: str | None


@router.post("/channels/{channel_id}/test", response_model=ChannelTestResult)
def test_channel(
    service: NotificationServiceDep,
    channel_id: int,
) -> ChannelTestResult:
    """Test a notification channel connection."""
    result = service.test_channel(channel_id)
    return ChannelTestResult(
        success=result.success,
        error_message=result.error_message,
    )


# =============================================================================
# Rule Routes
# =============================================================================


@router.get("/rules", response_model=list[NotificationRuleDetailResponse])
def list_rules(
    service: NotificationServiceDep,
    event_type: str | None = Query(None, description="Filter by event type"),
    channel_id: int | None = Query(None, description="Filter by channel ID"),
    enabled_only: bool = Query(False, description="Only return enabled rules"),
    limit: int | None = Query(None, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number to skip"),
) -> list[NotificationRuleDetailResponse]:
    """List all notification rules."""
    return service.list_rules(
        event_type=event_type,
        channel_id=channel_id,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )


@router.post("/rules", response_model=NotificationRuleResponse, status_code=201)
def create_rule(
    service: NotificationServiceDep,
    data: NotificationRuleCreate,
) -> NotificationRuleResponse:
    """Create a notification rule."""
    return service.create_rule(
        name=data.name,
        event_type=data.event_type,
        channel_id=data.channel_id,
        conditions=data.conditions,
        template_override=data.template_override,
    )


@router.get("/rules/{rule_id}", response_model=NotificationRuleDetailResponse)
def get_rule(
    service: NotificationServiceDep,
    rule_id: int,
) -> NotificationRuleDetailResponse:
    """Get notification rule details."""
    return service.get_rule(rule_id)


@router.patch("/rules/{rule_id}", response_model=NotificationRuleResponse)
def update_rule(
    service: NotificationServiceDep,
    rule_id: int,
    data: NotificationRuleUpdate,
) -> NotificationRuleResponse:
    """Update a notification rule."""
    return service.update_rule(
        rule_id=rule_id,
        name=data.name,
        event_type=data.event_type,
        conditions=data.conditions,
        channel_id=data.channel_id,
        template_override=data.template_override,
        is_enabled=data.is_enabled,
    )


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(
    service: NotificationServiceDep,
    rule_id: int,
) -> None:
    """Delete a notification rule."""
    service.delete_rule(rule_id)


# =============================================================================
# Log Routes
# =============================================================================


@router.get("/log", response_model=list[NotificationLogResponse])
def get_notification_log(
    service: NotificationServiceDep,
    event_type: str | None = Query(None, description="Filter by event type"),
    status: str | None = Query(None, description="Filter by status"),
    channel_id: int | None = Query(None, description="Filter by channel ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number to skip"),
) -> list[NotificationLogResponse]:
    """Get notification log entries."""
    return service.get_notification_log(
        event_type=event_type,
        status=status,
        channel_id=channel_id,
        limit=limit,
        offset=offset,
    )
