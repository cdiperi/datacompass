"""Repository for Column operations."""

from typing import Any, Literal

from sqlalchemy import and_, delete, select

from datacompass.core.models import Column
from datacompass.core.repositories.base import BaseRepository


class ColumnRepository(BaseRepository[Column]):
    """Repository for Column CRUD operations."""

    model = Column

    def get_by_object(self, object_id: int) -> list[Column]:
        """Get all columns for a catalog object.

        Args:
            object_id: ID of the catalog object.

        Returns:
            List of Column instances ordered by position.
        """
        stmt = (
            select(Column)
            .where(Column.object_id == object_id)
            .order_by(Column.position)
        )
        return list(self.session.scalars(stmt))

    def get_by_name(self, object_id: int, column_name: str) -> Column | None:
        """Get a column by object ID and column name.

        Args:
            object_id: ID of the catalog object.
            column_name: Name of the column.

        Returns:
            Column instance or None if not found.
        """
        stmt = select(Column).where(
            and_(
                Column.object_id == object_id,
                Column.column_name == column_name,
            )
        )
        return self.session.scalar(stmt)

    def upsert(
        self,
        object_id: int,
        column_name: str,
        position: int,
        source_metadata: dict[str, Any] | None = None,
    ) -> tuple[Column, Literal["created", "updated"]]:
        """Insert or update a column.

        Preserves user_metadata when updating.

        Args:
            object_id: ID of the parent catalog object.
            column_name: Name of the column.
            position: Ordinal position of the column.
            source_metadata: Metadata from the source system.

        Returns:
            Tuple of (Column, action) where action is 'created' or 'updated'.
        """
        existing = self.get_by_name(object_id, column_name)

        if existing:
            existing.position = position
            existing.source_metadata = source_metadata
            return existing, "updated"
        else:
            col = Column(
                object_id=object_id,
                column_name=column_name,
                position=position,
                source_metadata=source_metadata,
            )
            self.add(col)
            return col, "created"

    def upsert_batch(
        self,
        object_id: int,
        columns: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Upsert a batch of columns for an object.

        Removes columns that are no longer present.

        Args:
            object_id: ID of the parent catalog object.
            columns: List of column data dicts with keys:
                     column_name, position, source_metadata.

        Returns:
            Tuple of (created_count, updated_count, deleted_count).
        """
        created = 0
        updated = 0

        # Track column names we've processed
        current_names: set[str] = set()

        for col_data in columns:
            column_name = col_data["column_name"]
            current_names.add(column_name)

            _, action = self.upsert(
                object_id=object_id,
                column_name=column_name,
                position=col_data["position"],
                source_metadata=col_data.get("source_metadata"),
            )
            if action == "created":
                created += 1
            else:
                updated += 1

        # Delete columns that are no longer present
        deleted = self.delete_missing(object_id, current_names)

        return created, updated, deleted

    def delete_missing(self, object_id: int, current_names: set[str]) -> int:
        """Delete columns not in the current set of names.

        Args:
            object_id: ID of the parent catalog object.
            current_names: Set of column names that still exist.

        Returns:
            Number of columns deleted.
        """
        if not current_names:
            # Delete all columns for this object
            stmt = delete(Column).where(Column.object_id == object_id)
        else:
            stmt = delete(Column).where(
                and_(
                    Column.object_id == object_id,
                    ~Column.column_name.in_(current_names),
                )
            )
        result = self.session.execute(stmt)
        return result.rowcount

    def delete_by_object(self, object_id: int) -> int:
        """Delete all columns for an object.

        Args:
            object_id: ID of the parent catalog object.

        Returns:
            Number of columns deleted.
        """
        stmt = delete(Column).where(Column.object_id == object_id)
        result = self.session.execute(stmt)
        return result.rowcount

    def count_by_object(self, object_id: int) -> int:
        """Count columns for an object.

        Args:
            object_id: ID of the catalog object.

        Returns:
            Number of columns.
        """
        stmt = select(Column).where(Column.object_id == object_id)
        return len(list(self.session.scalars(stmt)))
