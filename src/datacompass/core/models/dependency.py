"""Dependency model for lineage tracking."""

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from datacompass.core.models.catalog_object import CatalogObject
    from datacompass.core.models.data_source import DataSource


# =============================================================================
# Enums / Constants
# =============================================================================

DependencyType = Literal["DIRECT", "INDIRECT"]
ParsingSource = Literal["source_metadata", "sql_parsing", "manual"]
ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW"]


# =============================================================================
# SQLAlchemy Model
# =============================================================================


class Dependency(Base, TimestampMixin):
    """Represents a dependency relationship between catalog objects.

    The dependent object (object_id) depends on the target (target_id).
    For example, if view V reads from table T, then:
    - object_id = V's id (the dependent)
    - target_id = T's id (what it depends on)

    For external references (objects not in the catalog), target_id is None
    and target_external contains the reference details.
    """

    __tablename__ = "dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("catalog_objects.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_external: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    dependency_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parsing_source: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[str] = mapped_column(String(50), nullable=False, default="HIGH")

    # Relationships
    source: Mapped["DataSource"] = relationship("DataSource")
    object: Mapped["CatalogObject"] = relationship(
        "CatalogObject",
        foreign_keys=[object_id],
        back_populates="dependencies",
    )
    target: Mapped["CatalogObject | None"] = relationship(
        "CatalogObject",
        foreign_keys=[target_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "object_id",
            "target_id",
            "parsing_source",
            name="uq_dependency_natural_key",
        ),
        Index("ix_dependencies_object_id", "object_id"),
        Index("ix_dependencies_target_id", "target_id"),
        Index("ix_dependencies_source_id", "source_id"),
    )

    def __repr__(self) -> str:
        target = f"obj#{self.target_id}" if self.target_id else str(self.target_external)
        return f"<Dependency(obj#{self.object_id} -> {target}, type={self.dependency_type!r})>"


# =============================================================================
# Pydantic Schemas
# =============================================================================


class DependencyResponse(BaseModel):
    """Schema for dependency responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    object_id: int
    target_id: int | None
    target_external: dict[str, Any] | None = None
    dependency_type: str
    parsing_source: str
    confidence: str


class LineageNode(BaseModel):
    """Represents a node in the lineage graph."""

    id: int = Field(..., description="Catalog object ID")
    source_name: str = Field(..., description="Data source name")
    schema_name: str = Field(..., description="Schema name")
    object_name: str = Field(..., description="Object name")
    object_type: str = Field(..., description="Object type (TABLE, VIEW, etc.)")
    distance: int = Field(..., description="Hops from root object (0 = root)")

    @property
    def full_name(self) -> str:
        """Return the fully-qualified object name."""
        return f"{self.source_name}.{self.schema_name}.{self.object_name}"


class ExternalNode(BaseModel):
    """Represents an external reference not in the catalog."""

    schema_name: str | None = Field(None, description="Schema name if known")
    object_name: str = Field(..., description="Object name")
    object_type: str | None = Field(None, description="Object type if known")
    distance: int = Field(..., description="Hops from root object")


class LineageEdge(BaseModel):
    """Represents an edge in the lineage graph."""

    from_id: int = Field(..., description="Source object ID")
    to_id: int | None = Field(None, description="Target object ID (null for external)")
    to_external: dict[str, Any] | None = Field(
        None, description="External reference details"
    )
    dependency_type: str = Field(..., description="DIRECT or INDIRECT")
    confidence: str = Field("HIGH", description="Confidence level")


class LineageGraph(BaseModel):
    """Complete lineage graph for an object."""

    root: LineageNode = Field(..., description="The root object being analyzed")
    nodes: list[LineageNode] = Field(
        default_factory=list, description="Objects in the graph"
    )
    external_nodes: list[ExternalNode] = Field(
        default_factory=list, description="External references"
    )
    edges: list[LineageEdge] = Field(
        default_factory=list, description="Dependencies between objects"
    )
    direction: str = Field(..., description="upstream or downstream")
    depth: int = Field(..., description="Maximum traversal depth")
    truncated: bool = Field(
        False, description="True if graph was truncated due to depth limit"
    )


class LineageSummary(BaseModel):
    """Summary statistics for lineage."""

    upstream_count: int = Field(0, description="Number of upstream dependencies")
    downstream_count: int = Field(0, description="Number of downstream dependents")
    external_count: int = Field(0, description="Number of external references")
