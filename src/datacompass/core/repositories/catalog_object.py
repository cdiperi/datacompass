"""Repository for CatalogObject operations with UPSERT support."""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import and_, select
from sqlalchemy.orm import joinedload

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.repositories.base import BaseRepository


class CatalogObjectRepository(BaseRepository[CatalogObject]):
    """Repository for CatalogObject CRUD operations with UPSERT support."""

    model = CatalogObject

    def get_by_natural_key(
        self,
        source_id: int,
        schema_name: str,
        object_name: str,
        object_type: str,
    ) -> CatalogObject | None:
        """Get an object by its natural key.

        Args:
            source_id: ID of the data source.
            schema_name: Schema name.
            object_name: Object name.
            object_type: Type of object (TABLE, VIEW, etc.).

        Returns:
            CatalogObject instance or None if not found.
        """
        stmt = select(CatalogObject).where(
            and_(
                CatalogObject.source_id == source_id,
                CatalogObject.schema_name == schema_name,
                CatalogObject.object_name == object_name,
                CatalogObject.object_type == object_type,
            )
        )
        return self.session.scalar(stmt)

    def upsert(
        self,
        source_id: int,
        schema_name: str,
        object_name: str,
        object_type: str,
        source_metadata: dict[str, Any] | None = None,
    ) -> tuple[CatalogObject, Literal["created", "updated"]]:
        """Insert or update a catalog object by natural key.

        Preserves user_metadata when updating. Un-deletes soft-deleted records.

        Args:
            source_id: ID of the data source.
            schema_name: Schema name.
            object_name: Object name.
            object_type: Type of object (TABLE, VIEW, etc.).
            source_metadata: Metadata from the source system.

        Returns:
            Tuple of (CatalogObject, action) where action is 'created' or 'updated'.
        """
        existing = self.get_by_natural_key(source_id, schema_name, object_name, object_type)

        if existing:
            existing.source_metadata = source_metadata
            existing.updated_at = datetime.utcnow()
            existing.deleted_at = None  # Un-delete if re-discovered
            return existing, "updated"
        else:
            obj = CatalogObject(
                source_id=source_id,
                schema_name=schema_name,
                object_name=object_name,
                object_type=object_type,
                source_metadata=source_metadata,
            )
            self.add(obj)
            return obj, "created"

    def get_by_source(
        self,
        source_id: int,
        include_deleted: bool = False,
    ) -> list[CatalogObject]:
        """Get all objects for a data source.

        Args:
            source_id: ID of the data source.
            include_deleted: Whether to include soft-deleted objects.

        Returns:
            List of CatalogObject instances.
        """
        stmt = select(CatalogObject).where(CatalogObject.source_id == source_id)
        if not include_deleted:
            stmt = stmt.where(CatalogObject.deleted_at.is_(None))
        stmt = stmt.order_by(CatalogObject.schema_name, CatalogObject.object_name)
        return list(self.session.scalars(stmt))

    def get_by_source_and_type(
        self,
        source_id: int,
        object_type: str,
        include_deleted: bool = False,
    ) -> list[CatalogObject]:
        """Get objects of a specific type for a data source.

        Args:
            source_id: ID of the data source.
            object_type: Type of object (TABLE, VIEW, etc.).
            include_deleted: Whether to include soft-deleted objects.

        Returns:
            List of CatalogObject instances.
        """
        stmt = select(CatalogObject).where(
            and_(
                CatalogObject.source_id == source_id,
                CatalogObject.object_type == object_type,
            )
        )
        if not include_deleted:
            stmt = stmt.where(CatalogObject.deleted_at.is_(None))
        stmt = stmt.order_by(CatalogObject.schema_name, CatalogObject.object_name)
        return list(self.session.scalars(stmt))

    def get_by_schema(
        self,
        source_id: int,
        schema_name: str,
        include_deleted: bool = False,
    ) -> list[CatalogObject]:
        """Get all objects in a specific schema.

        Args:
            source_id: ID of the data source.
            schema_name: Schema name.
            include_deleted: Whether to include soft-deleted objects.

        Returns:
            List of CatalogObject instances.
        """
        stmt = select(CatalogObject).where(
            and_(
                CatalogObject.source_id == source_id,
                CatalogObject.schema_name == schema_name,
            )
        )
        if not include_deleted:
            stmt = stmt.where(CatalogObject.deleted_at.is_(None))
        stmt = stmt.order_by(CatalogObject.object_name)
        return list(self.session.scalars(stmt))

    def get_with_columns(self, object_id: int) -> CatalogObject | None:
        """Get an object with its columns eagerly loaded.

        Args:
            object_id: ID of the catalog object.

        Returns:
            CatalogObject with columns loaded, or None if not found.
        """
        stmt = (
            select(CatalogObject)
            .options(joinedload(CatalogObject.columns))
            .where(CatalogObject.id == object_id)
        )
        return self.session.scalar(stmt)

    def get_with_source(self, object_id: int) -> CatalogObject | None:
        """Get an object with its source eagerly loaded.

        Args:
            object_id: ID of the catalog object.

        Returns:
            CatalogObject with source loaded, or None if not found.
        """
        stmt = (
            select(CatalogObject)
            .options(joinedload(CatalogObject.source))
            .where(CatalogObject.id == object_id)
        )
        return self.session.scalar(stmt)

    def soft_delete_missing(
        self,
        source_id: int,
        current_ids: set[int],
    ) -> int:
        """Soft delete objects not in the current set of IDs.

        Used after a scan to mark objects that no longer exist in the source.

        Args:
            source_id: ID of the data source.
            current_ids: Set of object IDs that still exist.

        Returns:
            Number of objects soft-deleted.
        """
        # Get all non-deleted objects for this source
        stmt = select(CatalogObject).where(
            and_(
                CatalogObject.source_id == source_id,
                CatalogObject.deleted_at.is_(None),
            )
        )
        objects = list(self.session.scalars(stmt))
        count = 0
        for obj in objects:
            if obj.id not in current_ids:
                obj.soft_delete()
                count += 1
        return count

    def list_objects(
        self,
        source_id: int | None = None,
        source_name: str | None = None,
        object_type: str | None = None,
        schema_name: str | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CatalogObject]:
        """List objects with optional filters.

        Args:
            source_id: Filter by source ID.
            source_name: Filter by source name (alternative to source_id).
            object_type: Filter by object type.
            schema_name: Filter by schema name.
            include_deleted: Whether to include soft-deleted objects.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of CatalogObject instances.
        """
        stmt = select(CatalogObject).options(joinedload(CatalogObject.source))

        if source_id is not None:
            stmt = stmt.where(CatalogObject.source_id == source_id)
        elif source_name is not None:
            stmt = stmt.join(DataSource).where(DataSource.name == source_name)

        if object_type is not None:
            stmt = stmt.where(CatalogObject.object_type == object_type)

        if schema_name is not None:
            stmt = stmt.where(CatalogObject.schema_name == schema_name)

        if not include_deleted:
            stmt = stmt.where(CatalogObject.deleted_at.is_(None))

        stmt = stmt.order_by(CatalogObject.schema_name, CatalogObject.object_name)
        stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt).unique())

    def count_by_source(self, source_id: int, include_deleted: bool = False) -> int:
        """Count objects for a data source.

        Args:
            source_id: ID of the data source.
            include_deleted: Whether to include soft-deleted objects.

        Returns:
            Number of objects.
        """
        stmt = select(CatalogObject).where(CatalogObject.source_id == source_id)
        if not include_deleted:
            stmt = stmt.where(CatalogObject.deleted_at.is_(None))
        return len(list(self.session.scalars(stmt)))

    def count_by_type(
        self,
        source_id: int,
        object_type: str,
        include_deleted: bool = False,
    ) -> int:
        """Count objects of a specific type.

        Args:
            source_id: ID of the data source.
            object_type: Type of object.
            include_deleted: Whether to include soft-deleted objects.

        Returns:
            Number of objects.
        """
        stmt = select(CatalogObject).where(
            and_(
                CatalogObject.source_id == source_id,
                CatalogObject.object_type == object_type,
            )
        )
        if not include_deleted:
            stmt = stmt.where(CatalogObject.deleted_at.is_(None))
        return len(list(self.session.scalars(stmt)))
