"""Deprecation campaign models for managing object retirement."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from datacompass.core.models.catalog_object import CatalogObject
    from datacompass.core.models.data_source import DataSource


# =============================================================================
# Type Aliases
# =============================================================================

CampaignStatus = Literal["draft", "active", "completed"]


# =============================================================================
# SQLAlchemy Models
# =============================================================================


class DeprecationCampaign(Base, TimestampMixin):
    """Deprecation campaign scoped to a data source.

    A campaign groups multiple deprecated objects together with a shared
    target retirement date.
    """

    __tablename__ = "deprecation_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    target_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    source: Mapped["DataSource"] = relationship("DataSource", back_populates="deprecation_campaigns")
    deprecations: Mapped[list["Deprecation"]] = relationship(
        "Deprecation",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("source_id", "name", name="uq_deprecation_campaigns_source_name"),
        Index("ix_deprecation_campaigns_source_id", "source_id"),
        Index("ix_deprecation_campaigns_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<DeprecationCampaign(id={self.id}, name={self.name!r}, status={self.status!r})>"


class Deprecation(Base, TimestampMixin):
    """An object being deprecated within a campaign.

    Links a catalog object to a campaign, optionally specifying
    a replacement object and migration notes.
    """

    __tablename__ = "deprecations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deprecation_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    replacement_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("catalog_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    migration_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    campaign: Mapped["DeprecationCampaign"] = relationship(
        "DeprecationCampaign",
        back_populates="deprecations",
    )
    object: Mapped["CatalogObject"] = relationship(
        "CatalogObject",
        foreign_keys=[object_id],
        back_populates="deprecations",
    )
    replacement: Mapped["CatalogObject | None"] = relationship(
        "CatalogObject",
        foreign_keys=[replacement_id],
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "object_id", name="uq_deprecations_campaign_object"),
        Index("ix_deprecations_campaign_id", "campaign_id"),
        Index("ix_deprecations_object_id", "object_id"),
    )

    def __repr__(self) -> str:
        return f"<Deprecation(id={self.id}, object_id={self.object_id}, campaign_id={self.campaign_id})>"


# =============================================================================
# Pydantic Schemas - Input
# =============================================================================


class CampaignCreate(BaseModel):
    """Request to create a deprecation campaign."""

    source_id: int = Field(..., description="ID of the data source")
    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    description: str | None = Field(None, description="Campaign description")
    target_date: date = Field(..., description="Target retirement date")


class CampaignUpdate(BaseModel):
    """Request to update a deprecation campaign."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: CampaignStatus | None = None
    target_date: date | None = None


class DeprecationCreate(BaseModel):
    """Request to add an object to a campaign."""

    object_id: int = Field(..., description="ID of the object to deprecate")
    replacement_id: int | None = Field(None, description="ID of the replacement object")
    migration_notes: str | None = Field(None, description="Migration instructions")


class DeprecationUpdate(BaseModel):
    """Request to update a deprecation."""

    replacement_id: int | None = None
    migration_notes: str | None = None


# =============================================================================
# Pydantic Schemas - Response
# =============================================================================


class DeprecationResponse(BaseModel):
    """Response for a deprecation entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    object_id: int
    object_name: str
    schema_name: str
    object_type: str
    replacement_id: int | None
    replacement_name: str | None = None
    migration_notes: str | None
    created_at: datetime
    updated_at: datetime


class CampaignListItem(BaseModel):
    """Campaign summary for list views."""

    id: int
    source_id: int
    source_name: str
    name: str
    status: str
    target_date: date
    object_count: int

    @computed_field
    @property
    def days_remaining(self) -> int | None:
        """Days until target date (None if completed)."""
        if self.status == "completed":
            return None
        delta = self.target_date - date.today()
        return delta.days


class CampaignDetailResponse(BaseModel):
    """Detailed campaign response with deprecations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_name: str
    name: str
    description: str | None
    status: str
    target_date: date
    deprecations: list[DeprecationResponse]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def days_remaining(self) -> int | None:
        """Days until target date (None if completed)."""
        if self.status == "completed":
            return None
        delta = self.target_date - date.today()
        return delta.days


# =============================================================================
# Impact Analysis Schemas
# =============================================================================


class ImpactedObject(BaseModel):
    """Object impacted by a deprecation."""

    id: int
    source_name: str
    schema_name: str
    object_name: str
    object_type: str
    distance: int = Field(..., description="Hops from deprecated object")

    @computed_field
    @property
    def full_name(self) -> str:
        """Full qualified name."""
        return f"{self.source_name}.{self.schema_name}.{self.object_name}"


class DeprecationImpact(BaseModel):
    """Impact analysis for a single deprecated object."""

    deprecated_object_id: int
    deprecated_object_name: str
    downstream_count: int
    impacted_objects: list[ImpactedObject]


class CampaignImpactSummary(BaseModel):
    """Impact summary for an entire campaign."""

    campaign_id: int
    campaign_name: str
    total_deprecated: int
    total_impacted: int
    impacts: list[DeprecationImpact]


# =============================================================================
# Hub Summary Schema
# =============================================================================


class DeprecationHubSummary(BaseModel):
    """Summary data for deprecation hub dashboard."""

    total_campaigns: int = Field(0, description="Total campaigns")
    active_campaigns: int = Field(0, description="Active campaigns")
    draft_campaigns: int = Field(0, description="Draft campaigns")
    completed_campaigns: int = Field(0, description="Completed campaigns")
    total_deprecated_objects: int = Field(0, description="Total deprecated objects")
    upcoming_deadlines: list[CampaignListItem] = Field(
        default_factory=list,
        description="Campaigns with upcoming target dates",
    )
