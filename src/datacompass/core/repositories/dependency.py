"""Repository for Dependency operations."""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import joinedload

from datacompass.core.models import CatalogObject, DataSource
from datacompass.core.models.dependency import Dependency
from datacompass.core.repositories.base import BaseRepository


class DependencyRepository(BaseRepository[Dependency]):
    """Repository for Dependency CRUD operations."""

    model = Dependency

    def get_by_natural_key(
        self,
        object_id: int,
        target_id: int | None,
        parsing_source: str,
    ) -> Dependency | None:
        """Get a dependency by its natural key.

        Args:
            object_id: ID of the dependent object.
            target_id: ID of the target object (can be None for external).
            parsing_source: Source of the dependency info.

        Returns:
            Dependency instance or None if not found.
        """
        stmt = select(Dependency).where(
            and_(
                Dependency.object_id == object_id,
                Dependency.target_id == target_id
                if target_id is not None
                else Dependency.target_id.is_(None),
                Dependency.parsing_source == parsing_source,
            )
        )
        return self.session.scalar(stmt)

    def upsert(
        self,
        source_id: int,
        object_id: int,
        target_id: int | None,
        dependency_type: str,
        parsing_source: str,
        target_external: dict[str, Any] | None = None,
        confidence: str = "HIGH",
    ) -> tuple[Dependency, Literal["created", "updated"]]:
        """Insert or update a dependency by natural key.

        Args:
            source_id: ID of the data source.
            object_id: ID of the dependent object.
            target_id: ID of the target object (None for external refs).
            dependency_type: DIRECT or INDIRECT.
            parsing_source: source_metadata, sql_parsing, or manual.
            target_external: External reference details (if target_id is None).
            confidence: HIGH, MEDIUM, or LOW.

        Returns:
            Tuple of (Dependency, action) where action is 'created' or 'updated'.
        """
        existing = self.get_by_natural_key(object_id, target_id, parsing_source)

        if existing:
            existing.dependency_type = dependency_type
            existing.target_external = target_external
            existing.confidence = confidence
            existing.updated_at = datetime.utcnow()
            return existing, "updated"
        else:
            dep = Dependency(
                source_id=source_id,
                object_id=object_id,
                target_id=target_id,
                target_external=target_external,
                dependency_type=dependency_type,
                parsing_source=parsing_source,
                confidence=confidence,
            )
            self.add(dep)
            return dep, "created"

    def upsert_batch(
        self,
        source_id: int,
        dependencies: list[dict[str, Any]],
        parsing_source: str,
    ) -> tuple[int, int]:
        """Batch upsert dependencies for a source.

        Args:
            source_id: ID of the data source.
            dependencies: List of dependency dicts with keys:
                - object_id: int
                - target_id: int | None
                - dependency_type: str
                - target_external: dict | None (optional)
                - confidence: str (optional, defaults to HIGH)
            parsing_source: Source of the dependency info.

        Returns:
            Tuple of (created_count, updated_count).
        """
        created = 0
        updated = 0

        for dep_data in dependencies:
            _, action = self.upsert(
                source_id=source_id,
                object_id=dep_data["object_id"],
                target_id=dep_data.get("target_id"),
                dependency_type=dep_data["dependency_type"],
                parsing_source=parsing_source,
                target_external=dep_data.get("target_external"),
                confidence=dep_data.get("confidence", "HIGH"),
            )
            if action == "created":
                created += 1
            else:
                updated += 1

        return created, updated

    def get_upstream(
        self,
        object_id: int,
        include_external: bool = True,
    ) -> list[Dependency]:
        """Get direct upstream dependencies for an object.

        These are the objects that the given object depends on.

        Args:
            object_id: ID of the catalog object.
            include_external: Whether to include external references.

        Returns:
            List of Dependency instances.
        """
        stmt = (
            select(Dependency)
            .options(
                joinedload(Dependency.target).joinedload(CatalogObject.source),
            )
            .where(Dependency.object_id == object_id)
        )
        if not include_external:
            stmt = stmt.where(Dependency.target_id.isnot(None))
        return list(self.session.scalars(stmt).unique())

    def get_downstream(self, object_id: int) -> list[Dependency]:
        """Get direct downstream dependencies (dependents) for an object.

        These are objects that depend on the given object.

        Args:
            object_id: ID of the catalog object.

        Returns:
            List of Dependency instances.
        """
        stmt = (
            select(Dependency)
            .options(
                joinedload(Dependency.object).joinedload(CatalogObject.source),
            )
            .where(Dependency.target_id == object_id)
        )
        return list(self.session.scalars(stmt).unique())

    def get_by_source(self, source_id: int) -> list[Dependency]:
        """Get all dependencies for a source.

        Args:
            source_id: ID of the data source.

        Returns:
            List of Dependency instances.
        """
        stmt = select(Dependency).where(Dependency.source_id == source_id)
        return list(self.session.scalars(stmt))

    def delete_by_source(self, source_id: int) -> int:
        """Delete all dependencies for a source.

        Used when re-scanning to clear stale dependencies.

        Args:
            source_id: ID of the data source.

        Returns:
            Number of dependencies deleted.
        """
        stmt = delete(Dependency).where(Dependency.source_id == source_id)
        result = self.session.execute(stmt)
        return result.rowcount

    def delete_by_parsing_source(
        self,
        source_id: int,
        parsing_source: str,
    ) -> int:
        """Delete dependencies from a specific parsing source.

        Useful for re-ingesting from a specific source without clearing manual deps.

        Args:
            source_id: ID of the data source.
            parsing_source: The parsing source to clear (e.g., "source_metadata").

        Returns:
            Number of dependencies deleted.
        """
        stmt = delete(Dependency).where(
            and_(
                Dependency.source_id == source_id,
                Dependency.parsing_source == parsing_source,
            )
        )
        result = self.session.execute(stmt)
        return result.rowcount

    def count_by_object(self, object_id: int) -> dict[str, int]:
        """Count upstream and downstream dependencies for an object.

        Args:
            object_id: ID of the catalog object.

        Returns:
            Dict with 'upstream' and 'downstream' counts.
        """
        upstream_stmt = select(Dependency).where(Dependency.object_id == object_id)
        downstream_stmt = select(Dependency).where(Dependency.target_id == object_id)

        return {
            "upstream": len(list(self.session.scalars(upstream_stmt))),
            "downstream": len(list(self.session.scalars(downstream_stmt))),
        }

    def get_objects_with_dependencies(
        self,
        source_id: int | None = None,
    ) -> list[int]:
        """Get IDs of objects that have dependencies (as dependent).

        Args:
            source_id: Optional filter by source.

        Returns:
            List of object IDs.
        """
        stmt = select(Dependency.object_id).distinct()
        if source_id is not None:
            stmt = stmt.where(Dependency.source_id == source_id)
        return list(self.session.scalars(stmt))

    def get_objects_with_dependents(
        self,
        source_id: int | None = None,
    ) -> list[int]:
        """Get IDs of objects that have dependents (as target).

        Args:
            source_id: Optional filter by source.

        Returns:
            List of object IDs.
        """
        stmt = select(Dependency.target_id).distinct().where(
            Dependency.target_id.isnot(None)
        )
        if source_id is not None:
            stmt = stmt.where(Dependency.source_id == source_id)
        return list(self.session.scalars(stmt))
