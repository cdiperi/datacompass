# Cloud Database Adapters Implementation Plan

**Goal:** Implement and test adapters for 5 cloud databases using free tiers
**Target Databases:** Snowflake, BigQuery, Redshift, Azure SQL, Databricks
**Estimated Cost:** $0 (using free tiers/trials)

---

## Overview

Each adapter must implement the `SourceAdapter` interface:

| Method | Required | Purpose |
|--------|----------|---------|
| `connect()` | Yes | Establish connection |
| `disconnect()` | Yes | Close connection |
| `test_connection()` | Yes | Verify connectivity |
| `get_objects()` | Yes | Fetch table/view metadata |
| `get_columns()` | Yes | Fetch column metadata |
| `execute_query()` | Yes | Run arbitrary SQL |
| `get_usage_metrics()` | No | Platform-specific usage stats |

---

## 1. Snowflake

### Free Tier Setup

- **Trial:** 30-day free trial with $400 credit
- **Sign up:** https://signup.snowflake.com/
- **What you get:** Full-featured account, no credit card required initially

### Account Setup Steps

1. Sign up for trial (use a personal email)
2. Choose cloud provider (AWS/Azure/GCP - any works)
3. Choose region closest to you
4. Note your account identifier: `<org>-<account>` (e.g., `xyz12345.us-east-1`)

### Connection Details

```yaml
# config/snowflake-dev.yaml
connection:
  account: ${SNOWFLAKE_ACCOUNT}      # e.g., xyz12345.us-east-1
  warehouse: COMPUTE_WH              # Default warehouse
  database: ${SNOWFLAKE_DATABASE}
  username: ${SNOWFLAKE_USER}
  password: ${SNOWFLAKE_PASSWORD}
  role: ACCOUNTADMIN                 # Or a custom role
```

### Python Driver

```bash
pip install snowflake-connector-python
```

### Config Schema

```python
# src/datacompass/core/adapters/schemas.py

class SnowflakeConfig(BaseModel):
    """Configuration for Snowflake connections."""

    account: str = Field(
        ...,
        description="Snowflake account identifier (e.g., xyz12345.us-east-1)",
    )
    warehouse: str = Field(
        ...,
        description="Compute warehouse name",
    )
    database: str = Field(
        ...,
        description="Database name to scan",
    )
    username: str = Field(
        ...,
        description="Snowflake username",
    )
    password: SecretStr = Field(
        ...,
        description="Snowflake password",
    )
    role: str | None = Field(
        default=None,
        description="Role to assume (optional)",
    )
    schema_filter: str | None = Field(
        default=None,
        description="Regex pattern to filter schemas",
    )
    exclude_schemas: list[str] = Field(
        default_factory=lambda: ["INFORMATION_SCHEMA"],
        description="Schemas to exclude from scanning",
    )
```

### Metadata Queries

```sql
-- Get objects (tables/views)
SELECT
    table_schema AS schema_name,
    table_name AS object_name,
    table_type AS object_type,
    created AS created_at,
    last_altered AS updated_at,
    comment AS description,
    row_count,
    bytes AS size_bytes
FROM information_schema.tables
WHERE table_catalog = :database
  AND table_schema NOT IN ('INFORMATION_SCHEMA')
ORDER BY table_schema, table_name;

-- Get columns
SELECT
    table_schema AS schema_name,
    table_name AS object_name,
    column_name,
    ordinal_position AS position,
    data_type,
    is_nullable,
    column_default,
    comment AS description
FROM information_schema.columns
WHERE table_catalog = :database
  AND (table_schema, table_name) IN (...)
ORDER BY table_schema, table_name, ordinal_position;

-- Get view dependencies (for lineage)
SELECT
    referencing_object_name AS view_name,
    referencing_schema_name AS view_schema,
    referenced_object_name AS source_name,
    referenced_schema_name AS source_schema
FROM snowflake.account_usage.object_dependencies
WHERE referencing_database = :database
  AND dependency_type = 'BY_NAME';
```

### Usage Metrics

Snowflake has excellent usage tracking via `SNOWFLAKE.ACCOUNT_USAGE`:

```sql
-- Query history for table access patterns
SELECT
    query_text,
    database_name,
    schema_name,
    user_name,
    start_time,
    total_elapsed_time
FROM snowflake.account_usage.query_history
WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND database_name = :database;

-- Table storage metrics
SELECT
    table_catalog,
    table_schema,
    table_name,
    active_bytes,
    time_travel_bytes,
    failsafe_bytes,
    row_count
FROM snowflake.account_usage.table_storage_metrics
WHERE table_catalog = :database;
```

