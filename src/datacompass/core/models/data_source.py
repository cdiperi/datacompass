"""DataSource SQLAlchemy model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from datacompass.core.models.catalog_object import CatalogObject
    from datacompass.core.models.deprecation import DeprecationCampaign


class DataSource(Base, TimestampMixin):
    """Represents a configured data source (e.g., Databricks workspace, PostgreSQL database)."""

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    connection_info: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sync_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_scan_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_scan_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    objects: Mapped[list["CatalogObject"]] = relationship(
        "CatalogObject",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    deprecation_campaigns: Mapped[list["DeprecationCampaign"]] = relationship(
        "DeprecationCampaign",
        back_populates="source",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DataSource(name={self.name!r}, type={self.source_type!r})>"
