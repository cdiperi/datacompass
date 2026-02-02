"""Databricks Unity Catalog adapter."""

import asyncio
from typing import Any

from datacompass.core.adapters.base import SourceAdapter
from datacompass.core.adapters.exceptions import (
    AdapterAuthenticationError,
    AdapterConnectionError,
    AdapterQueryError,
)
from datacompass.core.adapters.registry import AdapterRegistry
from datacompass.core.adapters.schemas import AuthMethod, DatabricksConfig


@AdapterRegistry.register(
    source_type="databricks",
    display_name="Databricks Unity Catalog",
    config_schema=DatabricksConfig,
)
class DatabricksAdapter(SourceAdapter):
    """Adapter for Databricks Unity Catalog.

    Supports:
    - Unity Catalog metadata via INFORMATION_SCHEMA
    - TABLE, VIEW, and MATERIALIZED_VIEW objects
    - Column metadata including data types and comments
    - Multiple authentication methods (token, service principal, managed identity)
    """

    SUPPORTED_OBJECT_TYPES = ["TABLE", "VIEW", "MATERIALIZED_VIEW"]
    SUPPORTED_DQ_METRICS = [
        "row_count",
        "distinct_count",
        "null_count",
        "min",
        "max",
        "mean",
        "sum",
    ]

    def __init__(self, config: DatabricksConfig) -> None:
        super().__init__(config)
        self.config: DatabricksConfig = config
        self._connection: Any = None

    def _get_access_token(self) -> str:
        """Get access token based on configured auth method."""
        if self.config.auth_method == AuthMethod.PERSONAL_TOKEN:
            if self.config.access_token is None:
                raise AdapterAuthenticationError(
                    "Personal access token not configured",
                    source_type="databricks",
                )
            return self.config.access_token.get_secret_value()

        elif self.config.auth_method == AuthMethod.SERVICE_PRINCIPAL:
            try:
                from azure.identity import ClientSecretCredential
            except ImportError as e:
                raise AdapterAuthenticationError(
                    "azure-identity package required for service principal auth. "
                    "Install with: pip install datacompass[azure]",
                    source_type="databricks",
                ) from e

            if not all([self.config.client_id, self.config.client_secret, self.config.tenant_id]):
                raise AdapterAuthenticationError(
                    "client_id, client_secret, and tenant_id required for service principal auth",
                    source_type="databricks",
                )

            credential = ClientSecretCredential(
                tenant_id=self.config.tenant_id,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret.get_secret_value(),
            )
            # Databricks Azure resource ID
            token = credential.get_token("2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default")
            return token.token

        elif self.config.auth_method == AuthMethod.MANAGED_IDENTITY:
            try:
                from azure.identity import ManagedIdentityCredential
            except ImportError as e:
                raise AdapterAuthenticationError(
                    "azure-identity package required for managed identity auth. "
                    "Install with: pip install datacompass[azure]",
                    source_type="databricks",
                ) from e

            credential = ManagedIdentityCredential()
            token = credential.get_token("2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default")
            return token.token

        else:
            raise AdapterAuthenticationError(
                f"Unsupported auth method: {self.config.auth_method}",
                source_type="databricks",
            )

    async def connect(self) -> None:
        """Establish connection to Databricks SQL warehouse."""
        try:
            from databricks import sql as databricks_sql
        except ImportError as e:
            raise AdapterConnectionError(
                "databricks-sql-connector package required. "
                "Install with: pip install datacompass[databricks] or pip install databricks-sql-connector",
                source_type="databricks",
            ) from e

        try:
            access_token = self._get_access_token()

            # Run sync connection in thread pool
            def _connect():
                return databricks_sql.connect(
                    server_hostname=self.config.host,
                    http_path=self.config.http_path,
                    access_token=access_token,
                )

            loop = asyncio.get_event_loop()
            self._connection = await loop.run_in_executor(None, _connect)

        except Exception as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise AdapterAuthenticationError(
                    f"Authentication failed: {e}",
                    source_type="databricks",
                ) from e
            raise AdapterConnectionError(
                f"Failed to connect to Databricks: {e}",
                source_type="databricks",
            ) from e

    async def disconnect(self) -> None:
        """Close the Databricks connection."""
        if self._connection is not None:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._connection.close)
            finally:
                self._connection = None

    async def test_connection(self) -> bool:
        """Test connection by running a simple query."""
        try:
            await self.execute_query("SELECT 1 as test")
            return True
        except Exception:
            return False

    async def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts."""
        if self._connection is None:
            raise AdapterConnectionError(
                "Not connected. Call connect() first.",
                source_type="databricks",
            )

        def _execute():
            cursor = self._connection.cursor()
            try:
                cursor.execute(query)
                if cursor.description is None:
                    return []
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row, strict=True)) for row in rows]
            finally:
                cursor.close()

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _execute)
        except Exception as e:
            raise AdapterQueryError(
                f"Query execution failed: {e}",
                query=query,
                source_type="databricks",
            ) from e

    def _normalize_object_type(self, databricks_type: str) -> str:
        """Map Databricks table types to standard types."""
        mapping = {
            "MANAGED": "TABLE",
            "EXTERNAL": "TABLE",
            "VIEW": "VIEW",
            "MATERIALIZED_VIEW": "MATERIALIZED_VIEW",
        }
        return mapping.get(databricks_type, databricks_type)

    async def get_objects(
        self,
        object_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch object metadata from Unity Catalog.

        Uses INFORMATION_SCHEMA.TABLES to retrieve tables and views.
        """
        types = object_types or self.SUPPORTED_OBJECT_TYPES

        # Build type filter - handle both standard and Databricks-specific types
        # INFORMATION_SCHEMA uses MANAGED/EXTERNAL for tables
        db_types = set()
        for t in types:
            if t == "TABLE":
                db_types.update(["MANAGED", "EXTERNAL"])
            else:
                db_types.add(t)

        type_filter = ", ".join(f"'{t}'" for t in db_types)

        query = f"""
            SELECT
                table_schema as schema_name,
                table_name as object_name,
                table_type as object_type,
                created as created_at,
                last_altered as updated_at,
                comment as description
            FROM {self.config.catalog}.information_schema.tables
            WHERE table_type IN ({type_filter})
        """

        if self.config.schema_filter:
            query += f" AND table_schema RLIKE '{self.config.schema_filter}'"

        query += " ORDER BY table_schema, table_name"

        rows = await self.execute_query(query)

        return [
            {
                "schema_name": row["schema_name"],
                "object_name": row["object_name"],
                "object_type": self._normalize_object_type(row["object_type"]),
                "source_metadata": {
                    "original_type": row["object_type"],
                    "created_at": str(row["created_at"]) if row.get("created_at") else None,
                    "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
                    "description": row.get("description"),
                },
            }
            for row in rows
        ]

    async def get_columns(
        self,
        objects: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Fetch column metadata for specified objects.

        Args:
            objects: List of (schema_name, object_name) tuples.

        Returns:
            List of column metadata dicts.
        """
        if not objects:
            return []

        # Build filter for specific objects
        object_filters = " OR ".join(
            f"(table_schema = '{schema}' AND table_name = '{name}')"
            for schema, name in objects
        )

        query = f"""
            SELECT
                table_schema as schema_name,
                table_name as object_name,
                column_name,
                ordinal_position as position,
                data_type,
                is_nullable,
                column_default,
                comment as description
            FROM {self.config.catalog}.information_schema.columns
            WHERE {object_filters}
            ORDER BY table_schema, table_name, ordinal_position
        """

        rows = await self.execute_query(query)

        return [
            {
                "schema_name": row["schema_name"],
                "object_name": row["object_name"],
                "column_name": row["column_name"],
                "position": row["position"],
                "source_metadata": {
                    "data_type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                    "default": row.get("column_default"),
                    "description": row.get("description"),
                },
            }
            for row in rows
        ]