### Implementation Notes

- Snowflake uses uppercase identifiers by default; handle case sensitivity
- `information_schema` queries are fast; `account_usage` has ~45min latency
- Connection pooling not needed for metadata scanning

---

## 2. Google BigQuery

### Free Tier Setup

- **Always free:** 10GB storage, 1TB queries/month
- **Console:** https://console.cloud.google.com/bigquery
- **No trial needed** - just create a Google Cloud project

### Account Setup Steps

1. Go to Google Cloud Console
2. Create a new project (e.g., `datacompass-dev`)
3. Enable BigQuery API (usually auto-enabled)
4. Create a service account:
   - IAM & Admin → Service Accounts → Create
   - Grant role: `BigQuery Data Viewer` + `BigQuery Job User`
   - Create JSON key and download

### Connection Details

```yaml
# config/bigquery-dev.yaml
connection:
  project: ${GCP_PROJECT_ID}
  credentials_path: ${GOOGLE_APPLICATION_CREDENTIALS}  # Path to JSON key
  location: US  # or EU, etc.
```

### Python Driver

```bash
pip install google-cloud-bigquery
```

### Config Schema

```python
class BigQueryConfig(BaseModel):
    """Configuration for Google BigQuery connections."""

    project: str = Field(
        ...,
        description="GCP project ID",
    )
    credentials_path: str | None = Field(
        default=None,
        description="Path to service account JSON key (uses ADC if not provided)",
    )
    location: str = Field(
        default="US",
        description="Dataset location",
    )
    dataset_filter: str | None = Field(
        default=None,
        description="Regex pattern to filter datasets",
    )
    exclude_datasets: list[str] = Field(
        default_factory=list,
        description="Datasets to exclude from scanning",
    )
```

### Metadata Queries

BigQuery uses `INFORMATION_SCHEMA` per-region:

```sql
-- Get datasets (schemas)
SELECT
    schema_name,
    creation_time,
    last_modified_time,
    location
FROM `project.region-US`.INFORMATION_SCHEMA.SCHEMATA;

-- Get tables in a dataset
SELECT
    table_schema AS schema_name,
    table_name AS object_name,
    table_type AS object_type,
    creation_time AS created_at,
    -- BigQuery-specific
    ddl,
    row_count,
    size_bytes
FROM `project.dataset`.INFORMATION_SCHEMA.TABLES;

-- Get columns
SELECT
    table_schema AS schema_name,
    table_name AS object_name,
    column_name,
    ordinal_position AS position,
    data_type,
    is_nullable,
    column_default_value AS column_default,
    -- BigQuery-specific
    is_partitioning_column,
    clustering_ordinal_position
FROM `project.dataset`.INFORMATION_SCHEMA.COLUMNS
WHERE table_name = :table_name;

-- Get view definitions (for lineage)
SELECT
    table_name,
    view_definition
FROM `project.dataset`.INFORMATION_SCHEMA.VIEWS;
```

### Usage Metrics

BigQuery has `INFORMATION_SCHEMA.JOBS_BY_*` views:

```sql
-- Recent queries touching tables
SELECT
    user_email,
    job_id,
    creation_time,
    total_bytes_processed,
    referenced_tables
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND state = 'DONE';
```

### Implementation Notes

- BigQuery uses datasets (not schemas) as the organizational unit
- Must query `INFORMATION_SCHEMA` per-dataset for some views
- Use the Python client library, not raw SQL for connection handling
- BigQuery handles case differently; preserve original casing

---

## 3. AWS Redshift

### Free Tier Setup

