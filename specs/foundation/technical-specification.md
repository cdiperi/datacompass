# Data Compass - Technical Specification

## Executive Summary

Data Compass is a metadata catalog application for database systems with data quality monitoring and lineage visualization. It provides a unified interface for browsing, searching, documenting, and understanding database objects across multiple data sources.

---

## 1. Core Purpose & Features

### What Data Compass Does
- **Metadata Catalog**: Browse, search, and document database objects (tables, views, stored procedures, etc.)
- **Multi-Database Support**: Connect to multiple databases/data sources from a single UI
- **Data Quality Monitoring**: Track metrics (row counts, null counts, etc.) and detect anomalies
- **Lineage Visualization**: Show data flow and dependencies between objects
- **Deprecation Management**: Create campaigns to deprecate objects with dependency warnings

### Key User Flows
1. **Search → Browse → Detail**: Search-first landing → paginated results → rich object detail page
2. **DQ Monitoring**: Configure expectations → scheduled execution → breach detection → investigation
3. **Lineage Exploration**: Select object → expand upstream/downstream → understand data flow
4. **Deprecation Campaigns**: Create campaign → select objects → review dependencies → track migration

---

## 2. Tech Stack

### Core Library (Python)
| Component | Technology | Rationale |
|-----------|------------|-----------|
| ORM | **SQLAlchemy 2.0** | Type hints, supports SQLite and PostgreSQL |
| Validation | **Pydantic v2** | Fast validation, good error messages |
| CLI Framework | **Typer** or **Click** | First-class CLI experience |
| Local Storage | **SQLite** | Zero infrastructure, local-first |
| Production Storage | **PostgreSQL** (optional) | For multi-user deployments |

### API Layer
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | **FastAPI** | Async support, automatic OpenAPI docs |
| Task Queue | **Celery + Redis** (optional) | For scheduled/distributed tasks |

### Frontend
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | **React 18+** | Component model, ecosystem |
| Build | **Vite** | Fast builds, HMR |
| UI Library | **Ant Design 5** | Comprehensive, well-maintained |
| Data Fetching | **TanStack Query v5** | Caching, devtools |
| Graph Viz | **ReactFlow** | Lineage visualization |

### Infrastructure
- **SQLite** for local/single-user (default)
- **PostgreSQL** for team deployments (optional)
- **Docker Compose** for local development
- **Redis** for Celery broker (optional, for scheduling)
- **GitHub Actions** for CI/CD

---

## 3. Database Schema Design

### Core Entities

```
┌─────────────────┐
│  DataSource     │ Multi-database registry
├─────────────────┤
│ id              │
│ name (unique)   │ Identifier for this source
│ display_name    │
│ source_type     │ The type of data source (for adapter selection)
│ connection_info │ JSON: connection parameters (host, port, etc.)
│ sync_config     │ JSON: enabled, schedule, options
│ is_active       │
│ created_at      │
│ updated_at      │
└────────┬────────┘
         │
         ▼ 1:N
┌─────────────────┐
│     Object      │ Tables, views, procedures, etc.
├─────────────────┤
│ id              │
│ source_id (FK)  │
│ schema_name     │ Schema/namespace/owner
│ object_name     │
│ object_type     │ TABLE, VIEW, PROCEDURE, FILE, etc.
│ source_metadata │ JSON: metadata from source (row count, size, etc.)
│ user_metadata   │ JSON: description, tags, business_name
│ created_at      │
│ updated_at      │
│ deleted_at      │ Soft delete support
└────────┬────────┘
         │
         ▼ 1:N
┌─────────────────┐
│     Column      │
├─────────────────┤
│ id              │
│ object_id (FK)  │
│ column_name     │
│ position        │
│ source_metadata │ JSON: data_type, nullable, precision
│ user_metadata   │ JSON: description, business_name, is_pii
└─────────────────┘
```

### Dependency/Lineage

```
┌─────────────────┐
│   Dependency    │ Object relationships
├─────────────────┤
│ id              │
│ source_id       │
│ object_id (FK)  │ The dependent object
│ target_id (FK)  │ The object being depended on (nullable)
│ target_external │ JSON: schema, name, type, location (for external refs)
│ dependency_type │ DIRECT, INDIRECT
│ parsing_source  │ source_metadata, sql_parsing, file_log, manual
│ confidence      │ HIGH, MEDIUM, LOW (for heuristic matches)
│ source_context  │ Additional context (e.g., which package for sql_parsing)
└─────────────────┘
```

### Data Quality

