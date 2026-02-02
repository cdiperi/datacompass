"""Repository for DataSource operations."""

from datetime import datetime
from typing import Any

from sqlalchemy import select

from datacompass.core.models import DataSource
from datacompass.core.repositories.base import BaseRepository


class DataSourceRepository(BaseRepository[DataSource]):
    """Repository for DataSource CRUD operations."""

    model = DataSource

    def get_by_name(self, name: str) -> DataSource | None:
        """Get a data source by its unique name.

        Args:
            name: The unique name of the data source.

        Returns:
            DataSource instance or None if not found.
        """
        stmt = select(DataSource).where(DataSource.name == name)
        return self.session.scalar(stmt)

    def get_active(self) -> list[DataSource]:
        """Get all active data sources.

        Returns:
            List of active DataSource instances.
        """
        stmt = select(DataSource).where(DataSource.is_active == True)  # noqa: E712
        return list(self.session.scalars(stmt))

    def get_by_type(self, source_type: str) -> list[DataSource]:
        """Get all data sources of a specific type.

        Args:
            source_type: The type of data source (e.g., 'databricks').

        Returns:
            List of DataSource instances.
        """
        stmt = select(DataSource).where(DataSource.source_type == source_type)
        return list(self.session.scalars(stmt))

    def create(
        self,
        name: str,
        source_type: str,
        connection_info: dict[str, Any],
        display_name: str | None = None,
        sync_config: dict[str, Any] | None = None,
    ) -> DataSource:
        """Create a new data source.

        Args:
            name: Unique name for the source.
            source_type: Type of data source (e.g., 'databricks').
            connection_info: Connection configuration (sensitive fields should be encrypted).
            display_name: Human-readable display name.
            sync_config: Optional sync configuration.

        Returns:
            The created DataSource instance.
        """
        source = DataSource(
            name=name,
            display_name=display_name,
            source_type=source_type,
            connection_info=connection_info,
            sync_config=sync_config,
        )
        self.add(source)
        return source

    def update_scan_status(
        self,
        source: DataSource,
        status: str,
        message: str | None = None,
    ) -> DataSource:
        """Update the last scan status for a data source.

        Args:
            source: The DataSource to update.
            status: Scan status ('success', 'partial', 'failed').
            message: Optional status message.

        Returns:
            The updated DataSource instance.
        """
        source.last_scan_at = datetime.utcnow()
        source.last_scan_status = status
        source.last_scan_message = message
        return source

    def exists(self, name: str) -> bool:
        """Check if a data source with the given name exists.

        Args:
            name: The name to check.

        Returns:
            True if exists, False otherwise.
        """
        return self.get_by_name(name) is not None

    def deactivate(self, source: DataSource) -> DataSource:
        """Deactivate a data source.

        Args:
            source: The DataSource to deactivate.

        Returns:
            The updated DataSource instance.
        """
        source.is_active = False
        return source

    def activate(self, source: DataSource) -> DataSource:
        """Activate a data source.

        Args:
            source: The DataSource to activate.

        Returns:
            The updated DataSource instance.
        """
        source.is_active = True
        return source
