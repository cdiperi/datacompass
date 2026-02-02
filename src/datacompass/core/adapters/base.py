"""Base adapter interface for data sources."""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel


class SourceAdapter(ABC):
    """Abstract base class for data source adapters.

    Adapters provide a uniform interface for interacting with different
    data sources (Databricks, Snowflake, PostgreSQL, etc.).

    All adapters must implement async methods for connection management
    and data retrieval. The async interface allows efficient concurrent
    operations when scanning multiple sources.
    """

    # Class-level constants - override in subclasses
    SUPPORTED_OBJECT_TYPES: ClassVar[list[str]] = []
    SUPPORTED_DQ_METRICS: ClassVar[list[str]] = []

    def __init__(self, config: BaseModel) -> None:
        """Initialize adapter with validated configuration.

        Args:
            config: Pydantic model with connection configuration.
        """
        self.config = config
        self._connection: Any = None

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source.

        Raises:
            AdapterConnectionError: If connection cannot be established.
            AdapterAuthenticationError: If authentication fails.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and release resources."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connection is valid.

        Returns:
            True if connection is successful, False otherwise.
        """
        pass

    @abstractmethod
    async def get_objects(
        self,
        object_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch metadata for database objects.

        Args:
            object_types: Filter by object types (TABLE, VIEW, etc.).
                         If None, returns all supported types.

        Returns:
            List of dicts with keys:
                - schema_name: str
                - object_name: str
                - object_type: str (TABLE, VIEW, etc.)
                - source_metadata: dict (created_at, updated_at, description, etc.)
        """
        pass

    @abstractmethod
    async def get_columns(
        self,
        objects: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Fetch column metadata for specified objects.

        Args:
            objects: List of (schema_name, object_name) tuples.

        Returns:
            List of dicts with keys:
                - schema_name: str
                - object_name: str
                - column_name: str
                - position: int
                - source_metadata: dict (data_type, nullable, default, description, etc.)
        """
        pass

    @abstractmethod
    async def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute an arbitrary SQL query.

        Args:
            query: SQL query string.

        Returns:
            List of result rows as dicts.

        Raises:
            AdapterQueryError: If query execution fails.
        """
        pass

    async def __aenter__(self) -> "SourceAdapter":
        """Async context manager entry - establish connection."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - close connection."""
        await self.disconnect()
