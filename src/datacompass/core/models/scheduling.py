"""Scheduling and notification models for automated jobs and alerts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, TimestampMixin


# =============================================================================
# Type Aliases
# =============================================================================

JobType = Literal["scan", "dq_run", "deprecation_check"]
RunStatus = Literal["running", "success", "failed"]
ChannelType = Literal["email", "slack", "webhook"]
EventType = Literal["dq_breach", "scan_failed", "scan_completed", "deprecation_deadline"]
NotificationStatus = Literal["sent", "failed", "rate_limited"]


# =============================================================================
# SQLAlchemy Models
# =============================================================================


class Schedule(Base, TimestampMixin):
    """Scheduled job configuration.

    Defines when and what job to run (scan, dq_run, deprecation_check).
    Uses cron expressions for flexible scheduling.
    """

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    runs: Mapped[list["ScheduleRun"]] = relationship(
        "ScheduleRun",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Schedule(id={self.id}, name={self.name!r}, job_type={self.job_type!r})>"


class ScheduleRun(Base):
    """Execution history for a scheduled job.

    Records the start time, end time, status, and results of each run.
    """

    __tablename__ = "schedule_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    schedule: Mapped["Schedule"] = relationship("Schedule", back_populates="runs")

    def __repr__(self) -> str:
        return f"<ScheduleRun(id={self.id}, status={self.status!r})>"


class NotificationChannel(Base, TimestampMixin):
    """Notification delivery channel configuration.

    Stores connection details for email, Slack, or webhook channels.
    """

    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    rules: Mapped[list["NotificationRule"]] = relationship(
        "NotificationRule",
        back_populates="channel",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<NotificationChannel(id={self.id}, name={self.name!r}, type={self.channel_type!r})>"


class NotificationRule(Base, TimestampMixin):
    """Rule mapping events to notification channels.

    Defines which events trigger notifications on which channels,
    with optional filtering conditions.
    """

    __tablename__ = "notification_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    channel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    channel: Mapped["NotificationChannel"] = relationship(
        "NotificationChannel", back_populates="rules"
    )

    def __repr__(self) -> str:
        return f"<NotificationRule(id={self.id}, name={self.name!r}, event={self.event_type!r})>"


class NotificationLog(Base):
    """Log of sent notifications.

    Records all notification attempts with status and any errors.
    """

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("notification_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("notification_channels.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<NotificationLog(id={self.id}, event={self.event_type!r}, status={self.status!r})>"


# =============================================================================
# Pydantic Schemas - Schedule
# =============================================================================


class ScheduleCreate(BaseModel):
    """Request to create a schedule."""

    name: str = Field(..., max_length=100, description="Unique schedule name")
    description: str | None = Field(None, description="Schedule description")
    job_type: JobType = Field(..., description="Type of job to run")
    target_id: int | None = Field(None, description="Target ID (source, config, or campaign)")
    cron_expression: str = Field(..., description="Cron expression (e.g., '0 6 * * *')")
    timezone: str = Field("UTC", description="Timezone for cron expression")


class ScheduleUpdate(BaseModel):
    """Request to update a schedule."""

    name: str | None = Field(None, max_length=100)
    description: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    is_enabled: bool | None = None


class ScheduleResponse(BaseModel):
    """Response for a schedule."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    job_type: str
    target_id: int | None
    cron_expression: str
    timezone: str
    is_enabled: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    created_at: datetime
    updated_at: datetime


class ScheduleRunResponse(BaseModel):
    """Response for a schedule run."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    result_summary: dict[str, Any] | None
    error_message: str | None
    created_at: datetime


class ScheduleDetailResponse(ScheduleResponse):
    """Detailed schedule response with recent runs."""

    recent_runs: list[ScheduleRunResponse] = Field(default_factory=list)


# =============================================================================
# Pydantic Schemas - Notification Channel
# =============================================================================


class ChannelConfigEmail(BaseModel):
    """Email channel configuration."""

    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(587, description="SMTP server port")
    smtp_user: str | None = Field(None, description="SMTP username")
    smtp_password: str | None = Field(None, description="SMTP password")
    from_address: str = Field(..., description="From email address")
    to_addresses: list[str] = Field(..., description="Recipient email addresses")
    use_tls: bool = Field(True, description="Use TLS encryption")


class ChannelConfigSlack(BaseModel):
    """Slack channel configuration."""

    webhook_url: str = Field(..., description="Slack webhook URL")
    channel: str | None = Field(None, description="Override channel name")
    username: str | None = Field(None, description="Override bot username")
    icon_emoji: str | None = Field(None, description="Override bot icon emoji")


class ChannelConfigWebhook(BaseModel):
    """Generic webhook channel configuration."""

    url: str = Field(..., description="Webhook URL")
    method: str = Field("POST", description="HTTP method")
    headers: dict[str, str] = Field(default_factory=dict, description="Custom headers")
    timeout_seconds: int = Field(30, description="Request timeout")


class NotificationChannelCreate(BaseModel):
    """Request to create a notification channel."""

    name: str = Field(..., max_length=100, description="Unique channel name")
    channel_type: ChannelType = Field(..., description="Channel type")
    config: dict[str, Any] = Field(..., description="Channel-specific configuration")


class NotificationChannelUpdate(BaseModel):
    """Request to update a notification channel."""

    name: str | None = Field(None, max_length=100)
    config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class NotificationChannelResponse(BaseModel):
    """Response for a notification channel."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel_type: str
    config: dict[str, Any]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Pydantic Schemas - Notification Rule
