"""Repository for Usage Metrics operations."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import joinedload

from datacompass.core.models import CatalogObject
from datacompass.core.models.data_source import DataSource
from datacompass.core.models.usage import UsageMetric
from datacompass.core.repositories.base import BaseRepository


class UsageRepository(BaseRepository[UsageMetric]):
    """Repository for Usage Metrics CRUD operations."""

    model = UsageMetric

    def record_metrics(
        self,
        object_id: int,
        row_count: int | None = None,
        size_bytes: int | None = None,
        read_count: int | None = None,
        write_count: int | None = None,
        last_read_at: datetime | None = None,
        last_written_at: datetime | None = None,
        distinct_users: int | None = None,
        query_count: int | None = None,
        source_metrics: dict[str, Any] | None = None,
        collected_at: datetime | None = None,
    ) -> UsageMetric:
        """Record usage metrics for an object.

        Creates a new metrics snapshot.

        Args:
            object_id: ID of the catalog object.
            row_count: Number of rows in the object.
            size_bytes: Size of the object in bytes.
            read_count: Number of read operations.
            write_count: Number of write operations.
            last_read_at: Timestamp of last read.
            last_written_at: Timestamp of last write.
            distinct_users: Number of distinct users.
            query_count: Number of queries.
            source_metrics: Platform-specific metrics.
            collected_at: When metrics were collected (defaults to now).

        Returns:
            Created UsageMetric instance.
        """
        metric = UsageMetric(
            object_id=object_id,
            row_count=row_count,
            size_bytes=size_bytes,
            read_count=read_count,
            write_count=write_count,
            last_read_at=last_read_at,
            last_written_at=last_written_at,
            distinct_users=distinct_users,
            query_count=query_count,
            source_metrics=source_metrics,
            collected_at=collected_at or datetime.utcnow(),
        )
        self.add(metric)
        self.flush()
        return metric

    def get_latest(self, object_id: int) -> UsageMetric | None:
        """Get the most recent usage metrics for an object.

        Args:
            object_id: ID of the catalog object.

        Returns:
            Most recent UsageMetric or None if no metrics exist.
        """
        stmt = (
            select(UsageMetric)
            .where(UsageMetric.object_id == object_id)
            .order_by(desc(UsageMetric.collected_at))
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_latest_with_details(self, object_id: int) -> UsageMetric | None:
        """Get the most recent usage metrics with object details.

        Args:
            object_id: ID of the catalog object.

        Returns:
            Most recent UsageMetric with loaded relationships or None.
        """
        stmt = (
            select(UsageMetric)
            .options(
                joinedload(UsageMetric.object).joinedload(CatalogObject.source),
            )
            .where(UsageMetric.object_id == object_id)
            .order_by(desc(UsageMetric.collected_at))
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_history(
        self,
        object_id: int,
        days: int = 30,
        limit: int | None = None,
    ) -> list[UsageMetric]:
        """Get historical usage metrics for an object.

        Args:
            object_id: ID of the catalog object.
            days: Number of days to look back.
            limit: Maximum number of records to return.

        Returns:
            List of UsageMetric instances ordered by collected_at descending.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(UsageMetric)
            .where(
                and_(
                    UsageMetric.object_id == object_id,
                    UsageMetric.collected_at >= cutoff,
                )
            )
            .order_by(desc(UsageMetric.collected_at))
        )

        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.session.scalars(stmt))

    def get_hot_tables(
        self,
        source_id: int | None = None,
        days: int = 7,
        limit: int = 20,
        order_by: str = "read_count",
    ) -> list[tuple[CatalogObject, UsageMetric]]:
        """Get the most accessed tables based on latest metrics.

        Uses a subquery to get only the latest metric for each object,
        then orders by the specified metric.

        Args:
            source_id: Filter by source ID.
            days: Only consider metrics from the last N days.
            limit: Maximum number of results.
            order_by: Metric to order by (read_count, write_count, row_count, size_bytes).

        Returns:
            List of (CatalogObject, UsageMetric) tuples.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Subquery to get the latest metric ID for each object
        latest_metric_subq = (
            select(
                UsageMetric.object_id,
                func.max(UsageMetric.collected_at).label("max_collected"),
            )
            .where(UsageMetric.collected_at >= cutoff)
            .group_by(UsageMetric.object_id)
            .subquery()
        )

        # Main query joining on the latest metrics
        stmt = (
            select(CatalogObject, UsageMetric)
            .join(UsageMetric, CatalogObject.id == UsageMetric.object_id)
            .join(
                latest_metric_subq,
                and_(
                    UsageMetric.object_id == latest_metric_subq.c.object_id,
                    UsageMetric.collected_at == latest_metric_subq.c.max_collected,
                ),
            )
            .join(DataSource, CatalogObject.source_id == DataSource.id)
            .options(joinedload(CatalogObject.source))
        )

        if source_id is not None:
            stmt = stmt.where(CatalogObject.source_id == source_id)

        # Order by the specified metric (descending, nulls last)
        order_column = getattr(UsageMetric, order_by, UsageMetric.read_count)
        stmt = stmt.order_by(desc(order_column).nullslast())
        stmt = stmt.limit(limit)

        results = self.session.execute(stmt).all()
        return [(row[0], row[1]) for row in results]

    def get_objects_by_source(self, source_id: int) -> list[CatalogObject]:
        """Get all catalog objects for a source.

        Args:
            source_id: ID of the data source.

        Returns:
            List of CatalogObject instances.
        """
        stmt = (
            select(CatalogObject)
            .where(CatalogObject.source_id == source_id)
            .order_by(CatalogObject.schema_name, CatalogObject.object_name)
        )
        return list(self.session.scalars(stmt))

    def count_objects_with_metrics(self, source_id: int | None = None) -> int:
        """Count objects that have at least one usage metric.

        Args:
            source_id: Optional filter by source ID.

        Returns:
            Number of objects with metrics.
        """
        subq = select(UsageMetric.object_id).distinct().subquery()

        stmt = select(func.count()).select_from(CatalogObject).where(
            CatalogObject.id.in_(select(subq))
        )

        if source_id is not None:
            stmt = stmt.where(CatalogObject.source_id == source_id)

        return self.session.scalar(stmt) or 0

    def get_total_metrics_count(self, source_id: int | None = None) -> int:
        """Count total usage metric records.

        Args:
            source_id: Optional filter by source ID.

        Returns:
            Total number of metric records.
        """
        stmt = select(func.count()).select_from(UsageMetric)

        if source_id is not None:
            stmt = stmt.join(CatalogObject).where(CatalogObject.source_id == source_id)

        return self.session.scalar(stmt) or 0
