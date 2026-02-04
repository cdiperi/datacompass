"""Snowflake adapter."""

import asyncio
from typing import Any

from datacompass.core.adapters.base import SourceAdapter
from datacompass.core.adapters.exceptions import (
    AdapterAuthenticationError,
    AdapterConnectionError,
    AdapterQueryError,
)
from datacompass.core.adapters.registry import AdapterRegistry
from datacompass.core.adapters.schemas import SnowflakeConfig


@AdapterRegistry.register(
    source_type="snowflake",
    display_name="Snowflake",
    config_schema=SnowflakeConfig,
)
class SnowflakeAdapter(SourceAdapter):
    """Adapter for Snowflake data warehouse.

    Supports:
    - Standard Snowflake metadata via INFORMATION_SCHEMA
    - TABLE, VIEW, MATERIALIZED VIEW, and DYNAMIC TABLE objects
    - Column metadata including data types, nullability, and comments
    - Usage metrics from ACCOUNT_USAGE views (requires appropriate permissions)
    """

    SUPPORTED_OBJECT_TYPES = ["TABLE", "VIEW", "MATERIALIZED VIEW", "DYNAMIC TABLE"]
    SUPPORTED_DQ_METRICS = [
        "row_count",
        "distinct_count",
        "null_count",
        "min",
        "max",
        "mean",
        "sum",
    ]

    def __init__(self, config: SnowflakeConfig) -> None:
        super().__init__(config)
        self.config: SnowflakeConfig = config
        self._connection: Any = None

    async def connect(self) -> None:
        """Establish connection to Snowflake."""
        try:
            import snowflake.connector
        except ImportError as e:
            raise AdapterConnectionError(
                "snowflake-connector-python package required. "
                "Install with: pip install datacompass[snowflake] or pip install snowflake-connector-python",
                source_type="snowflake",
            ) from e

        try:
            connect_params: dict[str, Any] = {
                "account": self.config.account,
                "user": self.config.username,
                "password": self.config.password.get_secret_value(),
                "warehouse": self.config.warehouse,
                "database": self.config.database,
                "login_timeout": self.config.connect_timeout,
                "network_timeout": self.config.query_timeout,
            }

            if self.config.role:
                connect_params["role"] = self.config.role

            # Run sync connection in thread pool
            def _connect() -> Any:
                return snowflake.connector.connect(**connect_params)

            loop = asyncio.get_event_loop()
            self._connection = await loop.run_in_executor(None, _connect)

        except Exception as e:
            error_msg = str(e).lower()
            if "incorrect username or password" in error_msg or "authentication" in error_msg:
                raise AdapterAuthenticationError(
                    f"Authentication failed: {e}",
                    source_type="snowflake",
                ) from e
            if "could not connect" in error_msg or "connection refused" in error_msg:
                raise AdapterConnectionError(
                    f"Failed to connect to Snowflake account {self.config.account}: {e}",
                    source_type="snowflake",
                ) from e
            raise AdapterConnectionError(
                f"Failed to connect to Snowflake: {e}",
                source_type="snowflake",
            ) from e

    async def disconnect(self) -> None:
        """Close the Snowflake connection."""
        if self._connection is not None:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._connection.close)
            finally:
                self._connection = None

    async def test_connection(self) -> bool:
        """Test connection by running a simple query."""
        try:
            await self.execute_query("SELECT 1 AS test")
            return True
        except Exception:
            return False

    async def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts."""
        if self._connection is None:
            raise AdapterConnectionError(
                "Not connected. Call connect() first.",
                source_type="snowflake",
            )

        def _execute() -> list[dict[str, Any]]:
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
                source_type="snowflake",
            ) from e

    def _build_schema_filter(self, schema_column: str = "TABLE_SCHEMA") -> str:
        """Build SQL WHERE clause for schema filtering."""
        conditions = []

        # Exclude system schemas
        if self.config.exclude_schemas:
            excluded = ", ".join(f"'{s}'" for s in self.config.exclude_schemas)
            conditions.append(f"{schema_column} NOT IN ({excluded})")

        # Apply regex filter if specified (Snowflake uses RLIKE for regex)
        if self.config.schema_filter:
            conditions.append(f"{schema_column} RLIKE '{self.config.schema_filter}'")

        if conditions:
            return " AND " + " AND ".join(conditions)
        return ""

    def _normalize_object_type(self, snowflake_type: str) -> str:
        """Map Snowflake object types to standard types."""
        mapping = {
            "BASE TABLE": "TABLE",
            "TABLE": "TABLE",
            "VIEW": "VIEW",
            "MATERIALIZED VIEW": "MATERIALIZED VIEW",
            "DYNAMIC TABLE": "DYNAMIC TABLE",
        }
        return mapping.get(snowflake_type, snowflake_type)

    async def get_objects(
        self,
        object_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch object metadata from Snowflake.

        Uses INFORMATION_SCHEMA.TABLES to retrieve tables and views.
        """
        types = object_types or self.SUPPORTED_OBJECT_TYPES

        # Map standard types to Snowflake INFORMATION_SCHEMA types
        sf_types = set()
        for t in types:
            if t == "TABLE":
                sf_types.add("BASE TABLE")
            else:
                sf_types.add(t)

        type_filter = ", ".join(f"'{t}'" for t in sf_types)
        schema_filter = self._build_schema_filter()

        query = f"""
            SELECT
                TABLE_SCHEMA AS schema_name,
                TABLE_NAME AS object_name,
                TABLE_TYPE AS object_type,
                CREATED AS created_at,
                LAST_ALTERED AS updated_at,
                COMMENT AS description,
                ROW_COUNT AS row_count,
                BYTES AS size_bytes
            FROM {self.config.database}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_CATALOG = '{self.config.database}'
              AND TABLE_TYPE IN ({type_filter})
              {schema_filter}
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """

        rows = await self.execute_query(query)

        return [
            {
                "schema_name": row["SCHEMA_NAME"],
                "object_name": row["OBJECT_NAME"],
                "object_type": self._normalize_object_type(row["OBJECT_TYPE"]),
                "source_metadata": {
                    "original_type": row["OBJECT_TYPE"],
                    "created_at": str(row["CREATED_AT"]) if row.get("CREATED_AT") else None,
                    "updated_at": str(row["UPDATED_AT"]) if row.get("UPDATED_AT") else None,
                    "description": row.get("DESCRIPTION"),
                    "row_count": row.get("ROW_COUNT"),
                    "size_bytes": row.get("SIZE_BYTES"),
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
            f"(TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{name}')"
            for schema, name in objects
        )

        query = f"""
            SELECT
                TABLE_SCHEMA AS schema_name,
                TABLE_NAME AS object_name,
                COLUMN_NAME AS column_name,
                ORDINAL_POSITION AS position,
                DATA_TYPE AS data_type,
                IS_NULLABLE AS is_nullable,
                COLUMN_DEFAULT AS column_default,
                COMMENT AS description,
                CHARACTER_MAXIMUM_LENGTH AS char_max_length,
                NUMERIC_PRECISION AS numeric_precision,
                NUMERIC_SCALE AS numeric_scale
            FROM {self.config.database}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_CATALOG = '{self.config.database}'
              AND ({object_filters})
            ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
        """

        rows = await self.execute_query(query)

        return [
            {
                "schema_name": row["SCHEMA_NAME"],
                "object_name": row["OBJECT_NAME"],
                "column_name": row["COLUMN_NAME"],
                "position": row["POSITION"],
                "source_metadata": {
                    "data_type": self._format_data_type(row),
                    "nullable": row["IS_NULLABLE"] == "YES",
                    "default": row.get("COLUMN_DEFAULT"),
                    "description": row.get("DESCRIPTION"),
                },
            }
            for row in rows
        ]

    def _format_data_type(self, row: dict[str, Any]) -> str:
        """Format the full data type string including precision/length."""
        base_type = row["DATA_TYPE"]

        # Add length for character types
        if row.get("CHAR_MAX_LENGTH"):
            return f"{base_type}({row['CHAR_MAX_LENGTH']})"

        # Add precision/scale for numeric types
        if row.get("NUMERIC_PRECISION"):
            if row.get("NUMERIC_SCALE"):
                return f"{base_type}({row['NUMERIC_PRECISION']},{row['NUMERIC_SCALE']})"
            return f"{base_type}({row['NUMERIC_PRECISION']})"

        return base_type

    async def get_usage_metrics(
        self,
        objects: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Fetch usage metrics for Snowflake objects.

        Uses SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS for storage metrics.
        Note: Requires ACCOUNTADMIN role or appropriate privileges.

        Args:
            objects: List of (schema_name, object_name) tuples.

        Returns:
            List of usage metric dicts.
        """
        if not objects:
            return []

        # Build filter for specific objects
        object_filters = " OR ".join(
            f"(TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{name}')"
            for schema, name in objects
        )

        # Try to get metrics from ACCOUNT_USAGE - this may fail without proper permissions
        try:
            query = f"""
                SELECT
                    TABLE_SCHEMA AS schema_name,
                    TABLE_NAME AS object_name,
                    ACTIVE_BYTES AS size_bytes,
                    ROW_COUNT AS row_count,
                    CLONE_GROUP_ID,
                    IS_TRANSIENT,
                    DELETED
                FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
                WHERE TABLE_CATALOG = '{self.config.database}'
                  AND ({object_filters})
                  AND DELETED IS NULL
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY TABLE_SCHEMA, TABLE_NAME
                    ORDER BY ID DESC
                ) = 1
            """

            rows = await self.execute_query(query)

            return [
                {
                    "schema_name": row["SCHEMA_NAME"],
                    "object_name": row["OBJECT_NAME"],
                    "row_count": row.get("ROW_COUNT"),
                    "size_bytes": row.get("SIZE_BYTES"),
                    "read_count": None,  # Not available in this view
                    "write_count": None,
                    "last_read_at": None,
                    "last_written_at": None,
                    "distinct_users": None,
                    "query_count": None,
                    "source_metrics": {
                        "clone_group_id": row.get("CLONE_GROUP_ID"),
                        "is_transient": row.get("IS_TRANSIENT"),
                    },
                }
                for row in rows
            ]

        except AdapterQueryError:
            # Fall back to basic metrics from INFORMATION_SCHEMA if ACCOUNT_USAGE is not accessible
            fallback_query = f"""
                SELECT
                    TABLE_SCHEMA AS schema_name,
                    TABLE_NAME AS object_name,
                    ROW_COUNT AS row_count,
                    BYTES AS size_bytes
                FROM {self.config.database}.INFORMATION_SCHEMA.TABLES
                WHERE TABLE_CATALOG = '{self.config.database}'
                  AND ({object_filters})
            """

            try:
                rows = await self.execute_query(fallback_query)
                return [
                    {
                        "schema_name": row["SCHEMA_NAME"],
                        "object_name": row["OBJECT_NAME"],
                        "row_count": row.get("ROW_COUNT"),
                        "size_bytes": row.get("SIZE_BYTES"),
                        "read_count": None,
                        "write_count": None,
                        "last_read_at": None,
                        "last_written_at": None,
                        "distinct_users": None,
                        "query_count": None,
                        "source_metrics": None,
                    }
                    for row in rows
                ]
            except AdapterQueryError:
                return []

    async def get_foreign_keys(self) -> list[dict[str, Any]]:
        """Extract foreign key relationships for lineage.

        Uses INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS and TABLE_CONSTRAINTS.
        Note: Snowflake FK constraints are not enforced but can store metadata.

        Returns:
            List of foreign key relationships with source and target info.
        """
        schema_filter = self._build_schema_filter("tc.TABLE_SCHEMA")

        query = f"""
            SELECT
                tc.CONSTRAINT_NAME AS constraint_name,
                tc.TABLE_SCHEMA AS source_schema,
                tc.TABLE_NAME AS source_table,
                kcu.COLUMN_NAME AS source_column,
                rc.UNIQUE_CONSTRAINT_SCHEMA AS target_schema,
                ccu.TABLE_NAME AS target_table,
                ccu.COLUMN_NAME AS target_column
            FROM {self.config.database}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN {self.config.database}.INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                ON tc.CONSTRAINT_CATALOG = rc.CONSTRAINT_CATALOG
                AND tc.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
                AND tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            JOIN {self.config.database}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_CATALOG = kcu.CONSTRAINT_CATALOG
                AND tc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA
                AND tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN {self.config.database}.INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_CATALOG = ccu.CONSTRAINT_CATALOG
                AND rc.UNIQUE_CONSTRAINT_SCHEMA = ccu.CONSTRAINT_SCHEMA
                AND rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
              AND tc.TABLE_CATALOG = '{self.config.database}'
              {schema_filter}
            ORDER BY tc.TABLE_SCHEMA, tc.TABLE_NAME
        """

        try:
            rows = await self.execute_query(query)
            return [
                {
                    "constraint_name": row["CONSTRAINT_NAME"],
                    "source_schema": row["SOURCE_SCHEMA"],
                    "source_table": row["SOURCE_TABLE"],
                    "source_column": row["SOURCE_COLUMN"],
                    "target_schema": row["TARGET_SCHEMA"],
                    "target_table": row["TARGET_TABLE"],
                    "target_column": row["TARGET_COLUMN"],
                }
                for row in rows
            ]
        except AdapterQueryError:
            # FK metadata may not be available
            return []

    async def get_view_dependencies(self) -> list[dict[str, Any]]:
        """Extract view dependencies for lineage.

        Uses INFORMATION_SCHEMA.VIEW_TABLE_USAGE to find tables/views
        referenced by views.

        Returns:
            List of view dependencies showing which tables/views a view depends on.
        """
        schema_filter = self._build_schema_filter("VIEW_SCHEMA")

        query = f"""
            SELECT DISTINCT
                VIEW_SCHEMA AS view_schema,
                VIEW_NAME AS view_name,
                TABLE_SCHEMA AS source_schema,
                TABLE_NAME AS source_table
            FROM {self.config.database}.INFORMATION_SCHEMA.VIEW_TABLE_USAGE
            WHERE VIEW_CATALOG = '{self.config.database}'
              AND TABLE_CATALOG = '{self.config.database}'
              {schema_filter}
            ORDER BY VIEW_SCHEMA, VIEW_NAME, TABLE_SCHEMA, TABLE_NAME
        """

        try:
            rows = await self.execute_query(query)
            return [
                {
                    "view_schema": row["VIEW_SCHEMA"],
                    "view_name": row["VIEW_NAME"],
                    "source_schema": row["SOURCE_SCHEMA"],
                    "source_table": row["SOURCE_TABLE"],
                }
                for row in rows
            ]
        except AdapterQueryError:
            # View dependencies may not be available
            return []