```
┌─────────────────┐
│   DQConfig      │ One per monitored object
├─────────────────┤
│ id              │
│ object_id (FK)  │ Unique
│ date_column     │
│ date_format     │
│ grain           │ daily, weekly, monthly
│ grain_config    │ JSON: day_of_week, day_of_month
│ is_enabled      │
│ last_executed   │
└────────┬────────┘
         │
         ▼ 1:N
┌─────────────────┐
│ DQExpectation   │ Individual metrics
├─────────────────┤
│ id              │
│ config_id (FK)  │
│ metric_type     │ row_count, distinct_count, null_count, etc.
│ column_name     │ NULL for table-level
│ threshold_config│ JSON: type, min, max, multiplier
│ priority        │ 1=Critical, 2=High, 3=Medium, 4=Low
│ is_enabled      │
└────────┬────────┘
         │
         ├─► 1:N DQResult (metric_value by date)
         │
         └─► 1:N DQBreach (threshold violations)
              │
              ├─ threshold_snapshot │ JSON: complete config at detection
              ├─ status             │ open, acknowledged, dismissed, resolved
              └─ lifecycle_events   │ JSON array: [{status, by, at, notes}]
```

### Deprecation

```
┌─────────────────────┐
│ DeprecationCampaign │
├─────────────────────┤
│ id                  │
│ source_id           │
│ name                │
│ description         │
│ status              │ draft, active, completed
│ target_date         │
└──────────┬──────────┘
           │
           ▼ 1:N
┌─────────────────────┐
│    Deprecation      │
├─────────────────────┤
│ campaign_id (FK)    │
│ object_id (FK)      │
│ replacement_id (FK) │ Nullable
│ migration_notes     │
└─────────────────────┘
```

### Governance

```
┌─────────────────────┐
│   Classification    │ Object/column classification
├─────────────────────┤
│ id                  │
│ object_id (FK)      │
│ column_id (FK)      │ Nullable (null = object-level)
│ level               │ public, internal, confidential, restricted
│ compliance_labels   │ JSON array: ["gdpr", "hipaa", "pci_dss"]
│ classified_by       │
│ classified_at       │
│ source              │ manual, rule, inherited
└─────────────────────┘

┌─────────────────────┐
│      Domain         │ Business domain hierarchy
├─────────────────────┤
│ id                  │
│ name                │
│ description         │
│ parent_id (FK)      │ Self-referential for hierarchy
│ created_at          │
└─────────────────────┘

┌─────────────────────┐
│    ObjectOwner      │ Ownership assignments
├─────────────────────┤
│ id                  │
│ object_id (FK)      │
│ domain_id (FK)      │ Nullable
│ user_id             │ Email or username
│ role                │ owner, steward, delegate
│ assigned_by         │
│ assigned_at         │
└─────────────────────┘

┌─────────────────────┐
│    Permission       │ RBAC grants
├─────────────────────┤
│ id                  │
│ user_id             │
│ role                │ viewer, editor, steward, admin
│ scope_type          │ global, source, domain, object
│ scope_id            │ Nullable (null for global)
│ granted_by          │
│ granted_at          │
└─────────────────────┘

┌─────────────────────┐
│    AuditEvent       │ Audit trail
├─────────────────────┤
│ id                  │
│ timestamp           │
│ user_id             │
│ action              │ view, create, update, delete, classify, etc.
│ entity_type         │ object, dq_config, breach, etc.
│ entity_id           │
│ changes             │ JSON: {"field": {"old": x, "new": y}}
│ context             │ JSON: {ip, user_agent, etc.}
└─────────────────────┘
```

### Key Schema Design Decisions

1. **JSON columns for flexible metadata** - Source-specific metadata varies; JSON avoids schema changes
2. **Soft deletes** - `deleted_at` instead of cascade deletes; preserves history
3. **Lifecycle events array** - Track all status changes, not just current status
4. **Confidence scoring** - For heuristic-based dependency matching
5. **Threshold snapshot as JSON** - Simpler than many individual columns
6. **Source-agnostic naming** - `source_metadata` instead of vendor-specific names

---

## 4. API Design

### RESTful Resource Structure

```
/api/v1/
├── sources/
│   ├── GET    /                    List data sources
│   ├── POST   /                    Create data source
│   ├── GET    /{id}                Get data source
│   ├── PATCH  /{id}                Update data source
│   ├── DELETE /{id}                Soft delete data source
│   └── GET    /{id}/stats          Data source statistics
│
├── objects/
│   ├── GET    /                    List/search objects (with filters)
│   ├── GET    /{id}                Get object detail
│   ├── PATCH  /{id}                Update user metadata
│   ├── GET    /{id}/columns        Get columns
│   ├── GET    /{id}/lineage        Get lineage graph
│   └── GET    /lookup/{source}/{type}/{schema}/{name}  Semantic lookup
│
├── search/
│   ├── GET    /                    Full-text search
│   └── GET    /autocomplete        Search suggestions
│
├── dq/
│   ├── configs/
│   │   ├── GET    /                List DQ configs
│   │   ├── POST   /                Create config
│   │   ├── GET    /{id}            Get config with expectations
│   │   ├── PATCH  /{id}            Update config
│   │   ├── DELETE /{id}            Delete config
│   │   └── POST   /{id}/execute    Trigger execution
│   │
│   ├── expectations/
│   │   ├── POST   /                Create expectation
│   │   ├── PATCH  /{id}            Update expectation
│   │   └── DELETE /{id}            Delete expectation
│   │
│   ├── breaches/
│   │   ├── GET    /                List breaches (filterable)
│   │   ├── GET    /{id}            Get breach detail
│   │   ├── PATCH  /{id}/status     Update breach status
│   │   └── POST   /bulk/status     Bulk status update
│   │
│   └── hub/
│       └── GET    /summary         DQ dashboard data
│
├── deprecations/
│   ├── campaigns/
│   │   ├── GET    /                List campaigns
│   │   ├── POST   /                Create campaign
│   │   ├── GET    /{id}            Get campaign with objects
│   │   ├── PATCH  /{id}            Update campaign
│   │   └── DELETE /{id}            Delete campaign
│   │
│   └── POST   /check-dependencies  Check deprecation impact
│
├── sync/
│   ├── POST   /trigger             Trigger sync
│   ├── GET    /history             Sync history
│   └── GET    /status              Current sync status
│
└── system/
    ├── GET    /health              Health check
    └── GET    /metrics             Prometheus metrics
```

