"""Service for managing data sources."""

import asyncio
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from datacompass.core.adapters import AdapterNotFoundError, AdapterRegistry
from datacompass.core.models import ConnectionTestResult, DataSource
from datacompass.core.repositories import DataSourceRepository
from datacompass.core.services.config_loader import load_source_config


class SourceServiceError(Exception):
    """Raised when a source service operation fails."""

    pass


class SourceNotFoundError(SourceServiceError):
    """Raised when a requested source does not exist."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Data source not found: {name!r}")
        self.name = name


class SourceExistsError(SourceServiceError):
    """Raised when trying to create a source that already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Data source already exists: {name!r}")
        self.name = name


class SourceService:
    """Service for managing data source configurations.

    Handles:
    - Adding, listing, and removing data sources
    - Testing source connections
    - Configuration loading and validation

    All adapter operations are async but wrapped for sync CLI usage.
    """

    def __init__(self, session: Session) -> None:
        """Initialize source service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.repo = DataSourceRepository(session)

    def add_source(
        self,
        name: str,
        source_type: str,
        config_path: Path,
        display_name: str | None = None,
    ) -> DataSource:
        """Add a new data source.

        Args:
            name: Unique name for the source.
            source_type: Type of adapter (e.g., 'databricks').
            config_path: Path to YAML configuration file.
            display_name: Optional human-readable name.

        Returns:
            Created DataSource instance.

        Raises:
            SourceExistsError: If source with name already exists.
            AdapterNotFoundError: If source_type is not registered.
            ConfigLoadError: If config file is invalid.
        """
        if self.repo.exists(name):
            raise SourceExistsError(name)

        if not AdapterRegistry.is_registered(source_type):
            raise AdapterNotFoundError(source_type)

        # Load and validate config
        config = load_source_config(config_path)

        # Validate against adapter's config schema
        schema = AdapterRegistry.get_config_schema(source_type)
        validated = schema(**config)

        # Store config as dict (with secrets as strings)
        connection_info = validated.model_dump(mode="json")

        source = self.repo.create(
            name=name,
            source_type=source_type,
            connection_info=connection_info,
            display_name=display_name,
        )

        return source

    def add_source_from_dict(
        self,
        name: str,
        source_type: str,
        connection_info: dict[str, Any],
        display_name: str | None = None,
    ) -> DataSource:
        """Add a new data source from a connection info dict.

        This method is for API use where configuration is provided directly
        rather than from a file.

        Args:
            name: Unique name for the source.
            source_type: Type of adapter (e.g., 'databricks').
            connection_info: Connection configuration dict.
            display_name: Optional human-readable name.

        Returns:
            Created DataSource instance.

        Raises:
            SourceExistsError: If source with name already exists.
            AdapterNotFoundError: If source_type is not registered.
            ValidationError: If connection_info is invalid for the adapter.
        """
        if self.repo.exists(name):
            raise SourceExistsError(name)

        if not AdapterRegistry.is_registered(source_type):
            raise AdapterNotFoundError(source_type)

        # Validate against adapter's config schema
        schema = AdapterRegistry.get_config_schema(source_type)
        validated = schema(**connection_info)

        # Store config as dict (with secrets as strings)
        validated_info = validated.model_dump(mode="json")

        source = self.repo.create(
            name=name,
            source_type=source_type,
            connection_info=validated_info,
            display_name=display_name,
        )

        # Flush to populate auto-generated fields (id, created_at, etc.)
        self.repo.flush()

        return source

    def list_sources(self, active_only: bool = False) -> list[DataSource]:
        """List all configured data sources.

        Args:
            active_only: If True, only return active sources.

        Returns:
            List of DataSource instances.
        """
        if active_only:
            return self.repo.get_active()
        return self.repo.get_all()

    def get_source(self, name: str) -> DataSource:
        """Get a data source by name.

        Args:
            name: Name of the source.

        Returns:
            DataSource instance.

        Raises:
            SourceNotFoundError: If source does not exist.
        """
        source = self.repo.get_by_name(name)
        if source is None:
            raise SourceNotFoundError(name)
        return source

    def remove_source(self, name: str) -> None:
        """Remove a data source.

        Args:
            name: Name of the source to remove.

        Raises:
            SourceNotFoundError: If source does not exist.
        """
        source = self.get_source(name)
        self.repo.delete(source)

    def test_source(self, name: str) -> ConnectionTestResult:
        """Test connection to a data source.

        Args:
            name: Name of the source to test.

        Returns:
            ConnectionTestResult with status.

        Raises:
            SourceNotFoundError: If source does not exist.
        """
        source = self.get_source(name)

        async def _test():
            adapter = AdapterRegistry.get_adapter(
                source.source_type,
                source.connection_info,
            )
            start = time.perf_counter()
            try:
                async with adapter:
                    connected = await adapter.test_connection()
                    latency = (time.perf_counter() - start) * 1000
                    return ConnectionTestResult(
                        source_name=name,
                        connected=connected,
                        message="Connection successful" if connected else "Connection test failed",
                        latency_ms=round(latency, 2),
                    )
            except Exception as e:
                return ConnectionTestResult(
                    source_name=name,
                    connected=False,
                    message=str(e),
                    latency_ms=None,
                )

        return asyncio.run(_test())

    def get_available_adapters(self) -> list[dict[str, Any]]:
        """Get information about available adapter types.

        Returns:
            List of adapter info dicts.
        """
        adapters = AdapterRegistry.list_adapters()
        return [
            {
                "type": info.source_type,
                "display_name": info.display_name,
                "object_types": info.supported_object_types,
                "dq_metrics": info.supported_dq_metrics,
            }
            for info in adapters
        ]
