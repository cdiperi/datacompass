"""Data quality models for DQ configs, expectations, results, and breaches."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from datacompass.core.models.catalog_object import CatalogObject


# =============================================================================
# Type Aliases
# =============================================================================

ExpectationType = Literal["row_count", "null_count", "distinct_count", "min", "max", "mean", "sum"]
ThresholdType = Literal["absolute", "simple_average", "dow_adjusted"]
BreachDirection = Literal["high", "low"]
BreachStatus = Literal["open", "acknowledged", "dismissed", "resolved"]
Priority = Literal["critical", "high", "medium", "low"]
Grain = Literal["daily", "hourly"]


# =============================================================================
# SQLAlchemy Models
# =============================================================================


class DQConfig(Base, TimestampMixin):
    """Data quality configuration for a catalog object.

    Each catalog object can have at most one DQ config, which defines
    how DQ checks should be run (date column, grain) and contains
    multiple expectations.
    """

    __tablename__ = "dq_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_objects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    date_column: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grain: Mapped[str] = mapped_column(String(50), nullable=False, default="daily")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    object: Mapped["CatalogObject"] = relationship("CatalogObject", back_populates="dq_config")
    expectations: Mapped[list["DQExpectation"]] = relationship(
        "DQExpectation",
        back_populates="config",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_dq_configs_object_id", "object_id"),
    )

    def __repr__(self) -> str:
        return f"<DQConfig(id={self.id}, object_id={self.object_id}, grain={self.grain!r})>"


class DQExpectation(Base, TimestampMixin):
    """Individual DQ expectation (metric + threshold) within a config.

    Defines what to check (metric type, column) and the threshold
    strategy for determining breaches.
    """

    __tablename__ = "dq_expectations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dq_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    expectation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    threshold_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    config: Mapped["DQConfig"] = relationship("DQConfig", back_populates="expectations")
    results: Mapped[list["DQResult"]] = relationship(
        "DQResult",
        back_populates="expectation",
        cascade="all, delete-orphan",
    )
    breaches: Mapped[list["DQBreach"]] = relationship(
        "DQBreach",
        back_populates="expectation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_dq_expectations_config_id", "config_id"),
    )

    def __repr__(self) -> str:
        col = f", column={self.column_name!r}" if self.column_name else ""
        return f"<DQExpectation(id={self.id}, type={self.expectation_type!r}{col})>"


class DQResult(Base):
    """Result of a DQ check execution for a specific date.

    Stores the actual metric value and computed thresholds for
    a single expectation on a specific snapshot date.
    """

    __tablename__ = "dq_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expectation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dq_expectations.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    computed_threshold_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_threshold_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    expectation: Mapped["DQExpectation"] = relationship("DQExpectation", back_populates="results")
    breach: Mapped["DQBreach | None"] = relationship(
        "DQBreach",
        back_populates="result",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("expectation_id", "snapshot_date", name="uq_dq_results_expectation_date"),
        Index("ix_dq_results_expectation_id", "expectation_id"),
        Index("ix_dq_results_snapshot_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<DQResult(id={self.id}, date={self.snapshot_date}, value={self.metric_value})>"


class DQBreach(Base, TimestampMixin):
    """Threshold violation detected during DQ check execution.

    Records when a metric value breaches the computed thresholds,
    with lifecycle management for tracking breach resolution.
    """

    __tablename__ = "dq_breaches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expectation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dq_expectations.id", ondelete="CASCADE"),
        nullable=False,
    )
    result_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dq_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    breach_direction: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_value: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_percent: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    lifecycle_events: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    expectation: Mapped["DQExpectation"] = relationship("DQExpectation", back_populates="breaches")
    result: Mapped["DQResult"] = relationship("DQResult", back_populates="breach")

    __table_args__ = (
        UniqueConstraint("expectation_id", "snapshot_date", name="uq_dq_breaches_expectation_date"),
        Index("ix_dq_breaches_expectation_id", "expectation_id"),
        Index("ix_dq_breaches_status", "status"),
        Index("ix_dq_breaches_snapshot_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<DQBreach(id={self.id}, status={self.status!r}, direction={self.breach_direction!r})>"


# =============================================================================
# Pydantic Schemas
# =============================================================================


class ThresholdConfig(BaseModel):
    """Configuration for how thresholds are computed."""

    type: ThresholdType = Field(..., description="Threshold strategy type")
    min: float | None = Field(None, description="Absolute minimum threshold")
    max: float | None = Field(None, description="Absolute maximum threshold")
    multiplier: float | None = Field(None, description="Multiplier for dynamic thresholds")
    lookback_days: int | None = Field(None, description="Days to look back for historical data")


class DQConfigCreate(BaseModel):
    """Request to create a DQ config."""

    object_id: int = Field(..., description="ID of the catalog object")
    date_column: str | None = Field(None, description="Column for date partitioning")
    grain: Grain = Field("daily", description="Check granularity")


class DQConfigUpdate(BaseModel):
    """Request to update a DQ config."""

    date_column: str | None = None
    grain: Grain | None = None
    is_enabled: bool | None = None


class DQExpectationCreate(BaseModel):
    """Request to create a DQ expectation."""

    config_id: int = Field(..., description="ID of the DQ config")
    expectation_type: str = Field(..., description="Type of metric to check")
    column_name: str | None = Field(None, description="Column for column-level metrics")
    threshold_config: ThresholdConfig = Field(..., description="Threshold configuration")
    priority: Priority = Field("medium", description="Expectation priority")


class DQExpectationUpdate(BaseModel):
    """Request to update a DQ expectation."""

    expectation_type: str | None = None
    column_name: str | None = None
    threshold_config: ThresholdConfig | None = None
    priority: Priority | None = None
    is_enabled: bool | None = None


class BreachStatusUpdate(BaseModel):
    """Request to update breach status."""

    status: Literal["acknowledged", "dismissed", "resolved"] = Field(
        ..., description="New status"
    )
    notes: str | None = Field(None, description="Optional notes for lifecycle event")


class LifecycleEvent(BaseModel):
    """A single lifecycle event in breach history."""

    status: str = Field(..., description="Status change")
    by: str = Field(..., description="Who made the change")
    at: datetime = Field(..., description="When the change was made")
    notes: str | None = Field(None, description="Optional notes")


# =============================================================================
# Response Schemas
# =============================================================================


class DQConfigResponse(BaseModel):
    """Response for a DQ config."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    date_column: str | None
    grain: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class DQConfigListItem(BaseModel):
    """DQ config with object details for list views."""

    id: int
    object_id: int
    object_name: str
    schema_name: str
    source_name: str
    date_column: str | None
    grain: str
    is_enabled: bool
    expectation_count: int
    open_breach_count: int