- **Trial:** Redshift Serverless - 3 months free with $300 credit
- **Console:** https://console.aws.amazon.com/redshiftv2/
- **Requires:** AWS account (credit card needed, but won't be charged within limits)

### Account Setup Steps

1. Go to AWS Console → Redshift
2. Create Serverless namespace and workgroup:
   - Namespace: `datacompass-dev`
   - Workgroup: `datacompass-workgroup`
   - Choose default VPC or create one
3. Create database user or use admin credentials
4. Configure security group to allow your IP

### Connection Details

```yaml
# config/redshift-dev.yaml
connection:
  host: ${REDSHIFT_HOST}           # workgroup.account.region.redshift-serverless.amazonaws.com
  port: 5439
  database: dev                     # Default database
  username: ${REDSHIFT_USER}
  password: ${REDSHIFT_PASSWORD}
```

### Python Driver

```bash
pip install redshift-connector
# OR use psycopg2 (Redshift is PostgreSQL-compatible)
pip install psycopg2-binary
```

### Config Schema

```python
class RedshiftConfig(BaseModel):
    """Configuration for AWS Redshift connections."""

    host: str = Field(
        ...,
        description="Redshift endpoint hostname",
    )
    port: int = Field(
        default=5439,
        description="Redshift port",
    )
    database: str = Field(
        ...,
        description="Database name",
    )
    username: str = Field(
        ...,
        description="Database username",
    )
    password: SecretStr = Field(
        ...,
        description="Database password",
    )
    # Alternative: IAM auth
    iam_auth: bool = Field(
        default=False,
        description="Use IAM authentication instead of password",
    )
    aws_region: str | None = Field(
        default=None,
        description="AWS region (required for IAM auth)",
    )
    schema_filter: str | None = Field(
        default=None,
        description="Regex pattern to filter schemas",
    )
    exclude_schemas: list[str] = Field(
        default_factory=lambda: ["pg_catalog", "information_schema", "pg_internal"],
        description="Schemas to exclude",
    )
```

### Metadata Queries

Redshift is PostgreSQL-based but has its own system tables:

```sql
-- Get objects (tables/views)
SELECT
    schemaname AS schema_name,
    tablename AS object_name,
    'TABLE' AS object_type
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
UNION ALL
SELECT
    schemaname AS schema_name,
    viewname AS object_name,
    'VIEW' AS object_type
FROM pg_views
WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_internal');

-- Get columns
SELECT
    n.nspname AS schema_name,
    c.relname AS object_name,
    a.attname AS column_name,
    a.attnum AS position,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    NOT a.attnotnull AS is_nullable,
    d.adsrc AS column_default
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
LEFT JOIN pg_catalog.pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
WHERE a.attnum > 0
  AND NOT a.attisdropped
  AND n.nspname = :schema
  AND c.relname = :table
ORDER BY a.attnum;

-- Get table sizes
SELECT
    "schema" AS schema_name,
    "table" AS object_name,
    size AS size_mb,
    tbl_rows AS row_count
FROM svv_table_info
WHERE "schema" NOT IN ('pg_catalog', 'information_schema');
```

### Usage Metrics

Redshift tracks queries in system tables:

```sql
-- Recent query activity
SELECT
    userid,
    query,
    querytxt,
    starttime,
    endtime,
    elapsed
FROM stl_query
WHERE starttime > DATEADD(day, -30, CURRENT_DATE)
ORDER BY starttime DESC;

-- Table scan statistics
SELECT
    "schema",
    "table",
    scan_count,
    row_count,
    size
FROM svv_table_info;
```

### Implementation Notes

- Redshift is PostgreSQL-compatible; can reuse much of PostgreSQL adapter
- System tables differ from PostgreSQL (`stl_*`, `svv_*`, `svl_*`)
- Serverless vs Provisioned: same SQL, different pricing
- Connection string format is identical to PostgreSQL

---

## 4. Azure SQL Database

### Free Tier Setup

- **Always free:** 100,000 vCore seconds/month (Basic tier)
- **Console:** https://portal.azure.com/
- **Requires:** Azure account (free tier available)

### Account Setup Steps

1. Azure Portal → SQL databases → Create
2. Create new resource group: `datacompass-dev-rg`
3. Create new server:
   - Server name: `datacompass-dev-server`
   - Region: closest to you
   - Admin login and password
4. Database settings:
   - Database name: `datacompass_test`
   - Compute: **Serverless** (scales to zero)
   - Choose **Free** offer or Basic tier
5. Networking:
   - Add your client IP to firewall rules
   - Enable "Allow Azure services" if needed

### Connection Details

```yaml
# config/azuresql-dev.yaml
connection:
  server: ${AZURE_SQL_SERVER}.database.windows.net
  database: ${AZURE_SQL_DATABASE}
  username: ${AZURE_SQL_USER}
  password: ${AZURE_SQL_PASSWORD}
  # Alternative: Azure AD auth
  # authentication: ActiveDirectoryPassword
```

### Python Driver

```bash
pip install pyodbc
# Also need ODBC driver installed on system
# macOS: brew install unixodbc msodbcsql18
# Linux: see Microsoft docs for repo setup
```

### Config Schema

```python
class AzureSQLConfig(BaseModel):
    """Configuration for Azure SQL Database connections."""

    server: str = Field(
        ...,
        description="Azure SQL server name (without .database.windows.net)",
    )
    database: str = Field(
        ...,
        description="Database name",
    )
    username: str | None = Field(
        default=None,
        description="SQL authentication username",
    )
    password: SecretStr | None = Field(
        default=None,
        description="SQL authentication password",
    )
    # Azure AD auth
    auth_method: AuthMethod = Field(
        default=AuthMethod.USERNAME_PASSWORD,
        description="Authentication method",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Azure AD tenant ID (for AAD auth)",
    )
    client_id: str | None = Field(
        default=None,
        description="Azure AD client ID (for service principal)",
    )
    client_secret: SecretStr | None = Field(
        default=None,
        description="Azure AD client secret",
    )
    schema_filter: str | None = Field(
        default=None,
        description="Regex pattern to filter schemas",
    )
    exclude_schemas: list[str] = Field(
        default_factory=lambda: ["sys", "INFORMATION_SCHEMA", "guest"],
        description="Schemas to exclude",
    )
    encrypt: bool = Field(
        default=True,
        description="Encrypt connection (required for Azure)",
    )
```

### Metadata Queries

Azure SQL uses standard SQL Server system views:

```sql
-- Get objects (tables/views)
SELECT
    s.name AS schema_name,
    t.name AS object_name,
    CASE t.type
        WHEN 'U' THEN 'TABLE'
        WHEN 'V' THEN 'VIEW'
    END AS object_type,
    t.create_date AS created_at,
    t.modify_date AS updated_at,
    ep.value AS description
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
LEFT JOIN sys.extended_properties ep
    ON ep.major_id = t.object_id
    AND ep.minor_id = 0
    AND ep.name = 'MS_Description'
WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')

UNION ALL

SELECT
    s.name AS schema_name,
    v.name AS object_name,
    'VIEW' AS object_type,
    v.create_date AS created_at,
    v.modify_date AS updated_at,
    ep.value AS description
FROM sys.views v
JOIN sys.schemas s ON v.schema_id = s.schema_id
LEFT JOIN sys.extended_properties ep
    ON ep.major_id = v.object_id
    AND ep.minor_id = 0
    AND ep.name = 'MS_Description';

-- Get columns
SELECT
    s.name AS schema_name,
    t.name AS object_name,
    c.name AS column_name,
    c.column_id AS position,
    TYPE_NAME(c.user_type_id) +
        CASE
            WHEN TYPE_NAME(c.user_type_id) IN ('varchar', 'nvarchar', 'char', 'nchar')
                THEN '(' + CAST(c.max_length AS VARCHAR) + ')'
            WHEN TYPE_NAME(c.user_type_id) IN ('decimal', 'numeric')
                THEN '(' + CAST(c.precision AS VARCHAR) + ',' + CAST(c.scale AS VARCHAR) + ')'
            ELSE ''
        END AS data_type,
    c.is_nullable,
    dc.definition AS column_default,
    ep.value AS description
FROM sys.columns c
JOIN sys.tables t ON c.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
LEFT JOIN sys.extended_properties ep
    ON ep.major_id = c.object_id
    AND ep.minor_id = c.column_id
    AND ep.name = 'MS_Description'
WHERE s.name = :schema AND t.name = :table
ORDER BY c.column_id;

-- Get foreign keys (for lineage)
SELECT
    OBJECT_SCHEMA_NAME(fk.parent_object_id) AS source_schema,
    OBJECT_NAME(fk.parent_object_id) AS source_table,
    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS source_column,
    OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS target_schema,
    OBJECT_NAME(fk.referenced_object_id) AS target_table,
    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS target_column,
    fk.name AS constraint_name
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id;

-- Get view dependencies
SELECT
    OBJECT_SCHEMA_NAME(d.referencing_id) AS view_schema,
    OBJECT_NAME(d.referencing_id) AS view_name,
    d.referenced_schema_name AS source_schema,
    d.referenced_entity_name AS source_table
FROM sys.sql_expression_dependencies d
JOIN sys.views v ON d.referencing_id = v.object_id
WHERE d.referenced_entity_name IS NOT NULL;
```

### Usage Metrics

Azure SQL has Query Store and DMVs:

```sql
-- Query Store statistics
SELECT
    q.query_id,
    qt.query_sql_text,
    rs.count_executions,
    rs.avg_duration,
    rs.avg_cpu_time
FROM sys.query_store_query q
JOIN sys.query_store_query_text qt ON q.query_text_id = qt.query_text_id
JOIN sys.query_store_plan p ON q.query_id = p.query_id
JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
WHERE rs.last_execution_time > DATEADD(day, -30, GETDATE());

-- Table row counts and sizes
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    p.rows AS row_count,
    SUM(a.total_pages) * 8 * 1024 AS size_bytes
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id
JOIN sys.allocation_units a ON p.partition_id = a.container_id
WHERE p.index_id IN (0, 1)  -- heap or clustered index
GROUP BY s.name, t.name, p.rows;
```

### Implementation Notes

- Requires ODBC driver installation (platform-specific)
- Azure AD auth preferred for production (no password rotation)
- Connection string includes `Encrypt=yes` by default
- Case sensitivity depends on database collation

---

## 5. Databricks (Unity Catalog)

### Free Tier Setup

- **Community Edition:** Free, but limited (no Unity Catalog)
- **Trial:** 14-day full trial available
- **Console:** https://accounts.cloud.databricks.com/

For Unity Catalog features, you need a workspace trial (not Community Edition).

### Account Setup Steps

1. Sign up at Databricks (choose AWS, Azure, or GCP)
2. Create a workspace
3. Enable Unity Catalog (if not auto-enabled)
4. Create a SQL Warehouse:
   - SQL → SQL Warehouses → Create
   - Choose Serverless for cost efficiency
5. Generate personal access token:
   - User Settings → Developer → Access tokens → Generate

### Connection Details

```yaml
# config/databricks-dev.yaml
connection:
  host: ${DATABRICKS_HOST}           # adb-xxx.azuredatabricks.net
  http_path: ${DATABRICKS_HTTP_PATH} # /sql/1.0/warehouses/abc123
  catalog: main                       # Unity Catalog name
  access_token: ${DATABRICKS_TOKEN}
```

### Existing Implementation

The Databricks adapter already exists at `src/datacompass/core/adapters/databricks.py`. It needs:

1. **Testing** against real Unity Catalog
2. **Lineage extraction** - Unity Catalog has lineage APIs
3. **Usage metrics** - via system tables

### Additional Metadata Queries

```sql
-- Get table lineage (Unity Catalog)
SELECT
    source_table_full_name,
    source_column_name,
    target_table_full_name,
    target_column_name
FROM system.access.column_lineage
WHERE target_table_full_name LIKE :catalog || '.%';

-- Get table access history
SELECT
    event_time,
    service_principal,
    action_name,
    request_params.full_name_arg AS table_name
FROM system.access.audit
WHERE action_name IN ('getTable', 'createTable', 'alterTable')
  AND event_date > DATE_SUB(CURRENT_DATE(), 30);
```

### Implementation Notes

- Adapter exists but is untested
- Unity Catalog provides richer lineage than most platforms
- Multiple auth methods supported (token, service principal, managed identity)
- Serverless SQL warehouse recommended for cost

---

## Standard Test Schema

Create this schema in each database for consistent testing:

```sql
-- Schema/Dataset
CREATE SCHEMA IF NOT EXISTS datacompass_test;

-- Sample tables
CREATE TABLE datacompass_test.customers (
    customer_id INT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE datacompass_test.orders (
    order_id INT PRIMARY KEY,
    customer_id INT REFERENCES datacompass_test.customers(customer_id),
    order_date DATE NOT NULL,
    total_amount DECIMAL(10,2),
    status VARCHAR(20)
);

CREATE TABLE datacompass_test.order_items (
    item_id INT PRIMARY KEY,
    order_id INT REFERENCES datacompass_test.orders(order_id),
    product_name VARCHAR(200),
    quantity INT,
    unit_price DECIMAL(10,2)
);

-- Sample view (for lineage testing)
CREATE VIEW datacompass_test.customer_order_summary AS
SELECT
    c.customer_id,
    c.name,
    c.email,
    COUNT(o.order_id) AS order_count,
    SUM(o.total_amount) AS total_spent
FROM datacompass_test.customers c
LEFT JOIN datacompass_test.orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.email;

-- Sample data
INSERT INTO datacompass_test.customers VALUES
    (1, 'alice@example.com', 'Alice Smith', CURRENT_TIMESTAMP, TRUE),
    (2, 'bob@example.com', 'Bob Jones', CURRENT_TIMESTAMP, TRUE),
    (3, 'carol@example.com', 'Carol White', CURRENT_TIMESTAMP, FALSE);

INSERT INTO datacompass_test.orders VALUES
    (101, 1, '2024-01-15', 150.00, 'completed'),
    (102, 1, '2024-02-20', 75.50, 'completed'),
    (103, 2, '2024-03-10', 200.00, 'pending');

INSERT INTO datacompass_test.order_items VALUES
    (1001, 101, 'Widget A', 2, 50.00),
    (1002, 101, 'Widget B', 1, 50.00),
    (1003, 102, 'Gadget X', 1, 75.50),
    (1004, 103, 'Widget A', 4, 50.00);

-- Add comments/descriptions
COMMENT ON TABLE datacompass_test.customers IS 'Customer master data';
COMMENT ON COLUMN datacompass_test.customers.email IS 'Primary contact email';
COMMENT ON TABLE datacompass_test.orders IS 'Customer orders';
COMMENT ON VIEW datacompass_test.customer_order_summary IS 'Aggregated customer order metrics';
```

**Note:** Syntax varies by platform. Adapt as needed:
- BigQuery: `CREATE SCHEMA` → `CREATE DATASET`
- Snowflake: Add `CREATE DATABASE` first
- Azure SQL: Comments use `sp_addextendedproperty`

---

## Testing Strategy

### Directory Structure

```
tests/
└── core/
    └── adapters/
        ├── conftest.py              # Shared fixtures
        ├── test_postgresql.py       # Existing
        ├── test_snowflake.py        # New
        ├── test_bigquery.py         # New
        ├── test_redshift.py         # New
        ├── test_azuresql.py         # New
        └── test_databricks.py       # New
```

### Test Fixture Pattern

```python
# tests/core/adapters/conftest.py
import os
import pytest

def env_configured(prefix: str) -> bool:
    """Check if environment variables for a database are set."""
    required = {
        "SNOWFLAKE": ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_DATABASE"],
        "BIGQUERY": ["GCP_PROJECT_ID"],
        "REDSHIFT": ["REDSHIFT_HOST", "REDSHIFT_USER", "REDSHIFT_PASSWORD"],
        "AZURESQL": ["AZURE_SQL_SERVER", "AZURE_SQL_USER", "AZURE_SQL_PASSWORD"],
        "DATABRICKS": ["DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_HTTP_PATH"],
    }
    return all(os.getenv(var) for var in required.get(prefix, []))


@pytest.fixture
def snowflake_config():
    """Create Snowflake config from environment."""
    from datacompass.core.adapters.schemas import SnowflakeConfig
    return SnowflakeConfig(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ["SNOWFLAKE_DATABASE"],
        username=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
    )
```

### Integration Test Template

```python
# tests/core/adapters/test_snowflake.py
import pytest
from tests.core.adapters.conftest import env_configured

pytestmark = pytest.mark.skipif(
    not env_configured("SNOWFLAKE"),
    reason="Snowflake credentials not configured"
)


class TestSnowflakeAdapterIntegration:
    """Integration tests for Snowflake adapter."""

    @pytest.fixture
    async def adapter(self, snowflake_config):
        from datacompass.core.adapters.snowflake import SnowflakeAdapter
        adapter = SnowflakeAdapter(snowflake_config)
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    async def test_connection(self, adapter):
        """Test that connection works."""
        assert await adapter.test_connection()

    async def test_get_objects(self, adapter):
        """Test fetching table/view metadata."""
        objects = await adapter.get_objects()
        assert len(objects) > 0

        # Check required fields
        obj = objects[0]
        assert "schema_name" in obj
        assert "object_name" in obj
        assert "object_type" in obj
        assert obj["object_type"] in ["TABLE", "VIEW", "MATERIALIZED VIEW"]

    async def test_get_columns(self, adapter):
        """Test fetching column metadata."""
        objects = await adapter.get_objects(object_types=["TABLE"])
        if not objects:
            pytest.skip("No tables found")

        sample = [(objects[0]["schema_name"], objects[0]["object_name"])]
        columns = await adapter.get_columns(sample)

        assert len(columns) > 0
        col = columns[0]
        assert "column_name" in col
        assert "position" in col
        assert "source_metadata" in col
        assert "data_type" in col["source_metadata"]

    async def test_execute_query(self, adapter):
        """Test arbitrary query execution."""
        result = await adapter.execute_query("SELECT 1 AS test_value")
        assert result == [{"test_value": 1}]

    async def test_get_test_schema(self, adapter):
        """Test that our test schema exists."""
        objects = await adapter.get_objects()
        test_objects = [o for o in objects if o["schema_name"] == "DATACOMPASS_TEST"]

        # Should have customers, orders, order_items tables and summary view
        assert len(test_objects) >= 4
```

### Running Tests

```bash
# Run all adapter tests (skips unconfigured ones)
.venv/bin/pytest tests/core/adapters/ -v

# Run only Snowflake tests
.venv/bin/pytest tests/core/adapters/test_snowflake.py -v

# Run with coverage
.venv/bin/pytest tests/core/adapters/ --cov=datacompass.core.adapters -v
```

### CI/CD Integration

Store credentials as GitHub secrets and use them in CI:

```yaml
# .github/workflows/test-adapters.yml
name: Test Cloud Adapters

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday

jobs:
  test-adapters:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev,snowflake,bigquery,redshift,azuresql,databricks]"

      - name: Run adapter tests
        env:
          SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
          SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
          SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
          SNOWFLAKE_DATABASE: ${{ secrets.SNOWFLAKE_DATABASE }}
          # ... other secrets
        run: |
          pytest tests/core/adapters/ -v --tb=short
```

---

## Implementation Order

| Phase | Database | Rationale |
|-------|----------|-----------|
| 1 | **Snowflake** | Clean SQL, excellent docs, generous trial |
| 2 | **BigQuery** | Always-free tier, different paradigm (good for testing generality) |
| 3 | **Redshift** | PostgreSQL-based (leverage existing code), AWS popular |
| 4 | **Azure SQL** | SQL Server syntax, different from others |
| 5 | **Databricks** | Already scaffolded, needs testing/completion |

---

## Dependencies to Add

Update `pyproject.toml` with optional dependencies:

```toml
[project.optional-dependencies]
# ... existing ...
snowflake = ["snowflake-connector-python>=3.0.0"]
bigquery = ["google-cloud-bigquery>=3.0.0"]
redshift = ["redshift-connector>=2.0.0"]
azuresql = ["pyodbc>=4.0.0"]
databricks = ["databricks-sql-connector>=2.0.0"]
azure = ["azure-identity>=1.12.0"]  # For Azure AD auth

# All cloud adapters
cloud = [
    "snowflake-connector-python>=3.0.0",
    "google-cloud-bigquery>=3.0.0",
    "redshift-connector>=2.0.0",
    "pyodbc>=4.0.0",
    "databricks-sql-connector>=2.0.0",
    "azure-identity>=1.12.0",
]
```

---

## Checklist

### Setup (do once)

- [ ] Create Snowflake trial account
- [ ] Create GCP project with BigQuery
- [ ] Create AWS account with Redshift Serverless
- [ ] Create Azure account with SQL Database
- [ ] Create Databricks workspace trial
- [ ] Set up test schema in each database
- [ ] Create `.env.adapters` with all credentials (gitignored)

### Per Adapter

- [ ] Add config schema to `schemas.py`
- [ ] Implement adapter class
- [ ] Register in `AdapterRegistry`
- [ ] Write integration tests
- [ ] Test with CLI: `datacompass source add`, `datacompass scan`
- [ ] Document any platform-specific quirks

### Completion

- [ ] All 5 adapters passing tests
- [ ] Update `pyproject.toml` with optional deps
- [ ] Update docs with supported databases
- [ ] Clean up cloud resources to avoid charges

---

## Cost Management Tips

1. **Snowflake:** Suspend warehouse when not in use; trial credit is generous
2. **BigQuery:** Stay under 1TB queries/month; use `LIMIT` during development
3. **Redshift Serverless:** Auto-pauses when idle; delete when done testing
4. **Azure SQL:** Serverless tier auto-pauses; Free tier has monthly limits
5. **Databricks:** Stop SQL warehouse when not testing

Set calendar reminders to:
- Check usage dashboards weekly
- Delete resources after testing complete
- Cancel trials before they convert to paid

---

## Notes

- Each adapter follows the same async pattern as PostgreSQL
- All use `run_in_executor` for sync drivers (most cloud connectors are sync)
- Test with real credentials locally before committing
- Credentials should never be committed; use environment variables
