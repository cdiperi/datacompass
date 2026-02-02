"""Column SQLAlchemy model."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base

if TYPE_CHECKING:
    from datacompass.core.models.catalog_object import CatalogObject


class Column(Base):
    """Represents a column within a catalog object."""

    __tablename__ = "columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metadata from the source system (data_type, nullable, default, etc.)
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # User-provided metadata (descriptions, classifications, etc.)
    user_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationship
    object: Mapped["CatalogObject"] = relationship("CatalogObject", back_populates="columns")

    __table_args__ = (
        UniqueConstraint("object_id", "column_name", name="uq_column_object_name"),
    )

    @property
    def data_type(self) -> str | None:
        """Get the data type from source metadata."""
        if self.source_metadata:
            return self.source_metadata.get("data_type")
        return None

    @property
    def is_nullable(self) -> bool | None:
        """Get nullable flag from source metadata."""
        if self.source_metadata:
            return self.source_metadata.get("nullable")
        return None

    def __repr__(self) -> str:
        return f"<Column({self.column_name!r}, type={self.data_type!r})>"