### API Design Principles

1. **Consistent response envelope**
   ```json
   {
     "data": {...},
     "meta": {"total": 100, "page": 1, "limit": 50},
     "errors": null
   }
   ```

2. **Standardized error format**
   ```json
   {
     "data": null,
     "errors": [{
       "code": "NOT_FOUND",
       "message": "Object not found",
       "field": null,
       "details": {"id": 123}
     }]
   }
   ```

3. **Query parameter conventions**
   - `page`, `limit` for pagination
   - `sort`, `order` for sorting
   - `fields` for sparse fieldsets
   - `include` for relationship expansion

4. **Filter conventions**
   - `status=open,acknowledged` (comma-separated OR)
   - `priority=1` (exact match)
   - `created_after=2024-01-01` (range)

---

## 5. Architecture Overview

### Terminal-First Design

The core library is the product. CLI, API, and web are interfaces to it.

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Interface                          │
│         (Visualization, collaboration, dashboards)          │
└─────────────────────────┬───────────────────────────────────┘
                          │ calls
┌─────────────────────────▼───────────────────────────────────┐
│                        API Layer                            │
│       (HTTP translation - thin, no business logic)          │
└─────────────────────────┬───────────────────────────────────┘
                          │ calls
┌─────────────────────────▼───────────────────────────────────┐
│                           CLI                               │
│            (First-class product surface)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ calls
┌─────────────────────────▼───────────────────────────────────┐
│                      Core Library                           │
│       (ALL business logic lives here)                       │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ CatalogSvc  │  │   DQSvc     │  │ DeprecationSvc      │ │
│  ├─────────────┤  ├─────────────┤  ├─────────────────────┤ │
│  │ scan()      │  │ configure() │  │ create_campaign()   │ │
│  │ search()    │  │ execute()   │  │ check_dependencies()│ │
│  │ get_detail()│  │ detect()    │  │ add_objects()       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Repository Layer                    │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────────┐    │   │
│  │  │ObjectRepo │  │ DQRepo    │  │DependencyRepo │    │   │
│  │  └───────────┘  └───────────┘  └───────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Every feature works headlessly** - If you can't do it from the CLI, the feature isn't ready
2. **API is a thin translation layer** - No business logic in route handlers
3. **Output is structured data** - JSON by default, human-friendly formatting optional
4. **Operations are idempotent** - Safe to re-run scans, DQ checks, etc.

### Key Services

**MetadataSyncService**
- Orchestrates multi-phase sync from data sources
- Uses adapter pattern for source-specific logic
- UPSERT pattern: preserve user metadata, update source metadata
- Scoped per source_id
- Reports progress via events/callbacks

**DQExecutionService**
- Builds and executes metric queries against data sources
- Stores results with UPSERT by date
- Triggers breach detection after execution

**DQBreachDetector**
- Calculates thresholds (absolute, simple_avg, dow_adjusted)
- Creates breach records with immutable threshold snapshots
- Re-evaluates existing breaches when thresholds change

**LineageService**
- Graph traversal with configurable depth
- Hub object filtering (prevent explosion from heavily-used objects)
- Deduplication by parsing source priority
- Cycle detection

**DependencyParser**
- Parses SQL/code for data flow patterns (INSERT/UPDATE/MERGE targets)
- Extensible for different SQL dialects
- Creates dependencies with appropriate `parsing_source`

---

## 6. Data Source Adapter Pattern

Data Compass uses an adapter pattern to support multiple database types. Each adapter is a plugin that implements a standard interface.

> **See**: [adapter-implementation-guide.md](adapter-implementation-guide.md) for complete implementation details, config schemas, and examples.

### Supported Adapters

