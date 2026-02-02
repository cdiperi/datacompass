"""Service for catalog operations (scanning, browsing objects)."""

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from datacompass.core.adapters import AdapterRegistry
from datacompass.core.events import ScanCompletedEvent, ScanFailedEvent, get_event_bus
from datacompass.core.models import (
    CatalogObject,
    CatalogObjectDetail,
    CatalogObjectSummary,
    ColumnSummary,
    ForeignKeyConstraint,
    ScanResult,
    ScanStats,
)
from datacompass.core.repositories import (
    CatalogObjectRepository,
    ColumnRepository,
    DataSourceRepository,
    DependencyRepository,
    SearchRepository,
)
from datacompass.core.services.source_service import SourceNotFoundError


class CatalogServiceError(Exception):
    """Raised when a catalog service operation fails."""

    pass


class ObjectNotFoundError(CatalogServiceError):
    """Raised when a catalog object is not found."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Catalog object not found: {identifier!r}")
        self.identifier = identifier


class CatalogService:
    """Service for catalog operations.

    Handles:
    - Scanning sources to discover/update objects
    - Listing and filtering catalog objects
    - Getting detailed object information
    """

    def __init__(self, session: Session) -> None:
        """Initialize catalog service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.source_repo = DataSourceRepository(session)
        self.object_repo = CatalogObjectRepository(session)
        self.column_repo = ColumnRepository(session)
        self.search_repo = SearchRepository(session)
        self.dependency_repo = DependencyRepository(session)

    def scan_source(self, name: str, full: bool = False) -> ScanResult:
        """Scan a data source to discover and update catalog objects.

        Args:
            name: Name of the source to scan.
            full: If True, performs full scan. Otherwise incremental (default).

        Returns:
            ScanResult with statistics.

        Raises:
            SourceNotFoundError: If source does not exist.
        """
        source = self.source_repo.get_by_name(name)
        if source is None:
            raise SourceNotFoundError(name)

        started_at = datetime.utcnow()

        async def _scan() -> ScanStats:
            adapter = AdapterRegistry.get_adapter(
                source.source_type,
                source.connection_info,
            )

            stats = ScanStats()

            async with adapter:
                # Get all objects from source
                objects = await adapter.get_objects()

                # Track IDs of objects we've seen (for soft-delete detection)
                seen_ids: set[int] = set()

                # Upsert objects
                for obj_data in objects:
                    obj, action = self.object_repo.upsert(
                        source_id=source.id,
                        schema_name=obj_data["schema_name"],
                        object_name=obj_data["object_name"],
                        object_type=obj_data["object_type"],
                        source_metadata=obj_data.get("source_metadata"),
                    )
                    self.session.flush()  # Get ID for new objects
                    seen_ids.add(obj.id)

                    if action == "created":
                        stats.objects_created += 1
                    else:
                        stats.objects_updated += 1

                # Fetch columns for all discovered objects
                # Use constraint-enriched columns if available (includes FK metadata)
                object_keys = [
                    (obj_data["schema_name"], obj_data["object_name"])
                    for obj_data in objects
                ]
                columns = await self._get_columns_from_adapter(adapter, object_keys)

                # Group columns by object
                columns_by_object: dict[tuple[str, str], list[dict[str, Any]]] = {}
                for col_data in columns:
                    key = (col_data["schema_name"], col_data["object_name"])
                    if key not in columns_by_object:
                        columns_by_object[key] = []
                    columns_by_object[key].append(col_data)

                # Upsert columns for each object
                for obj_data in objects:
                    key = (obj_data["schema_name"], obj_data["object_name"])
                    obj = self.object_repo.get_by_natural_key(
                        source_id=source.id,
                        schema_name=obj_data["schema_name"],
                        object_name=obj_data["object_name"],
                        object_type=obj_data["object_type"],
                    )
                    if obj is None:
                        continue

                    obj_columns = columns_by_object.get(key, [])
                    created, updated, deleted = self.column_repo.upsert_batch(
                        object_id=obj.id,
                        columns=[
                            {
                                "column_name": c["column_name"],
                                "position": c["position"],
                                "source_metadata": c.get("source_metadata"),
                            }
                            for c in obj_columns
                        ],
                    )
                    stats.columns_created += created
                    stats.columns_updated += updated
                    stats.columns_deleted += deleted

                # Extract lineage if adapter supports it
                await self._extract_lineage(adapter, source.id)

                # Soft-delete objects no longer in source
                if full:
                    stats.objects_deleted = self.object_repo.soft_delete_missing(
                        source_id=source.id,
                        current_ids=seen_ids,
                    )

                stats.total_objects = len(seen_ids)
                stats.total_columns = sum(len(cols) for cols in columns_by_object.values())

            return stats

        try:
            stats = asyncio.run(_scan())
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            # Update source scan status
            self.source_repo.update_scan_status(source, "success")

            # Reindex FTS for this source
            self.search_repo.reindex_all(source_id=source.id)

            # Emit scan completed event
            event = ScanCompletedEvent.create(
                source_name=name,
                source_id=source.id,
                objects_discovered=stats.objects_created,
                objects_updated=stats.objects_updated,
                objects_deleted=stats.objects_deleted,
                columns_discovered=stats.columns_created,
                duration_seconds=round(duration, 2),
            )
            get_event_bus().emit(event)

            return ScanResult(
                source_name=name,
                source_type=source.source_type,
                status="success",
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=round(duration, 2),
                stats=stats,
            )

        except Exception as e:
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            # Update source scan status
            self.source_repo.update_scan_status(source, "failed", str(e))

            # Emit scan failed event
            event = ScanFailedEvent.create(
                source_name=name,
                source_id=source.id,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            get_event_bus().emit(event)

            return ScanResult(
                source_name=name,
                source_type=source.source_type,
                status="failed",
                message=str(e),
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=round(duration, 2),
                stats=ScanStats(),
            )

    def list_objects(
        self,
        source: str | None = None,
        object_type: str | None = None,
        schema: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CatalogObjectSummary]:
        """List catalog objects with optional filters.

        Args:
            source: Filter by source name.
            object_type: Filter by object type (TABLE, VIEW, etc.).
            schema: Filter by schema name.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            List of CatalogObjectSummary instances.
        """
        objects = self.object_repo.list_objects(
            source_name=source,
            object_type=object_type,
            schema_name=schema,
            limit=limit,
            offset=offset,
        )

        return [
            CatalogObjectSummary(
                id=obj.id,
                source_name=obj.source.name,
                schema_name=obj.schema_name,
                object_name=obj.object_name,
                object_type=obj.object_type,
                description=obj.source_metadata.get("description")
                if obj.source_metadata
                else None,
                column_count=self.column_repo.count_by_object(obj.id),
            )
            for obj in objects
        ]

    def get_object(self, identifier: str) -> CatalogObjectDetail:
        """Get detailed information about a catalog object.

        Args:
            identifier: Object identifier in format "source.schema.name" or object ID.

        Returns:
            CatalogObjectDetail with columns.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(identifier)
        if obj is None:
            raise ObjectNotFoundError(identifier)

        # Get columns
        columns = self.column_repo.get_by_object(obj.id)

        return CatalogObjectDetail(
            id=obj.id,
            source_id=obj.source_id,
            source_name=obj.source.name,
            schema_name=obj.schema_name,
            object_name=obj.object_name,
            object_type=obj.object_type,
            source_metadata=obj.source_metadata,
            user_metadata=obj.user_metadata,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            deleted_at=obj.deleted_at,
            columns=[
                ColumnSummary(
                    column_name=col.column_name,
                    data_type=col.source_metadata.get("data_type") if col.source_metadata else None,
                    nullable=col.source_metadata.get("nullable") if col.source_metadata else None,
                    description=col.source_metadata.get("description")
                    if col.source_metadata
                    else None,
                    foreign_key=self._extract_fk_constraint(col.source_metadata),
                )
                for col in columns
            ],
        )

    def _extract_fk_constraint(
        self, source_metadata: dict[str, Any] | None
    ) -> ForeignKeyConstraint | None:
        """Extract foreign key constraint from column source_metadata.

        Args:
            source_metadata: Column's source_metadata dict.

        Returns:
            ForeignKeyConstraint if present, None otherwise.
        """
        if not source_metadata:
            return None
        constraints = source_metadata.get("constraints", {})
        fk = constraints.get("foreign_key")
        if not fk:
            return None
        return ForeignKeyConstraint(**fk)

    def _resolve_object(self, identifier: str) -> CatalogObject | None:
        """Resolve an object identifier to a CatalogObject.

        Supports:
        - Numeric ID: "123"
        - Qualified name: "source.schema.name"

        Args:
            identifier: Object identifier.

        Returns:
            CatalogObject or None if not found.
        """
        # Try as numeric ID first
        if identifier.isdigit():
            obj = self.object_repo.get_with_source(int(identifier))
            if obj:
                return obj

        # Try as qualified name (source.schema.object)
        parts = identifier.split(".")
        if len(parts) == 3:
            source_name, schema_name, object_name = parts
            source = self.source_repo.get_by_name(source_name)
            if source:
                # Get objects matching schema.name (could be multiple types)
                objects = self.object_repo.list_objects(
                    source_id=source.id,
                    schema_name=schema_name,
                )
                for obj in objects:
                    if obj.object_name == object_name:
                        return self.object_repo.get_with_source(obj.id)

        return None

    async def _extract_lineage(self, adapter: Any, source_id: int) -> None:
        """Extract lineage from adapter if supported.

        Calls adapter's get_view_dependencies() method if it exists, and stores
        the relationships in the dependency table.

        Note: Foreign key constraints are stored as column metadata (in
        source_metadata.constraints.foreign_key), not as lineage dependencies.

        Args:
            adapter: The source adapter instance.
            source_id: ID of the data source.
        """
        dependencies: list[dict[str, Any]] = []

        # Extract view dependencies
        try:
            if hasattr(adapter, "get_view_dependencies") and callable(
                adapter.get_view_dependencies
            ):
                view_deps = await adapter.get_view_dependencies()
                if isinstance(view_deps, list):
                    for dep in view_deps:
                        # Resolve the view
                        view_obj = self.object_repo.get_by_qualified_name(
                            source_id=source_id,
                            schema_name=dep["view_schema"],
                            object_name=dep["view_name"],
                        )
                        # Resolve the source table/view
                        source_table = self.object_repo.get_by_qualified_name(
                            source_id=source_id,
                            schema_name=dep["source_schema"],
                            object_name=dep["source_table"],
                        )

                        if view_obj and source_table:
                            dependencies.append({
                                "object_id": view_obj.id,
                                "target_id": source_table.id,
                                "dependency_type": "DIRECT",
                                "confidence": "HIGH",
                            })
        except (TypeError, AttributeError):
            # Adapter doesn't support view dependency extraction
            pass

        # Batch upsert dependencies
        if dependencies:
            # Clear existing source_metadata dependencies for this source
            self.dependency_repo.delete_by_parsing_source(source_id, "source_metadata")
            # Insert new dependencies
            self.dependency_repo.upsert_batch(
                source_id=source_id,
                dependencies=dependencies,
                parsing_source="source_metadata",
            )

    async def _get_columns_from_adapter(
        self, adapter: Any, object_keys: list[tuple[str, str]]
    ) -> list[dict[str, Any]]:
        """Get columns from adapter, using constraint-enriched method if available.

        Tries to use get_columns_with_constraints() if the adapter provides it
        (which includes FK constraint info in source_metadata), otherwise falls
        back to get_columns().

        Args:
            adapter: The source adapter instance.
            object_keys: List of (schema_name, object_name) tuples.

        Returns:
            List of column metadata dicts.
        """
        try:
            get_with_constraints = getattr(
                adapter, "get_columns_with_constraints", None
            )
            if get_with_constraints is not None and callable(get_with_constraints):
                result: list[dict[str, Any]] = await get_with_constraints(object_keys)
                return result
        except (TypeError, AttributeError):
            pass
        columns: list[dict[str, Any]] = await adapter.get_columns(object_keys)
        return columns
