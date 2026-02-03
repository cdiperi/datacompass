"""Service for Usage Metrics operations."""

import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

from datacompass.core.adapters.registry import AdapterRegistry
from datacompass.core.models.usage import (
    HotTableItem,
    UsageCollectResult,
    UsageHubSummary,
    UsageMetricDetailResponse,
    UsageMetricResponse,
)
from datacompass.core.repositories import (
    CatalogObjectRepository,
    DataSourceRepository,
    UsageRepository,
)
from datacompass.core.services.source_service import SourceNotFoundError


class UsageServiceError(Exception):
    """Base exception for usage service errors."""

    pass


class ObjectNotFoundError(UsageServiceError):
    """Raised when a catalog object is not found."""

    def __init__(self, identifier: str | int) -> None:
        self.identifier = identifier
        super().__init__(f"Object not found: {identifier}")


class UsageService:
    """Service for usage metrics operations.

    Handles:
    - Usage metrics collection from data sources
    - Querying latest and historical metrics
    - Hot tables ranking
    """

    def __init__(self, session: Session) -> None:
        """Initialize usage service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.usage_repo = UsageRepository(session)
        self.object_repo = CatalogObjectRepository(session)
        self.source_repo = DataSourceRepository(session)

    def collect_metrics(self, source_name: str) -> UsageCollectResult:
        """Collect usage metrics for all objects in a source.

        Args:
            source_name: Name of the data source.

        Returns:
            UsageCollectResult with collection statistics.

        Raises:
            SourceNotFoundError: If source not found.
        """
        source = self.source_repo.get_by_name(source_name)
        if source is None:
            raise SourceNotFoundError(source_name)

        # Get all objects for the source
        objects = self.object_repo.get_by_source(source.id)
        if not objects:
            return UsageCollectResult(
                source_name=source_name,
                collected_count=0,
                skipped_count=0,
                error_count=0,
                collected_at=datetime.utcnow(),
            )

        # Build list of (schema_name, object_name) tuples
        object_tuples = [(obj.schema_name, obj.object_name) for obj in objects]

        # Create adapter and collect metrics
        adapter = AdapterRegistry.get_adapter(source.source_type, source.connection_info)
        metrics_data = asyncio.run(self._collect_from_adapter(adapter, object_tuples))

        # Build lookup for collected metrics
        metrics_lookup = {
            (m["schema_name"], m["object_name"]): m for m in metrics_data
        }

        collected_count = 0
        skipped_count = 0
        collected_at = datetime.utcnow()

        # Record metrics for each object
        for obj in objects:
            key = (obj.schema_name, obj.object_name)
            if key in metrics_lookup:
                m = metrics_lookup[key]
                self.usage_repo.record_metrics(
                    object_id=obj.id,
                    row_count=m.get("row_count"),
                    size_bytes=m.get("size_bytes"),
                    read_count=m.get("read_count"),
                    write_count=m.get("write_count"),
                    last_read_at=m.get("last_read_at"),
                    last_written_at=m.get("last_written_at"),
                    distinct_users=m.get("distinct_users"),
                    query_count=m.get("query_count"),
                    source_metrics=m.get("source_metrics"),
                    collected_at=collected_at,
                )
                collected_count += 1
            else:
                skipped_count += 1

        return UsageCollectResult(
            source_name=source_name,
            collected_count=collected_count,
            skipped_count=skipped_count,
            error_count=0,
            collected_at=collected_at,
        )

    async def _collect_from_adapter(
        self,
        adapter,
        objects: list[tuple[str, str]],
    ) -> list[dict]:
        """Collect metrics from adapter.

        Args:
            adapter: Source adapter instance.
            objects: List of (schema_name, object_name) tuples.

        Returns:
            List of metric dictionaries.
        """
        async with adapter:
            return await adapter.get_usage_metrics(objects)

    def get_object_usage(
        self,
        object_identifier: str | int,
    ) -> UsageMetricDetailResponse | None:
        """Get latest usage metrics for an object.

        Args:
            object_identifier: Object ID or identifier string (source.schema.name).

        Returns:
            UsageMetricDetailResponse or None if no metrics exist.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        metric = self.usage_repo.get_latest_with_details(obj.id)

        if metric is None:
            return None

        return UsageMetricDetailResponse(
            id=metric.id,
            object_id=metric.object_id,
            collected_at=metric.collected_at,
            row_count=metric.row_count,
            size_bytes=metric.size_bytes,
            read_count=metric.read_count,
            write_count=metric.write_count,
            last_read_at=metric.last_read_at,
            last_written_at=metric.last_written_at,
            distinct_users=metric.distinct_users,
            query_count=metric.query_count,
            source_metrics=metric.source_metrics,
            object_name=metric.object.object_name,
            schema_name=metric.object.schema_name,
            source_name=metric.object.source.name,
        )

    def get_usage_history(
        self,
        object_identifier: str | int,
        days: int = 30,
        limit: int | None = None,
    ) -> list[UsageMetricResponse]:
        """Get historical usage metrics for an object.

        Args:
            object_identifier: Object ID or identifier string.
            days: Number of days to look back.
            limit: Maximum number of records.

        Returns:
            List of UsageMetricResponse.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        obj = self._resolve_object(object_identifier)
        metrics = self.usage_repo.get_history(obj.id, days=days, limit=limit)

        return [
            UsageMetricResponse(
                id=m.id,
                object_id=m.object_id,
                collected_at=m.collected_at,
                row_count=m.row_count,
                size_bytes=m.size_bytes,
                read_count=m.read_count,
                write_count=m.write_count,
                last_read_at=m.last_read_at,
                last_written_at=m.last_written_at,
                distinct_users=m.distinct_users,
                query_count=m.query_count,
                source_metrics=m.source_metrics,
            )
            for m in metrics
        ]

    def get_hot_tables(
        self,
        source_name: str | None = None,
        days: int = 7,
        limit: int = 20,
        order_by: str = "read_count",
    ) -> list[HotTableItem]:
        """Get the most accessed tables.

        Args:
            source_name: Optional filter by source name.
            days: Only consider metrics from last N days.
            limit: Maximum number of results.
            order_by: Metric to order by.

        Returns:
            List of HotTableItem.

        Raises:
            SourceNotFoundError: If source_name provided but not found.
        """
        source_id = None
        if source_name:
            source = self.source_repo.get_by_name(source_name)
            if source is None:
                raise SourceNotFoundError(source_name)
            source_id = source.id

        results = self.usage_repo.get_hot_tables(
            source_id=source_id,
            days=days,
            limit=limit,
            order_by=order_by,
        )

        return [
            HotTableItem(
                object_id=obj.id,
                object_name=obj.object_name,
                schema_name=obj.schema_name,
                source_name=obj.source.name,
                row_count=metric.row_count,
                size_bytes=metric.size_bytes,
                read_count=metric.read_count,
                write_count=metric.write_count,
                last_read_at=metric.last_read_at,
                last_written_at=metric.last_written_at,
            )
            for obj, metric in results
        ]

    def get_hub_summary(
        self,
        source_name: str | None = None,
    ) -> UsageHubSummary:
        """Get summary statistics for usage metrics.

        Args:
            source_name: Optional filter by source name.

        Returns:
            UsageHubSummary with aggregated statistics.
        """
        source_id = None
        if source_name:
            source = self.source_repo.get_by_name(source_name)
            if source:
                source_id = source.id

        total_objects = self.usage_repo.count_objects_with_metrics(source_id=source_id)
        total_metrics = self.usage_repo.get_total_metrics_count(source_id=source_id)

        # Get hot tables for the summary
        hot_tables = self.get_hot_tables(
            source_name=source_name,
            days=7,
            limit=10,
            order_by="read_count",
        )

        return UsageHubSummary(
            total_objects_with_metrics=total_objects,
            total_metrics_collected=total_metrics,
            hot_tables=hot_tables,
        )

    def _resolve_object(self, identifier: str | int):
        """Resolve an object identifier to a CatalogObject.

        Args:
            identifier: Object ID or identifier string (source.schema.name or schema.name).

        Returns:
            CatalogObject instance.

        Raises:
            ObjectNotFoundError: If object not found.
        """
        if isinstance(identifier, int):
            obj = self.object_repo.get_by_id(identifier)
            if obj is None:
                raise ObjectNotFoundError(identifier)
            return obj

        parts = identifier.split(".")
        if len(parts) == 3:
            # source.schema.name format
            source_name, schema_name, object_name = parts
            source = self.source_repo.get_by_name(source_name)
            if source is None:
                raise ObjectNotFoundError(identifier)
            obj = self.object_repo.get_by_name(source.id, schema_name, object_name)
        elif len(parts) == 2:
            # schema.name format - search across all sources
            schema_name, object_name = parts
            obj = self.object_repo.find_by_schema_and_name(schema_name, object_name)
        else:
            raise ObjectNotFoundError(identifier)

        if obj is None:
            raise ObjectNotFoundError(identifier)

        return obj