| Adapter | Auth Methods | Object Types |
|---------|--------------|--------------|
| **Databricks** | Personal token, Service principal, Managed identity | TABLE, VIEW, MATERIALIZED_VIEW, FUNCTION |
| **Snowflake** | Username/password, Key-pair, OAuth | TABLE, VIEW, MATERIALIZED_VIEW, PROCEDURE |
| **PostgreSQL** | Username/password, Azure AD | TABLE, VIEW, MATERIALIZED_VIEW, FUNCTION |
| **BigQuery** | Service account, Default credentials | TABLE, VIEW, MATERIALIZED_VIEW |

### Adapter Interface (Summary)

```python
class SourceAdapter(ABC):
    SUPPORTED_OBJECT_TYPES: ClassVar[list[str]] = []
    SUPPORTED_DQ_METRICS: ClassVar[list[str]] = []

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def test_connection(self) -> bool: ...
    async def get_objects(self, object_types: list[str] | None) -> list[dict]: ...
    async def get_columns(self, objects: list[tuple[str, str]]) -> list[dict]: ...
    async def get_dependencies(self) -> list[dict]: ...
    async def execute_query(self, query: str) -> list[dict]: ...
    async def execute_dq_query(self, query: DQQuery) -> list[dict]: ...
```

### Adding Sources

```yaml
# sources.yaml
sources:
  - name: databricks-prod
    type: databricks
    config:
      host: ${DATABRICKS_HOST}
      http_path: /sql/1.0/warehouses/abc123
      catalog: main
      auth_method: service_principal
      client_id: ${AZURE_CLIENT_ID}
      client_secret: ${AZURE_CLIENT_SECRET}
      tenant_id: ${AZURE_TENANT_ID}

  - name: snowflake-prod
    type: snowflake
    config:
      account: mycompany.us-east-1
      warehouse: ANALYTICS_WH
      database: PROD
      user: ${SNOWFLAKE_USER}
      password: ${SNOWFLAKE_PASSWORD}
```

Apply with: `datacompass source apply sources.yaml`

---

## 7. Background Task System

### Design Principle

All operations work synchronously via CLI first. Background/scheduled execution is optional infrastructure added for automation.

### CLI-First Operations

```bash
# These work without any task queue infrastructure
datacompass scan production          # Sync metadata now
datacompass dq run --all             # Run DQ checks now
datacompass dq backfill sales --days 30
```

### Optional: Celery + Redis for Scheduling

For automated/scheduled operations, add Celery:

```python
# tasks/sync.py
@celery.task(bind=True, max_retries=3)
def sync_source_metadata(self, source_id: int, full_sync: bool = False):
    """Sync metadata for a data source."""
    # Calls the same core library the CLI uses
    service = MetadataSyncService(source_id)
    return service.sync()

# Scheduled via Celery Beat
CELERYBEAT_SCHEDULE = {
    'metadata-sync-daily': {
        'task': 'tasks.sync.sync_all_sources',
        'schedule': crontab(hour=6, minute=0),
    },
    'dq-daily': {
        'task': 'tasks.dq.execute_dq_daily',
        'schedule': crontab(hour=7, minute=0),
    },
}
```

### When to Add Celery

- **Not needed**: Single user, manual operations, scripted via cron
- **Add when**: Team deployment, need visibility, want retries, web-triggered long operations

---

## 8. Frontend Architecture

### Directory Structure

```
frontend/src/
├── app/
│   ├── App.tsx           # Routes + providers
│   └── main.tsx          # Entry point
│
├── pages/                # Route components
│   ├── Home/
│   ├── Browse/
│   ├── ObjectDetail/
│   ├── DataQualityHub/
│   ├── DeprecationCampaigns/
│   └── index.ts          # Barrel export
│
├── features/             # Feature-based organization
│   ├── objects/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── api.ts
│   │   └── types.ts
│   │
│   ├── dq/
│   │   ├── components/
│   │   │   ├── DQChart.tsx
│   │   │   ├── BreachTable.tsx
│   │   │   ├── ExpectationForm.tsx
│   │   │   └── index.ts
│   │   ├── hooks/
│   │   │   ├── useDQConfig.ts
│   │   │   └── useBreaches.ts
│   │   ├── api.ts
│   │   └── types.ts
│   │
│   ├── lineage/
│   │   ├── components/
│   │   │   └── LineageGraph.tsx
│   │   ├── hooks/
│   │   └── utils/
│   │       └── layout.ts
│   │
│   └── deprecation/
│
├── shared/               # Cross-feature shared code
│   ├── components/
│   │   ├── ErrorBoundary.tsx
│   │   ├── LoadingSpinner.tsx
│   │   └── SourceSelector.tsx
│   ├── hooks/
│   │   ├── useCurrentSource.ts
│   │   └── usePagination.ts
│   ├── api/
│   │   └── client.ts     # Axios/fetch wrapper
│   └── utils/
│       └── format.ts
│
├── contexts/
│   ├── SourceContext.tsx
│   ├── ThemeContext.tsx
│   └── index.ts
│
└── types/
    └── index.ts          # Global types
```

### State Management Strategy

