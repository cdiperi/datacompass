"""Usage metrics models for tracking object-level usage statistics."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from datacompass.core.models.catalog_object import CatalogObject


# =============================================================================
# SQLAlchemy Models
# =============================================================================


class UsageMetric(Base, TimestampMixin):
    """Usage metrics snapshot for a catalog object.

    Stores point-in-time usage statistics. Each record represents a single
    collection event, enabling historical trend analysis.
    """

    __tablename__ = "usage_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Tier 1: Core metrics
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    write_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tier 2: Timestamp metrics
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_written_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Tier 3: Advanced metrics
    distinct_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    query_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Platform-specific metrics (JSON for flexibility)
    source_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    object: Mapped["CatalogObject"] = relationship("CatalogObject", back_populates="usage_metrics")

    __table_args__ = (
        Index("ix_usage_metrics_object_id", "object_id"),
        Index("ix_usage_metrics_collected_at", "collected_at"),
        Index("ix_usage_metrics_object_collected", "object_id", "collected_at"),
    )

    def __repr__(self) -> str:
        return f"<UsageMetric(id={self.id}, object_id={self.object_id}, collected_at={self.collected_at})>"


# =============================================================================
# Pydantic Schemas
# =============================================================================


class UsageMetricResponse(BaseModel):
    """Response schema for a single usage metric record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    collected_at: datetime
    row_count: int | None = None
    size_bytes: int | None = None
    read_count: int | None = None
    write_count: int | None = None
    last_read_at: datetime | None = None
    last_written_at: datetime | None = None
    distinct_users: int | None = None
    query_count: int | None = None
    source_metrics: dict[str, Any] | None = None


class UsageMetricDetailResponse(UsageMetricResponse):
    """Detailed usage metric response with object info."""

    object_name: str
    schema_name: str
    source_name: str


class UsageCollectResult(BaseModel):
    """Result of a usage metrics collection operation."""

    source_name: str
    collected_count: int = Field(..., description="Number of objects with metrics collected")
    skipped_count: int = Field(0, description="Number of objects skipped (no metrics available)")
    error_count: int = Field(0, description="Number of objects with collection errors")
    collected_at: datetime


class HotTableItem(BaseModel):
    """Item in the hot tables list."""

    object_id: int
    object_name: str
    schema_name: str
    source_name: str
    row_count: int | None = None
    size_bytes: int | None = None
    read_count: int | None = None
    write_count: int | None = None
    last_read_at: datetime | None = None
    last_written_at: datetime | None = None


class UsageHubSummary(BaseModel):
    """Summary statistics for usage metrics."""

    total_objects_with_metrics: int = Field(0, description="Objects with at least one metric")
    total_metrics_collected: int = Field(0, description="Total metric snapshots")
    avg_row_count: float | None = Field(None, description="Average row count across objects")
    total_size_bytes: int | None = Field(None, description="Total size of all objects")
    hot_tables: list[HotTableItem] = Field(
        default_factory=list, description="Most frequently accessed tables"
    )
