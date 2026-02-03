# Data Compass - Adapter Implementation Guide

This guide explains how to implement data source adapters for Data Compass. Adapters are the plugin system that allows connecting to different database types.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    MetadataSyncService                      │
│         (Orchestrates sync, source-agnostic)                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   AdapterRegistry                           │
│            get_adapter(source_type) → Adapter               │
│            list_adapters() → [AdapterInfo]                  │
│            get_config_schema(source_type) → Schema          │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │Databricks │   │ Snowflake │   │ PostgreSQL│
    │  Adapter  │   │  Adapter  │   │  Adapter  │
    └───────────┘   └───────────┘   └───────────┘
```

---

## Adapter Registry

The registry is the plugin system that discovers and instantiates adapters:

```python
# core/adapters/registry.py
from typing import Type
from dataclasses import dataclass

@dataclass
class AdapterInfo:
    """Metadata about a registered adapter."""
    source_type: str           # "databricks", "snowflake", etc.
    display_name: str          # "Databricks Unity Catalog"
    adapter_class: Type[SourceAdapter]
    config_schema: Type[BaseModel]  # Pydantic schema for validation
    supported_object_types: list[str]
    supported_dq_metrics: list[str]


class AdapterRegistry:
    """Registry for data source adapters."""

    _adapters: dict[str, AdapterInfo] = {}

    @classmethod
    def register(cls, source_type: str, display_name: str, config_schema: Type[BaseModel]):
        """Decorator to register an adapter class."""
        def decorator(adapter_class: Type[SourceAdapter]):
            cls._adapters[source_type] = AdapterInfo(
                source_type=source_type,
                display_name=display_name,
                adapter_class=adapter_class,
                config_schema=config_schema,
                supported_object_types=adapter_class.SUPPORTED_OBJECT_TYPES,
                supported_dq_metrics=adapter_class.SUPPORTED_DQ_METRICS,
            )
            return adapter_class
        return decorator

    @classmethod
    def get_adapter(cls, source_type: str, config: dict) -> SourceAdapter:
        """Instantiate an adapter by type."""
        if source_type not in cls._adapters:
            raise ValueError(f"Unknown adapter type: {source_type}. "
                           f"Available: {list(cls._adapters.keys())}")

        info = cls._adapters[source_type]
        # Validate config against schema
        validated_config = info.config_schema(**config)
        return info.adapter_class(validated_config)

    @classmethod
    def list_adapters(cls) -> list[AdapterInfo]:
        """List all registered adapters."""
        return list(cls._adapters.values())

    @classmethod
    def get_config_schema(cls, source_type: str) -> Type[BaseModel]:
        """Get the config schema for an adapter type."""
        return cls._adapters[source_type].config_schema
```

---

## Adapter Interface

All adapters implement this base class:

```python
# core/adapters/base.py
from abc import ABC, abstractmethod
from typing import ClassVar