1. **Server State**: TanStack Query (React Query)
   - All API data fetching
   - Caching with 5-min stale time
   - Automatic background refetch
   - Query keys: `[resource, ...identifiers, ...filters]`

2. **URL State**: React Router
   - Search queries, filters, pagination
   - Bookmarkable, shareable URLs
   - Browser back/forward support

3. **Global App State**: React Context
   - Current data source selection (persisted)
   - Theme preference (persisted)

4. **Local Component State**: useState/useReducer
   - Modal visibility
   - Form state
   - UI-only state

### Component Guidelines

- **Max 300 lines per component** - Extract hooks and sub-components
- **Custom hooks for data fetching** - `useDQConfig()`, `useBreaches()`
- **Barrel exports** - `import { DQChart, BreachTable } from '@/features/dq'`
- **TypeScript strict mode** - No `any`, explicit return types
- **Functional components only** - No class components

---

## 9. Data Quality System Design

### Expectation Types

| Type | Level | Description | Applicable Types |
|------|-------|-------------|------------------|
| `row_count` | Table | Total rows in date range | All |
| `distinct_count` | Column | Count of unique values | All |
| `null_count` | Column | Count of NULL values | All |
| `max_length` | Column | Maximum string length | String types |
| `min` | Column | Minimum value | Numeric, Date |
| `max` | Column | Maximum value | Numeric, Date |
| `mean` | Column | Average value | Numeric |
| `sum` | Column | Sum of values | Numeric |
| `median` | Column | Median value | Numeric |

### Threshold Strategies

**1. Absolute**
```json
{
  "type": "absolute",
  "min": 1000,
  "max": null
}
```
- Fixed bounds
- Best for: Known acceptable ranges

**2. Simple Average**
```json
{
  "type": "simple_average",
  "multiplier": 2.0,
  "lookback_days": 90
}
```
- `threshold = mean ± (multiplier × stddev)`
- Uses all historical data (or last N days)
- Best for: Stable metrics without patterns

**3. Day-of-Week Adjusted**
```json
{
  "type": "dow_adjusted",
  "multiplier": 2.0,
  "lookback_days": 90
}
```
- Calculates DOW scaling factor: `dow_mean / overall_mean`
- `expected = overall_mean × dow_factor`
- `threshold = expected ± (multiplier × stddev)`
- Best for: Metrics with weekly patterns

### Breach Lifecycle

```
┌───────┐     acknowledge     ┌──────────────┐
│ OPEN  │ ──────────────────► │ ACKNOWLEDGED │
└───┬───┘                     └───────┬──────┘
    │                                 │
    │ dismiss (false positive)        │ dismiss
    │                                 │
    ▼                                 ▼
┌───────────┐                  ┌───────────┐
│ DISMISSED │ ◄────────────────│ DISMISSED │
└───────────┘                  └───────────┘
    │
    │ resolve (issue fixed)
    ▼
┌──────────┐
│ RESOLVED │ (immutable)
└──────────┘
```

### Breach Record Design

```python
class DQBreach:
    # Identity
    expectation_id: int
    snapshot_date: date

    # Actual value
    metric_value: float
    breach_direction: Literal["high", "low"]
    deviation_value: float   # Absolute: actual - threshold
    deviation_percent: float # Percentage deviation

    # Threshold snapshot (immutable JSON)
    threshold_snapshot: dict  # Complete config at detection time

    # Lifecycle
    status: BreachStatus
    lifecycle_events: list[dict]  # [{status, by, at, notes}, ...]

    # Timestamps
    detected_at: datetime
    created_at: datetime
```

---

## 10. Metadata Sync System Design

### Sync Phases

```
Phase 1: Core Objects (parallel by type)
├── Tables
├── Views
├── Materialized Views
├── Stored Procedures
├── Functions
├── Synonyms/Aliases
└── External Files (if supported)

Phase 2: Object Metadata (sequential, depends on Phase 1)
├── Columns
├── Constraints
└── Indexes

Phase 3: Dependencies (parallel by source)
├── Source-provided dependencies
├── SQL parsing (from code repositories)
└── File dependencies (for ETL tracking)

Phase 4: Statistics (parallel)
├── Object sizes
├── Usage statistics
└── Query statistics (if available)
```

### UPSERT Pattern

```python
def upsert_object(source_row: dict, source_id: int) -> Object:
    """
    UPSERT pattern: update source metadata, preserve user metadata.
    """
    key = (source_id, source_row["SCHEMA"], source_row["NAME"], source_row["TYPE"])

    existing = repo.get_by_natural_key(*key)

    if existing:
        # Update ONLY source-provided fields
        existing.source_metadata = {
            "row_count": source_row.get("ROW_COUNT"),
            "last_analyzed": source_row.get("LAST_ANALYZED"),
            "size_bytes": source_row.get("SIZE_BYTES"),
        }
        existing.updated_at = datetime.utcnow()
        return existing
    else:
        # Create new with empty user metadata
        return Object(
            source_id=source_id,
            schema_name=source_row["SCHEMA"],
            object_name=source_row["NAME"],
            object_type=source_row["TYPE"],
            source_metadata={...},
            user_metadata={"description": None, "tags": []},
        )
```