class DQExpectationResponse(BaseModel):
    """Response for a DQ expectation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    config_id: int
    expectation_type: str
    column_name: str | None
    threshold_config: dict[str, Any]
    priority: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class DQConfigDetailResponse(BaseModel):
    """Detailed DQ config response with expectations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    object_name: str
    schema_name: str
    source_name: str
    date_column: str | None
    grain: str
    is_enabled: bool
    expectations: list[DQExpectationResponse]
    created_at: datetime
    updated_at: datetime


class DQResultResponse(BaseModel):
    """Response for a DQ result."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    expectation_id: int
    snapshot_date: date
    metric_value: float
    computed_threshold_low: float | None
    computed_threshold_high: float | None
    execution_time_ms: int | None
    status: str  # "pass" or "breach"
    created_at: datetime


class BreachResponse(BaseModel):
    """Response for a DQ breach."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    expectation_id: int
    result_id: int
    snapshot_date: date
    metric_value: float
    breach_direction: str
    threshold_value: float
    deviation_value: float
    deviation_percent: float
    status: str
    detected_at: datetime
    created_at: datetime
    updated_at: datetime


class BreachDetailResponse(BreachResponse):
    """Detailed breach response with object info."""

    object_id: int
    object_name: str
    schema_name: str
    source_name: str
    expectation_type: str
    column_name: str | None
    priority: str
    threshold_snapshot: dict[str, Any]
    lifecycle_events: list[dict[str, Any]]


class DQRunResultItem(BaseModel):
    """Single expectation result from a DQ run."""

    expectation_id: int
    expectation_type: str
    column_name: str | None
    metric_value: float
    computed_threshold_low: float | None
    computed_threshold_high: float | None
    status: str  # "pass" or "breach"
    breach_id: int | None = None


class DQRunResult(BaseModel):
    """Results from running DQ checks on a config."""

    config_id: int
    object_name: str
    schema_name: str
    source_name: str
    snapshot_date: date
    total_checks: int
    passed: int
    breached: int
    results: list[DQRunResultItem]


class DQHubSummary(BaseModel):
    """Summary data for DQ hub dashboard."""

    total_configs: int = Field(0, description="Total DQ configs")
    enabled_configs: int = Field(0, description="Enabled DQ configs")
    total_expectations: int = Field(0, description="Total expectations")
    enabled_expectations: int = Field(0, description="Enabled expectations")
    open_breaches: int = Field(0, description="Open breaches")
    breaches_by_priority: dict[str, int] = Field(
        default_factory=dict, description="Open breaches by priority"
    )
    breaches_by_status: dict[str, int] = Field(
        default_factory=dict, description="Breaches by status"
    )
    recent_breaches: list[BreachDetailResponse] = Field(
        default_factory=list, description="Recent breaches"
    )


# =============================================================================
# YAML Config Schema
# =============================================================================


class YAMLExpectation(BaseModel):
    """Expectation as defined in YAML config file."""

    type: str = Field(..., alias="type")
    column: str | None = Field(None, description="Column for column-level metrics")
    threshold: ThresholdConfig = Field(..., description="Threshold configuration")
    priority: Priority = Field("medium", description="Expectation priority")


class YAMLDQConfig(BaseModel):
    """DQ config as defined in YAML file."""

    object: str = Field(..., description="Object identifier (source.schema.name)")
    date_column: str | None = Field(None, description="Date column for partitioning")
    grain: Grain = Field("daily", description="Check granularity")
    expectations: list[YAMLExpectation] = Field(
        default_factory=list, description="List of expectations"
    )