# =============================================================================


class NotificationRuleCreate(BaseModel):
    """Request to create a notification rule."""

    name: str = Field(..., max_length=100, description="Rule name")
    event_type: EventType = Field(..., description="Event type to match")
    conditions: dict[str, Any] | None = Field(None, description="Filtering conditions")
    channel_id: int = Field(..., description="Channel to send notifications to")
    template_override: str | None = Field(None, description="Custom message template")


class NotificationRuleUpdate(BaseModel):
    """Request to update a notification rule."""

    name: str | None = Field(None, max_length=100)
    event_type: EventType | None = None
    conditions: dict[str, Any] | None = None
    channel_id: int | None = None
    template_override: str | None = None
    is_enabled: bool | None = None


class NotificationRuleResponse(BaseModel):
    """Response for a notification rule."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    event_type: str
    conditions: dict[str, Any] | None
    channel_id: int
    template_override: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class NotificationRuleDetailResponse(NotificationRuleResponse):
    """Detailed rule response with channel info."""

    channel_name: str
    channel_type: str


# =============================================================================
# Pydantic Schemas - Notification Log
# =============================================================================


class NotificationLogResponse(BaseModel):
    """Response for a notification log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int | None
    channel_id: int | None
    event_type: str
    event_payload: dict[str, Any]
    status: str
    error_message: str | None
    sent_at: datetime


# =============================================================================
# Pydantic Schemas - Hub Summary
# =============================================================================


class SchedulerHubSummary(BaseModel):
    """Summary data for scheduler hub dashboard."""

    total_schedules: int = Field(0, description="Total schedules")
    enabled_schedules: int = Field(0, description="Enabled schedules")
    total_channels: int = Field(0, description="Total notification channels")
    enabled_channels: int = Field(0, description="Enabled channels")
    total_rules: int = Field(0, description="Total notification rules")
    enabled_rules: int = Field(0, description="Enabled rules")
    recent_runs: list[ScheduleRunResponse] = Field(
        default_factory=list, description="Recent schedule runs"
    )
    recent_notifications: list[NotificationLogResponse] = Field(
        default_factory=list, description="Recent notifications"
    )
    schedules_by_type: dict[str, int] = Field(
        default_factory=dict, description="Schedules grouped by job type"
    )
    notifications_by_status: dict[str, int] = Field(
        default_factory=dict, description="Recent notifications by status"
    )


# =============================================================================
# YAML Config Schemas
# =============================================================================


class YAMLSchedule(BaseModel):
    """Schedule as defined in YAML config file."""

    name: str = Field(..., description="Unique schedule name")
    description: str | None = Field(None, description="Schedule description")
    job_type: JobType = Field(..., description="Type of job to run")
    target: str | None = Field(None, description="Target name (source, object, or campaign)")
    cron: str = Field(..., description="Cron expression")
    timezone: str = Field("UTC", description="Timezone")
    enabled: bool = Field(True, description="Whether schedule is enabled")


class YAMLChannel(BaseModel):
    """Notification channel as defined in YAML config file."""

    name: str = Field(..., description="Unique channel name")
    type: ChannelType = Field(..., description="Channel type")
    config: dict[str, Any] = Field(..., description="Channel configuration")
    enabled: bool = Field(True, description="Whether channel is enabled")


class YAMLRule(BaseModel):
    """Notification rule as defined in YAML config file."""

    name: str = Field(..., description="Rule name")
    event: EventType = Field(..., description="Event type")
    channel: str = Field(..., description="Channel name")
    conditions: dict[str, Any] | None = Field(None, description="Filtering conditions")
    template: str | None = Field(None, description="Custom message template")
    enabled: bool = Field(True, description="Whether rule is enabled")


class YAMLSchedulingConfig(BaseModel):
    """Full scheduling configuration from YAML file."""

    schedules: list[YAMLSchedule] = Field(default_factory=list)
    channels: list[YAMLChannel] = Field(default_factory=list)
    rules: list[YAMLRule] = Field(default_factory=list)