### Dependency Deduplication

When same dependency discovered from multiple parsing sources:

| Priority | Source | Use When |
|----------|--------|----------|
| 1 (highest) | file_log | ETL file → table mappings |
| 2 | sql_parsing | Code repository analysis |
| 3 | source_metadata | Database-provided dependencies |
| 4 | manual | User-defined relationships |

Keep highest priority source. Include confidence score for heuristic matches.

---

## 11. Search Implementation

### SQLite FTS5 (Local/Default)

```sql
-- Create FTS5 virtual table
CREATE VIRTUAL TABLE objects_fts USING fts5(
    object_name,
    description,
    tags,
    content='objects',
    content_rowid='id'
);

-- Search query
SELECT o.* FROM objects o
JOIN objects_fts fts ON o.id = fts.rowid
WHERE objects_fts MATCH 'customer*'
ORDER BY rank;
```

### PostgreSQL Full-Text (Production)

```sql
-- Create tsvector column
ALTER TABLE objects ADD COLUMN search_vector tsvector;

-- Generate from multiple fields
UPDATE objects SET search_vector =
    setweight(to_tsvector('english', coalesce(object_name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(user_metadata->>'description', '')), 'B') ||
    setweight(to_tsvector('english', coalesce(user_metadata->>'tags', '')), 'C');

-- GIN index for fast search
CREATE INDEX idx_objects_search ON objects USING GIN(search_vector);
```

### Search Features
- **Autocomplete**: Prefix matching on object_name
- **Fuzzy search**: Trigram similarity for typos (PostgreSQL)
- **Filters**: object_type, schema_name, source_id
- **Relevance ranking**: Weight: name > description > tags

### CLI Search

```bash
datacompass search "customer"
datacompass search "customer sales" --source prod --type TABLE
```

---

## 12. Authentication & Authorization

### Design Principle
Internal-only deployment with hooks for organizational verification. Architecture supports adding LDAP/OIDC later.

### Implementation

```python
# middleware/auth.py
class OrgVerificationMiddleware:
    """
    Verify user is part of the organization.
    Initially checks network/IP range, can be extended to LDAP/OIDC.
    """

    async def __call__(self, request: Request, call_next):
        # Phase 1: Network-based verification
        if not self.is_internal_network(request.client.host):
            raise HTTPException(403, "Access restricted to internal network")

        # Phase 2 (future): LDAP/OIDC verification
        # user = await self.verify_org_membership(request.headers.get("Authorization"))

        # Store user context for audit logging
        request.state.user = self.get_user_from_headers(request)
        return await call_next(request)
```

### Audit Trail Support
```python
class AuditMixin:
    """Mixin for tracking who made changes."""
    created_by: str | None  # Username/email from headers
    updated_by: str | None

# Usage in models
class Object(Base, AuditMixin):
    ...
```

### Extension Points for Future Auth
1. **Headers**: Accept `X-User-Email`, `X-User-Name` from reverse proxy
2. **Middleware slot**: Easy to add OIDC/LDAP verification
3. **Audit fields**: Track who made changes
4. **Permission hooks**: Can add role-based access later

---

## 13. Alerting & Notifications System

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  DQ Breach      │────►│  NotificationSvc │────►│  Channels       │
│  Detected       │     │                  │     │  - Email        │
└─────────────────┘     │  - Route by      │     │  - Slack        │
                        │    priority      │     │  - Webhook      │
┌─────────────────┐     │  - Deduplicate   │     └─────────────────┘
│  Sync Failed    │────►│  - Rate limit    │
└─────────────────┘     │  - Template      │
                        └──────────────────┘
```

### Notification Configuration

```python
# models/notification.py
class NotificationChannel(Base):
    id: int
    name: str  # "DQ Alerts Slack", "Critical Email"
    channel_type: str  # email, slack, webhook
    config: dict  # {"webhook_url": "...", "channel": "#alerts"}
    is_enabled: bool

class NotificationRule(Base):
    id: int
    name: str
    event_type: str  # breach_detected, sync_failed, campaign_created
    conditions: dict  # {"priority": [1, 2], "source_id": [1]}
    channel_id: int
    template: str | None  # Override default template
    is_enabled: bool
