"""PostgreSQL adapter."""

import asyncio
from typing import Any

from datacompass.core.adapters.base import SourceAdapter
from datacompass.core.adapters.exceptions import (
    AdapterAuthenticationError,
    AdapterConnectionError,
    AdapterQueryError,
)
from datacompass.core.adapters.registry import AdapterRegistry
from datacompass.core.adapters.schemas import PostgreSQLConfig


@AdapterRegistry.register(
    source_type="postgresql",
    display_name="PostgreSQL",
    config_schema=PostgreSQLConfig,
)
class PostgreSQLAdapter(SourceAdapter):
    """Adapter for PostgreSQL databases.

    Supports:
    - Standard PostgreSQL metadata via information_schema and pg_catalog
    - TABLE, VIEW, and MATERIALIZED VIEW objects
    - Column metadata including data types, nullability, and defaults
    - Foreign key relationship extraction for lineage
    - View dependency extraction for lineage
    """

    SUPPORTED_OBJECT_TYPES = ["TABLE", "VIEW", "MATERIALIZED VIEW"]
    SUPPORTED_DQ_METRICS = [
        "row_count",
        "distinct_count",
        "null_count",
        "min",
        "max",
        "mean",
        "sum",
    ]

    def __init__(self, config: PostgreSQLConfig) -> None:
        super().__init__(config)
        self.config: PostgreSQLConfig = config
        self._connection: Any = None

    async def connect(self) -> None:
        """Establish connection to PostgreSQL database."""
        try:
            import psycopg
        except ImportError as e:
            raise AdapterConnectionError(
                "psycopg package required. "
                "Install with: pip install datacompass[postgresql] or pip install psycopg[binary]",
                source_type="postgresql",
            ) from e

        try:
            conninfo = (
                f"host={self.config.host} "
                f"port={self.config.port} "
                f"dbname={self.config.database} "
                f"user={self.config.username} "
                f"password={self.config.password.get_secret_value()} "
                f"sslmode={self.config.ssl_mode.value} "
                f"connect_timeout={self.config.connect_timeout}"
            )

            # Run sync connection in thread pool
            def _connect() -> Any:
                return psycopg.connect(conninfo)

            loop = asyncio.get_event_loop()
            self._connection = await loop.run_in_executor(None, _connect)

        except Exception as e:
            error_msg = str(e).lower()
            if "password" in error_msg or "authentication" in error_msg:
                raise AdapterAuthenticationError(
                    f"Authentication failed: {e}",
                    source_type="postgresql",
                ) from e
            if "could not connect" in error_msg or "connection refused" in error_msg:
                raise AdapterConnectionError(
                    f"Failed to connect to PostgreSQL at {self.config.host}:{self.config.port}: {e}",
                    source_type="postgresql",
                ) from e
            raise AdapterConnectionError(
                f"Failed to connect to PostgreSQL: {e}",
                source_type="postgresql",
            ) from e

    async def disconnect(self) -> None:
        """Close the PostgreSQL connection."""
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
                source_type="postgresql",
            )

        def _execute() -> list[dict[str, Any]]:
            with self._connection.cursor() as cursor:
                cursor.execute(query)
                if cursor.description is None:
                    return []
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row, strict=True)) for row in rows]

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _execute)
        except Exception as e:
            raise AdapterQueryError(
                f"Query execution failed: {e}",
                query=query,
                source_type="postgresql",
            ) from e

    def _build_schema_filter(self) -> str:
        """Build SQL WHERE clause for schema filtering."""
        conditions = []

        # Exclude system schemas
        if self.config.exclude_schemas:
            excluded = ", ".join(f"'{s}'" for s in self.config.exclude_schemas)
            conditions.append(f"schema_name NOT IN ({excluded})")

        # Apply regex filter if specified
        if self.config.schema_filter:
            conditions.append(f"schema_name ~ '{self.config.schema_filter}'")

        if conditions:
            return " AND " + " AND ".join(conditions)
        return ""

    def _normalize_object_type(self, pg_type: str) -> str:
        """Map PostgreSQL object types to standard types."""
        mapping = {
            "BASE TABLE": "TABLE",
            "VIEW": "VIEW",
            "MATERIALIZED VIEW": "MATERIALIZED VIEW",
        }
        return mapping.get(pg_type, pg_type)

    async def get_objects(
        self,
        object_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch object metadata from PostgreSQL.

        Uses information_schema and pg_catalog to retrieve tables, views,
        and materialized views.
        """
        types = object_types or self.SUPPORTED_OBJECT_TYPES

        results: list[dict[str, Any]] = []

        # Get tables and views from information_schema
        if "TABLE" in types or "VIEW" in types:
            pg_types = []
            if "TABLE" in types:
                pg_types.append("'BASE TABLE'")
            if "VIEW" in types:
                pg_types.append("'VIEW'")

            type_filter = ", ".join(pg_types)
            schema_filter = self._build_schema_filter().replace("schema_name", "table_schema")

            query = f"""
                SELECT
                    table_schema as schema_name,
                    table_name as object_name,
                    table_type as object_type
                FROM information_schema.tables
                WHERE table_type IN ({type_filter})
                {schema_filter}
                ORDER BY table_schema, table_name
            """

            rows = await self.execute_query(query)

            for row in rows:
                # Get table/view comment
                comment = await self._get_object_comment(
                    row["schema_name"],
                    row["object_name"],
                    "TABLE" if row["object_type"] == "BASE TABLE" else "VIEW",
                )

                results.append({
                    "schema_name": row["schema_name"],
                    "object_name": row["object_name"],
                    "object_type": self._normalize_object_type(row["object_type"]),
                    "source_metadata": {
                        "original_type": row["object_type"],
                        "description": comment,
                    },
                })

        # Get materialized views from pg_catalog
        if "MATERIALIZED VIEW" in types:
            schema_filter = self._build_schema_filter().replace(
                "schema_name", "schemaname"
            )

            query = f"""
                SELECT
                    schemaname as schema_name,
                    matviewname as object_name,
                    'MATERIALIZED VIEW' as object_type
                FROM pg_matviews
                WHERE 1=1
                {schema_filter}
                ORDER BY schemaname, matviewname
            """

            rows = await self.execute_query(query)

            for row in rows:
                comment = await self._get_object_comment(
                    row["schema_name"],
                    row["object_name"],
                    "MATERIALIZED VIEW",
                )

                results.append({
                    "schema_name": row["schema_name"],
                    "object_name": row["object_name"],
                    "object_type": "MATERIALIZED VIEW",
                    "source_metadata": {
                        "original_type": "MATERIALIZED VIEW",
                        "description": comment,
                    },
                })

        return results

    async def _get_object_comment(
        self,
        schema_name: str,
        object_name: str,
        object_type: str,
    ) -> str | None:
        """Get the comment/description for a database object."""
        if object_type == "MATERIALIZED VIEW":
            relkind = "m"
        elif object_type == "VIEW":
            relkind = "v"
        else:
            relkind = "r"

        query = f"""
            SELECT obj_description(c.oid) as comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = '{schema_name}'
              AND c.relname = '{object_name}'
              AND c.relkind = '{relkind}'
        """

        rows = await self.execute_query(query)
        if rows and rows[0].get("comment"):
            return rows[0]["comment"]
        return None

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
                c.table_schema as schema_name,
                c.table_name as object_name,
                c.column_name,
                c.ordinal_position as position,
                c.data_type,
                c.udt_name,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.is_nullable,
                c.column_default,
                pgd.description
            FROM information_schema.columns c
            LEFT JOIN pg_catalog.pg_statio_all_tables st
                ON c.table_schema = st.schemaname
                AND c.table_name = st.relname
            LEFT JOIN pg_catalog.pg_description pgd
                ON pgd.objoid = st.relid
                AND pgd.objsubid = c.ordinal_position
            WHERE {object_filters}
            ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """

        rows = await self.execute_query(query)

        return [
            {
                "schema_name": row["schema_name"],
                "object_name": row["object_name"],
                "column_name": row["column_name"],
                "position": row["position"],
                "source_metadata": {
                    "data_type": self._format_data_type(row),
                    "nullable": row["is_nullable"] == "YES",
                    "default": row.get("column_default"),
                    "description": row.get("description"),
                },
            }
            for row in rows
        ]

    def _format_data_type(self, row: dict[str, Any]) -> str:
        """Format the full data type string including precision/length."""
        base_type = row["data_type"]
        udt_name = row.get("udt_name", "")

        # Use udt_name for user-defined types and arrays
        if base_type == "USER-DEFINED":
            base_type = udt_name
        elif base_type == "ARRAY":
            base_type = f"{udt_name}[]"

        # Add length for character types
        if row.get("character_maximum_length"):
            return f"{base_type}({row['character_maximum_length']})"

        # Add precision/scale for numeric types
        if row.get("numeric_precision"):
            if row.get("numeric_scale"):
                return f"{base_type}({row['numeric_precision']},{row['numeric_scale']})"
            return f"{base_type}({row['numeric_precision']})"

        return base_type

    async def get_columns_with_constraints(
        self,
        objects: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Fetch columns with FK constraints merged into source_metadata.

        Args:
            objects: List of (schema_name, object_name) tuples.

        Returns:
            List of column metadata dicts with FK info in source_metadata.
        """
        columns = await self.get_columns(objects)
        fks = await self.get_foreign_keys()

        # Build lookup: (schema, table, column) -> FK info
        fk_lookup: dict[tuple[str, str, str], dict[str, Any]] = {
            (fk["source_schema"], fk["source_table"], fk["source_column"]): {
                "constraint_name": fk["constraint_name"],
                "references_schema": fk["target_schema"],
                "references_table": fk["target_table"],
                "references_column": fk["target_column"],
            }
            for fk in fks
        }

        # Enrich columns with FK info
        for col in columns:
            key = (col["schema_name"], col["object_name"], col["column_name"])
            if key in fk_lookup:
                if col.get("source_metadata") is None:
                    col["source_metadata"] = {}
                col["source_metadata"]["constraints"] = {"foreign_key": fk_lookup[key]}

        return columns

    async def get_foreign_keys(self) -> list[dict[str, Any]]:
        """Extract foreign key relationships for lineage.

        Uses pg_catalog for reliable access regardless of user permissions.

        Returns:
            List of foreign key relationships with source and target info.
        """
        # Build schema filter for pg_catalog queries
        conditions = []
        if self.config.exclude_schemas:
            excluded = ", ".join(f"'{s}'" for s in self.config.exclude_schemas)
            conditions.append(f"src_ns.nspname NOT IN ({excluded})")
        if self.config.schema_filter:
            conditions.append(f"src_ns.nspname ~ '{self.config.schema_filter}'")

        schema_filter = ""
        if conditions:
            schema_filter = " AND " + " AND ".join(conditions)

        query = f"""
            SELECT
                tc.conname AS constraint_name,
                src_ns.nspname AS source_schema,
                src_tbl.relname AS source_table,
                src_att.attname AS source_column,
                tgt_ns.nspname AS target_schema,
                tgt_tbl.relname AS target_table,
                tgt_att.attname AS target_column
            FROM pg_constraint tc
            JOIN pg_class src_tbl ON tc.conrelid = src_tbl.oid
            JOIN pg_namespace src_ns ON src_tbl.relnamespace = src_ns.oid
            JOIN pg_class tgt_tbl ON tc.confrelid = tgt_tbl.oid
            JOIN pg_namespace tgt_ns ON tgt_tbl.relnamespace = tgt_ns.oid
            JOIN pg_attribute src_att ON src_att.attrelid = src_tbl.oid
                AND src_att.attnum = ANY(tc.conkey)
            JOIN pg_attribute tgt_att ON tgt_att.attrelid = tgt_tbl.oid
                AND tgt_att.attnum = ANY(tc.confkey)
            WHERE tc.contype = 'f'
            {schema_filter}
            ORDER BY src_ns.nspname, src_tbl.relname
        """

        return await self.execute_query(query)

    async def get_view_dependencies(self) -> list[dict[str, Any]]:
        """Extract view dependencies for lineage.

        Uses pg_depend for reliable access regardless of user permissions.

        Returns:
            List of view dependencies showing which tables/views a view depends on.
        """
        # Build schema filter for pg_catalog queries
        conditions = []
        if self.config.exclude_schemas:
            excluded = ", ".join(f"'{s}'" for s in self.config.exclude_schemas)
            conditions.append(f"dependent_ns.nspname NOT IN ({excluded})")
            conditions.append(f"source_ns.nspname NOT IN ({excluded})")
        if self.config.schema_filter:
            conditions.append(f"dependent_ns.nspname ~ '{self.config.schema_filter}'")

        schema_filter = ""
        if conditions:
            schema_filter = " AND " + " AND ".join(conditions)

        query = f"""
            SELECT DISTINCT
                dependent_ns.nspname AS view_schema,
                dependent_view.relname AS view_name,
                source_ns.nspname AS source_schema,
                source_table.relname AS source_table
            FROM pg_depend
            JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid
            JOIN pg_class AS dependent_view ON pg_rewrite.ev_class = dependent_view.oid
            JOIN pg_class AS source_table ON pg_depend.refobjid = source_table.oid
            JOIN pg_namespace dependent_ns ON dependent_ns.oid = dependent_view.relnamespace
            JOIN pg_namespace source_ns ON source_ns.oid = source_table.relnamespace
            WHERE source_table.relname != dependent_view.relname
            {schema_filter}
            ORDER BY dependent_ns.nspname, dependent_view.relname
        """

        return await self.execute_query(query)