class SourceAdapter(ABC):
    """Base class for data source adapters."""

    # Class-level constants - override in subclasses
    SUPPORTED_OBJECT_TYPES: ClassVar[list[str]] = []
    SUPPORTED_DQ_METRICS: ClassVar[list[str]] = []

    def __init__(self, config: BaseModel):
        """Initialize with validated config."""
        self.config = config
        self._connection = None

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to data source. Raises on failure."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and clean up resources."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if connection is valid. Returns True/False."""
        pass

    @abstractmethod
    async def get_objects(self, object_types: list[str] | None = None) -> list[dict]:
        """
        Fetch object metadata.

        Returns list of dicts with keys:
        - schema_name: str
        - object_name: str
        - object_type: str (TABLE, VIEW, etc.)
        - source_metadata: dict (row_count, size_bytes, created_at, etc.)
        """
        pass

    @abstractmethod
    async def get_columns(self, objects: list[tuple[str, str]]) -> list[dict]:
        """
        Fetch column metadata for specified objects.

        Args:
            objects: List of (schema_name, object_name) tuples

        Returns list of dicts with keys:
        - schema_name: str
        - object_name: str
        - column_name: str
        - position: int
        - source_metadata: dict (data_type, nullable, precision, scale, etc.)
        """
        pass

    @abstractmethod
    async def get_dependencies(self) -> list[dict]:
        """
        Fetch dependency/lineage information.

        Returns list of dicts with keys:
        - source_schema: str
        - source_object: str
        - target_schema: str
        - target_object: str
        - dependency_type: str (DIRECT, INDIRECT)
        """
        pass

    @abstractmethod
    async def execute_query(self, query: str) -> list[dict]:
        """Execute arbitrary SQL and return results as list of dicts."""
        pass

    async def execute_dq_query(self, query: DQQuery) -> list[dict]:
        """
        Execute a data quality metric query.
        Default implementation builds SQL from DQQuery.
        Override for non-SQL sources.
        """
        sql = self._build_dq_sql(query)
        return await self.execute_query(sql)

    def _build_dq_sql(self, query: DQQuery) -> str:
        """Build SQL for DQ metrics. Override for dialect differences."""
        # Default ANSI SQL implementation
        metrics_sql = ", ".join(
            f"{m.aggregation}({m.column or '*'}) as {m.alias}"
            for m in query.metrics
        )
        return f"""
            SELECT {query.date_column} as snapshot_date, {metrics_sql}
            FROM {query.object_name}
            WHERE {query.date_column} >= '{query.start_date}'
              AND {query.date_column} <= '{query.end_date}'
            GROUP BY {query.date_column}
        """
```

---

## Connection Configuration Schemas

Each adapter defines its own Pydantic config schema for validation:

```python
# core/adapters/schemas.py
from pydantic import BaseModel, Field, SecretStr
from typing import Literal
from enum import Enum

class AuthMethod(str, Enum):
    """Authentication methods for cloud sources."""
    SERVICE_PRINCIPAL = "service_principal"
    MANAGED_IDENTITY = "managed_identity"
    PERSONAL_TOKEN = "personal_token"
    OAUTH = "oauth"
    USERNAME_PASSWORD = "username_password"
```

### Databricks

```python
class DatabricksConfig(BaseModel):
    """Configuration for Databricks Unity Catalog."""

    # Connection
    host: str = Field(..., description="Databricks workspace URL (e.g., adb-xxx.azuredatabricks.net)")
    http_path: str = Field(..., description="SQL warehouse HTTP path")
    catalog: str = Field(..., description="Unity Catalog name")
    schema_filter: str | None = Field(None, description="Schema pattern to include (regex)")

    # Authentication (choose one)
    auth_method: AuthMethod = Field(default=AuthMethod.PERSONAL_TOKEN)

    # For personal token
    access_token: SecretStr | None = Field(None, description="Personal access token")

    # For service principal (Azure)
    client_id: str | None = Field(None, description="Azure AD app client ID")
    client_secret: SecretStr | None = Field(None, description="Azure AD app client secret")
    tenant_id: str | None = Field(None, description="Azure AD tenant ID")

    # For managed identity
    use_managed_identity: bool = Field(False, description="Use Azure managed identity")

    # Options
    timeout_seconds: int = Field(300, description="Query timeout")
    max_retries: int = Field(3, description="Max retry attempts")
```

### Snowflake

```python
class SnowflakeConfig(BaseModel):
    """Configuration for Snowflake."""

    # Connection
    account: str = Field(..., description="Snowflake account identifier")
    warehouse: str = Field(..., description="Warehouse name")
    database: str = Field(..., description="Database name")
    schema_filter: str | None = Field(None, description="Schema pattern to include (regex)")
    role: str | None = Field(None, description="Role to use")

    # Authentication
    auth_method: AuthMethod = Field(default=AuthMethod.USERNAME_PASSWORD)

    # For username/password
    user: str | None = Field(None)
    password: SecretStr | None = Field(None)

    # For key-pair auth
    private_key_path: str | None = Field(None, description="Path to private key file")
    private_key_passphrase: SecretStr | None = Field(None)

    # For OAuth
    oauth_token: SecretStr | None = Field(None)

    # Options
    timeout_seconds: int = Field(300)
```

### PostgreSQL / Azure SQL

```python
class PostgreSQLConfig(BaseModel):
    """Configuration for PostgreSQL or Azure SQL."""

    host: str = Field(..., description="Database host")
    port: int = Field(5432, description="Database port")
    database: str = Field(..., description="Database name")
    schema_filter: str | None = Field(None, description="Schema pattern (regex)")

    # Authentication
    auth_method: AuthMethod = Field(default=AuthMethod.USERNAME_PASSWORD)
    user: str | None = Field(None)
    password: SecretStr | None = Field(None)

    # For Azure AD auth
    use_azure_ad: bool = Field(False)
    client_id: str | None = Field(None)
    client_secret: SecretStr | None = Field(None)
    tenant_id: str | None = Field(None)

    # SSL
    ssl_mode: Literal["disable", "require", "verify-ca", "verify-full"] = Field("require")
    ssl_cert_path: str | None = Field(None)

    # Options
    connect_timeout: int = Field(30)
```

### BigQuery

```python
class BigQueryConfig(BaseModel):
    """Configuration for Google BigQuery."""

    project_id: str = Field(..., description="GCP project ID")
    dataset_filter: str | None = Field(None, description="Dataset pattern (regex)")
    location: str | None = Field(None, description="Dataset location (US, EU, etc.)")

    # Authentication
    auth_method: AuthMethod = Field(default=AuthMethod.SERVICE_PRINCIPAL)
    credentials_path: str | None = Field(None, description="Path to service account JSON")
    credentials_json: SecretStr | None = Field(None, description="Service account JSON as string")
    use_default_credentials: bool = Field(False, description="Use ADC (gcloud auth)")

    # Options
    timeout_seconds: int = Field(300)
```

---

## Complete Example: Databricks Adapter

```python
# core/adapters/databricks.py
from databricks import sql as databricks_sql
from databricks.sdk import WorkspaceClient
from azure.identity import ClientSecretCredential, ManagedIdentityCredential

from .base import SourceAdapter
from .registry import AdapterRegistry
from .schemas import DatabricksConfig, AuthMethod


@AdapterRegistry.register(
    source_type="databricks",
    display_name="Databricks Unity Catalog",
    config_schema=DatabricksConfig,
)
class DatabricksAdapter(SourceAdapter):
    """Adapter for Databricks Unity Catalog."""

    SUPPORTED_OBJECT_TYPES = ["TABLE", "VIEW", "MATERIALIZED_VIEW", "FUNCTION"]
    SUPPORTED_DQ_METRICS = ["row_count", "distinct_count", "null_count", "min", "max", "mean", "sum"]

    def __init__(self, config: DatabricksConfig):
        super().__init__(config)
        self.config: DatabricksConfig = config
        self._connection = None
        self._workspace_client = None

    async def connect(self) -> None:
        """Establish connection to Databricks."""
        access_token = self._get_access_token()

        self._connection = databricks_sql.connect(
            server_hostname=self.config.host,
            http_path=self.config.http_path,
            access_token=access_token,
        )

        # Also create workspace client for Unity Catalog API
        self._workspace_client = WorkspaceClient(
            host=f"https://{self.config.host}",
            token=access_token,
        )

    def _get_access_token(self) -> str:
        """Get access token based on auth method."""
        match self.config.auth_method:
            case AuthMethod.PERSONAL_TOKEN:
                return self.config.access_token.get_secret_value()

            case AuthMethod.SERVICE_PRINCIPAL:
                credential = ClientSecretCredential(
                    tenant_id=self.config.tenant_id,
                    client_id=self.config.client_id,
                    client_secret=self.config.client_secret.get_secret_value(),
                )
                token = credential.get_token("2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default")
                return token.token

            case AuthMethod.MANAGED_IDENTITY:
                credential = ManagedIdentityCredential()
                token = credential.get_token("2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default")
                return token.token

            case _:
                raise ValueError(f"Unsupported auth method: {self.config.auth_method}")

    async def disconnect(self) -> None:
        """Close connections."""
        if self._connection:
            self._connection.close()
            self._connection = None

    async def test_connection(self) -> bool:
        """Test connection by running simple query."""
        try:
            await self.execute_query("SELECT 1")
            return True
        except Exception:
            return False

    async def get_objects(self, object_types: list[str] | None = None) -> list[dict]:
        """Fetch objects from Unity Catalog."""
        types = object_types or self.SUPPORTED_OBJECT_TYPES

        # Use INFORMATION_SCHEMA for tables/views
        type_filter = ", ".join(f"'{t}'" for t in types)

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

        rows = await self.execute_query(query)

        return [
            {
                "schema_name": row["schema_name"],
                "object_name": row["object_name"],
                "object_type": self._normalize_object_type(row["object_type"]),
                "source_metadata": {
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "description": row.get("description"),
                },
            }
            for row in rows
        ]

    def _normalize_object_type(self, databricks_type: str) -> str:
        """Map Databricks types to standard types."""
        mapping = {
            "MANAGED": "TABLE",
            "EXTERNAL": "TABLE",
            "VIEW": "VIEW",
            "MATERIALIZED_VIEW": "MATERIALIZED_VIEW",
        }
        return mapping.get(databricks_type, databricks_type)

    async def get_columns(self, objects: list[tuple[str, str]]) -> list[dict]:
        """Fetch column metadata."""
        if not objects:
            return []

        # Build filter for specific objects
        object_filter = " OR ".join(
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
            WHERE {object_filter}
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

    async def get_dependencies(self) -> list[dict]:
        """
        Fetch lineage from Unity Catalog.
        Uses the Lineage API via workspace client.
        """
        dependencies = []

        # Get all tables first
        objects = await self.get_objects(["TABLE", "VIEW"])

        for obj in objects:
            full_name = f"{self.config.catalog}.{obj['schema_name']}.{obj['object_name']}"

            try:
                # Use Unity Catalog Lineage API
                lineage = self._workspace_client.lineage.get_table_lineage(
                    table_name=full_name
                )

                for upstream in lineage.upstreams or []:
                    dependencies.append({
                        "source_schema": obj["schema_name"],
                        "source_object": obj["object_name"],
                        "target_schema": upstream.table_info.schema_name,
                        "target_object": upstream.table_info.name,
                        "dependency_type": "DIRECT",
                    })

            except Exception:
                # Lineage not available for this object
                continue

        return dependencies

    async def execute_query(self, query: str) -> list[dict]:
        """Execute SQL query."""
        cursor = self._connection.cursor()
        try:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cursor.close()
```

---

## Adding a New Adapter

To add support for a new data source:

### Step 1: Create Config Schema

```python
# core/adapters/schemas.py
class MySourceConfig(BaseModel):
    host: str = Field(..., description="Server hostname")
    port: int = Field(5432, description="Server port")
    database: str = Field(..., description="Database name")
    user: str | None = Field(None)
    password: SecretStr | None = Field(None)
    # Add source-specific fields...
```

### Step 2: Create Adapter Class

```python
# core/adapters/my_source.py
@AdapterRegistry.register(
    source_type="my_source",
    display_name="My Source",
    config_schema=MySourceConfig,
)
class MySourceAdapter(SourceAdapter):
    SUPPORTED_OBJECT_TYPES = ["TABLE", "VIEW"]
    SUPPORTED_DQ_METRICS = ["row_count", "null_count", "distinct_count"]

    async def connect(self) -> None:
        # Implementation
        pass

    async def disconnect(self) -> None:
        # Implementation
        pass

    async def test_connection(self) -> bool:
        # Implementation
        pass

    async def get_objects(self, object_types: list[str] | None = None) -> list[dict]:
        # Implementation
        pass

    async def get_columns(self, objects: list[tuple[str, str]]) -> list[dict]:
        # Implementation
        pass

    async def get_dependencies(self) -> list[dict]:
        # Implementation
        pass

    async def execute_query(self, query: str) -> list[dict]:
        # Implementation
        pass
```

### Step 3: Register via Import

```python
# core/adapters/__init__.py
from .databricks import DatabricksAdapter
from .snowflake import SnowflakeAdapter
from .my_source import MySourceAdapter  # Add this line
```

### Step 4: Done

The adapter is now available via CLI and API.

---

## Source Configuration (YAML)

Configure multiple sources in a single file:

```yaml
# sources.yaml
sources:
  # Databricks with Azure Service Principal
  - name: databricks-prod
    type: databricks
    config:
      host: ${DATABRICKS_HOST}
      http_path: /sql/1.0/warehouses/abc123
      catalog: main
      schema_filter: "^(sales|marketing|analytics)$"
      auth_method: service_principal
      client_id: ${AZURE_CLIENT_ID}
      client_secret: ${AZURE_CLIENT_SECRET}
      tenant_id: ${AZURE_TENANT_ID}

  # Databricks with Personal Token (for dev)
  - name: databricks-dev
    type: databricks
    config:
      host: ${DATABRICKS_HOST}
      http_path: /sql/1.0/warehouses/dev123
      catalog: dev
      auth_method: personal_token
      access_token: ${DATABRICKS_TOKEN}

  # Snowflake
  - name: snowflake-prod
    type: snowflake
    config:
      account: mycompany.us-east-1
      warehouse: ANALYTICS_WH
      database: PROD
      role: ANALYST
      user: ${SNOWFLAKE_USER}
      password: ${SNOWFLAKE_PASSWORD}

  # PostgreSQL (Azure SQL)
  - name: azure-sql
    type: postgresql
    config:
      host: myserver.database.windows.net
      port: 5432
      database: analytics
      use_azure_ad: true
      client_id: ${AZURE_CLIENT_ID}
      client_secret: ${AZURE_CLIENT_SECRET}
      tenant_id: ${AZURE_TENANT_ID}

  # BigQuery
  - name: bigquery-prod
    type: bigquery
    config:
      project_id: my-gcp-project
      dataset_filter: "^(analytics|reporting)$"
      credentials_path: /secrets/gcp-service-account.json
```

Apply with: `datacompass source apply sources.yaml`

---

## CLI Commands

```bash
# List available adapter types
datacompass adapters list
# Output:
# TYPE         DISPLAY NAME              OBJECT TYPES
# databricks   Databricks Unity Catalog  TABLE, VIEW, MATERIALIZED_VIEW, FUNCTION
# snowflake    Snowflake                 TABLE, VIEW, MATERIALIZED_VIEW, PROCEDURE
# postgresql   PostgreSQL                TABLE, VIEW, MATERIALIZED_VIEW, FUNCTION
# bigquery     Google BigQuery           TABLE, VIEW, MATERIALIZED_VIEW

# Show config schema for an adapter
datacompass adapters schema databricks --format yaml

# Add sources from config file
datacompass source apply sources.yaml

# Or add single source
datacompass source add prod-db --type databricks --config databricks.yaml

# Test connection
datacompass source test prod-db

# Scan
datacompass scan prod-db
```

---

## Best Practices

### Error Handling

```python
async def connect(self) -> None:
    try:
        self._connection = create_connection(...)
    except AuthenticationError as e:
        raise AdapterError(f"Authentication failed: {e}") from e
    except NetworkError as e:
        raise AdapterError(f"Cannot reach {self.config.host}: {e}") from e
```

### Connection Pooling

For adapters that support it, consider connection pooling for better performance:

```python
def __init__(self, config: MySourceConfig):
    super().__init__(config)
    self._pool = None

async def connect(self) -> None:
    self._pool = await create_pool(
        host=self.config.host,
        min_size=1,
        max_size=10,
    )
```

### Retry Logic

Cloud sources may have transient failures. Implement retry with backoff:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def execute_query(self, query: str) -> list[dict]:
    # Implementation with automatic retry
    pass
```

### Rate Limiting

Some cloud APIs have rate limits. Track and respect them:

```python
from asyncio import Semaphore

class RateLimitedAdapter(SourceAdapter):
    def __init__(self, config):
        super().__init__(config)
        self._semaphore = Semaphore(10)  # Max 10 concurrent requests

    async def execute_query(self, query: str) -> list[dict]:
        async with self._semaphore:
            return await self._execute_query_impl(query)
```