```

### Event Types

| Event | Trigger | Default Template |
|-------|---------|------------------|
| `breach_detected` | New DQ breach created | Priority-based severity |
| `breach_bulk` | Multiple breaches in single run | Summary digest |
| `sync_failed` | Metadata sync fails | Error details |
| `sync_completed` | Sync completes (opt-in) | Stats summary |
| `campaign_deadline` | Deprecation deadline approaching | Objects remaining |

### Notification Service

```python
# services/notification_service.py
class NotificationService:
    def __init__(self, channels: list[NotificationChannel]):
        self.handlers = {
            "email": EmailHandler(),
            "slack": SlackHandler(),
            "webhook": WebhookHandler(),
        }

    async def notify(self, event_type: str, payload: dict):
        """Route notification to appropriate channels based on rules."""
        rules = await self.get_matching_rules(event_type, payload)

        for rule in rules:
            # Rate limiting: max 1 notification per rule per 5 min
            if await self.is_rate_limited(rule.id):
                continue

            channel = rule.channel
            handler = self.handlers[channel.channel_type]

            message = self.render_template(rule.template, payload)
            await handler.send(channel.config, message)

            await self.log_notification(rule, payload)
```

### Slack Integration Example

```python
# handlers/slack.py
class SlackHandler:
    async def send(self, config: dict, message: NotificationMessage):
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": message.title}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Priority:* {message.priority}"},
                    {"type": "mrkdwn", "text": f"*Source:* {message.source}"},
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message.body}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in Data Compass"},
                        "url": message.link
                    }
                ]
            }
        ]

        await self.client.chat_postMessage(
            channel=config["channel"],
            blocks=blocks
        )
```

---

## 14. CLI Reference

### Command Structure

All capabilities are exposed via CLI commands. The CLI outputs JSON by default.

```bash
# Adapters
datacompass adapters list                 # List available adapter types
datacompass adapters schema <type>        # Show config schema for adapter

# Source Management
datacompass source add <name> --type <type> --config <path>
datacompass source apply <config-file>    # Apply sources from YAML
datacompass source list [--format table|json]
datacompass source remove <name>
datacompass source test <name>

# Scanning
datacompass scan <source>
datacompass scan <source> --full
datacompass scan --all

# Catalog Browsing
datacompass objects list --source <name> [--type TABLE] [--schema <schema>]
datacompass objects show <source>.<schema>.<name>
datacompass columns list <source>.<schema>.<table>

# Search
datacompass search "<query>" [--source <name>] [--type TABLE]

# Documentation
datacompass describe <object> "<description>"
datacompass tag <object> --add <tag>
datacompass tag <object> --remove <tag>

# Lineage
datacompass lineage <object> --direction upstream [--depth 3]
datacompass lineage <object> --direction downstream
datacompass lineage <object> --format dot  # GraphViz output

# Data Quality
datacompass dq init <object>              # Create config template
datacompass dq apply <config-file>        # Apply config from file
datacompass dq list                       # List configured objects
datacompass dq run <object>               # Execute DQ checks
datacompass dq run --all
datacompass dq backfill <object> --days 30
datacompass dq status <object>            # Current breach status
datacompass dq breaches list [--status open]

# Deprecation
datacompass deprecate campaign create <name> --target-date 2025-06-01
datacompass deprecate add <object> --campaign <name>
datacompass deprecate check <campaign>    # Show dependency warnings

# Classification
datacompass classify <object> --level confidential
datacompass classify <object> --compliance gdpr pci_dss
datacompass classify list --level restricted
datacompass classify rules apply <rules-file>

# Ownership
datacompass owner assign <object> --owner <user>
datacompass steward assign <object> --steward <user>
datacompass domain create <name> [--parent <domain>]
datacompass domain assign <object> --domain <name>

# Audit
datacompass audit log [--entity-type <type>] [--user <user>] [--since <date>]
datacompass audit export --format json --since <date>
```

### Output Modes

```bash
# JSON output (default, machine-readable)
datacompass objects list --source prod

# Table output (human-readable)
datacompass objects list --source prod --format table

# Quiet mode (minimal output for scripts)
datacompass scan prod --quiet
```

---

## 15. Configuration as Code

### Principle

The platform is driven by configuration files. A user can define their entire setup in version-controlled files and apply with a single command.

### Source Configuration (`sources.yaml`)

```yaml
sources:
  - name: production
    type: snowflake  # or bigquery, redshift, postgres, etc.
    config:
      account: ${SNOWFLAKE_ACCOUNT}
      warehouse: ANALYTICS_WH
      database: PROD
      schema: PUBLIC
      user: ${SNOWFLAKE_USER}
      password: ${SNOWFLAKE_PASSWORD}
    sync:
      enabled: true
      schedule: "0 6 * * *"

  - name: staging
    type: snowflake
    config:
      account: ${SNOWFLAKE_ACCOUNT}
      warehouse: DEV_WH
      database: STAGING
```

Apply with: `datacompass source apply sources.yaml`

### DQ Rules (`dq/customer_rules.yaml`)

```yaml
object: production.analytics.customers
date_column: updated_at
grain: daily

expectations:
  - type: row_count
    threshold:
      type: dow_adjusted
      multiplier: 2.0
    priority: critical

  - type: null_count
    column: email
    threshold:
      type: absolute
      max: 0
    priority: high

  - type: distinct_count
    column: customer_id
    threshold:
      type: simple_average
      multiplier: 2.0
    priority: medium
