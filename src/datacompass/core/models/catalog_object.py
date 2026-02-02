"""CatalogObject SQLAlchemy model."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from datacompass.core.models.column import Column
    from datacompass.core.models.data_source import DataSource
    from datacompass.core.models.dependency import Dependency
    from datacompass.core.models.deprecation import Deprecation
    from datacompass.core.models.dq import DQConfig


class CatalogObject(Base, TimestampMixin, SoftDeleteMixin):
    """Represents a database object (table, view, etc.) in the catalog."""

    __tablename__ = "catalog_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Metadata from the source system (populated by adapters)
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # User-provided metadata (descriptions, tags, ownership, etc.)
    user_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    source: Mapped["DataSource"] = relationship("DataSource", back_populates="objects")
    columns: Mapped[list["Column"]] = relationship(
        "Column",
        back_populates="object",
        cascade="all, delete-orphan",
        order_by="Column.position",
    )
    dependencies: Mapped[list["Dependency"]] = relationship(
        "Dependency",
        foreign_keys="Dependency.object_id",
        back_populates="object",
        cascade="all, delete-orphan",
    )
    dq_config: Mapped["DQConfig | None"] = relationship(
        "DQConfig",
        back_populates="object",
        uselist=False,
        cascade="all, delete-orphan",
    )
    deprecations: Mapped[list["Deprecation"]] = relationship(
        "Deprecation",
        foreign_keys="Deprecation.object_id",
        back_populates="object",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "schema_name",
            "object_name",
            "object_type",
            name="uq_catalog_object_natural_key",
        ),
        Index("ix_catalog_objects_source_schema", "source_id", "schema_name"),
        Index("ix_catalog_objects_object_type", "object_type"),
    )

    @property
    def full_name(self) -> str:
        """Return the fully-qualified object name."""
        return f"{self.schema_name}.{self.object_name}"

    def __repr__(self) -> str:
        return f"<CatalogObject({self.schema_name}.{self.object_name}, type={self.object_type!r})>"