```

Apply with: `datacompass dq apply dq/customer_rules.yaml`

### Benefits

- **Version controlled** - Track changes in git
- **Reviewable** - PR-based workflow for rule changes
- **Reproducible** - Same config produces same setup
- **Scriptable** - CI/CD can apply configs automatically

---

## 16. API Design

### OpenAPI Specification

All endpoints have comprehensive OpenAPI documentation:

```python
# api/objects.py
@router.get(
    "/",
    response_model=PaginatedResponse[ObjectSummary],
    summary="List objects",
    description="List database objects with filtering and pagination.",
    responses={
        200: {"description": "List of objects"},
        400: {"description": "Invalid filter parameters"},
    },
    tags=["objects"],
)
async def list_objects(
    source_id: int = Query(..., description="Data source to query"),
    object_type: str | None = Query(None, description="Filter by type (TABLE, VIEW, etc)"),
    schema_name: str | None = Query(None, description="Filter by schema"),
    search: str | None = Query(None, description="Full-text search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[ObjectSummary]:
    ...
```

### API Versioning

```
/api/v1/objects/...   # Current version
/api/v2/objects/...   # Future breaking changes
```

### SDK Generation

Generate TypeScript client from OpenAPI spec:

```bash
# Generate TypeScript SDK
npx openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-fetch \
  -o frontend/src/generated/api
```

Generated types ensure frontend stays in sync:

```typescript
// generated/api/models/ObjectSummary.ts
export interface ObjectSummary {
    id: number;
    source_id: number;
    schema_name: string;
    object_name: string;
    object_type: ObjectType;
    source_metadata: SourceMetadata;
    user_metadata: UserMetadata;
}
```

### Standardized Response Envelope

```python
# schemas/responses.py
class APIResponse(BaseModel, Generic[T]):
    data: T | None
    meta: dict | None = None
    errors: list[APIError] | None = None

class PaginatedResponse(APIResponse[list[T]], Generic[T]):
    meta: PaginationMeta

class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
```

### API Documentation Portal

```python
# main.py
app = FastAPI(
    title="Data Compass API",
    description="Metadata catalog with DQ monitoring",
    version="1.0.0",
    docs_url="/api/docs",        # Swagger UI
    redoc_url="/api/redoc",      # ReDoc
    openapi_url="/api/openapi.json",
)
```

---

## 17. Technical Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | Terminal-first | Core library is the product; CLI, API, web are interfaces |
| **Local Storage** | SQLite (default) | Zero infrastructure, local-first, easy to start |
| **Production Storage** | PostgreSQL (optional) | For multi-user deployments needing concurrency |
| **Task Queue** | Celery + Redis (optional) | Only needed for scheduled/distributed operations |
| **Configuration** | YAML files | Version-controllable, reviewable, scriptable |
| **Output Format** | JSON default | Structured data for pipelines, human format optional |
| **Authentication** | Internal w/ org hooks | Network-based initially, LDAP/OIDC extensible |
| **Source Adapters** | Plugin pattern | Support multiple database types without core changes |
| **Notifications** | Email + Slack + Webhook | Multi-channel alerts for DQ breaches and sync failures |
| **Classification** | 4-level + compliance labels | Public/Internal/Confidential/Restricted + GDPR/HIPAA/etc |
| **Ownership** | Owner/Steward/Domain model | Clear accountability with domain hierarchy |
| **Access Control** | Scoped RBAC | Viewer/Editor/Steward/Admin with global/source/domain/object scope |
| **Audit** | Event-sourced log | All changes tracked with before/after snapshots |

---

## Appendix A: Supported Object Types

| Type | Description | Common In |
|------|-------------|-----------|
| `TABLE` | Physical data table | All databases |
| `VIEW` | Virtual table (query) | All databases |
| `MATERIALIZED_VIEW` | Cached query result | Most databases |
| `PROCEDURE` | Stored procedure | All databases |
| `FUNCTION` | User-defined function | All databases |
| `PACKAGE` | Procedure/function container | Some databases |
| `SYNONYM` | Alias to another object | Some databases |
| `SEQUENCE` | Auto-increment generator | Most databases |
| `INDEX` | Performance optimization | All databases |
| `FILE` | External file reference | ETL systems |

---

## Appendix B: DQ Metric SQL Patterns

These patterns are adapter-agnostic representations that adapters translate to source-specific SQL:

```python
# Table-level metrics
"row_count": "COUNT(*)"

# Column-level metrics
"distinct_count": "COUNT(DISTINCT {column})"
"null_count": "SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END)"
"max_length": "MAX(LENGTH({column}))"
"min": "MIN({column})"
"max": "MAX({column})"
"mean": "AVG({column})"
"sum": "SUM({column})"
"median": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {column})"
```

Adapters handle dialect-specific syntax (e.g., `LENGTH` vs `LEN`, `PERCENTILE_CONT` vs `MEDIAN`).
