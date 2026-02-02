# Architecture Overview

This document describes the architecture of Data Compass, a terminal-first metadata catalog with data quality monitoring and lineage visualization.

## Design Philosophy

Data Compass is built on several core principles documented in [terminal-first-design-philosophy.md](terminal-first-design-philosophy.md):

1. **The core library is the product** - All business logic lives in the core. CLI, API, and Web are thin interfaces.
2. **Every feature works headlessly first** - No capability requires a browser to function.
3. **Output is structured data by default** - JSON is the native format; human formatting is optional.
4. **Configuration is code** - Sources and rules live in version-controlled YAML files.
5. **Connectors are plugins** - The core is source-agnostic.
6. **Operations are idempotent** - Safe to re-run, safe to automate.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Interfaces                                    │
├───────────────────┬───────────────────┬─────────────────────────────────────┤
│    CLI (Typer)    │  REST API (Fast   │        Web UI (React)               │
│                   │     API)          │                                     │
│  - Human/script   │  - Machine        │  - Visual browsing                  │
│    interaction    │    integration    │  - Graph exploration                │
│  - JSON/table     │  - OpenAPI spec   │  - Collaborative features           │
│    output         │  - CORS enabled   │  - Dashboards                       │
└─────────┬─────────┴─────────┬─────────┴──────────────────┬──────────────────┘
          │                   │                            │
          │                   │                            │
          ▼                   ▼                            │
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Core Library                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          Services                                    │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ Catalog  │ │ Search   │ │ Lineage  │ │   DQ     │ │Deprecate │  │   │
│  │  │ Service  │ │ Service  │ │ Service  │ │ Service  │ │ Service  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌───────────────────┐  │   │
│  │  │Scheduling│ │ Notify   │ │Documentation │ │  Source Service   │  │   │
│  │  │ Service  │ │ Service  │ │   Service    │ │                   │  │   │
│  │  └──────────┘ └──────────┘ └──────────────┘ └───────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┴───────────────────────────────────┐   │
│  │                        Repositories                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ Source   │ │ Object   │ │Dependency│ │   DQ     │ │Deprecate │  │   │
│  │  │   Repo   │ │   Repo   │ │   Repo   │ │   Repo   │ │   Repo   │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │   │
│  │  │ Schedule │ │ Notify   │ │  Search  │                            │   │
│  │  │   Repo   │ │   Repo   │ │   Repo   │                            │   │
│  │  └──────────┘ └──────────┘ └──────────┘                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┴───────────────────────────────────┐   │
│  │                          Models                                      │   │
│  │  DataSource | CatalogObject | Column | Dependency | DQConfig        │   │
│  │  DQExpectation | DQResult | DQBreach | DeprecationCampaign          │   │
│  │  Deprecation | Schedule | NotificationChannel | NotificationRule    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Adapters (Plugins)                            │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │   │
│  │  │ Databricks │  │ Snowflake  │  │  BigQuery  │  │ PostgreSQL │    │   │
│  │  │  Adapter   │  │  (future)  │  │  (future)  │  │  (future)  │    │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Database Layer                                      │
│           SQLite (local development) / PostgreSQL (production)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Catalog Scan Flow

```
User runs: datacompass scan prod
    │
    ▼
CLI parses arguments, creates CatalogService
    │
    ▼
CatalogService.scan_source("prod")
    │
    ├─► SourceService loads source configuration
    │
    ├─► AdapterRegistry creates appropriate adapter
    │
    ├─► Adapter connects to data source
    │
    ├─► Adapter.get_objects() fetches metadata
    │
    ├─► Adapter.get_columns() fetches column info
    │
    ├─► ObjectRepository.upsert_objects() saves to DB
    │
    ├─► SearchService.reindex() updates FTS index
    │
    └─► Returns ScanResult with statistics
```

### Search Flow

```
User runs: datacompass search "customer"
    │
    ▼
CLI creates SearchService
    │
    ▼
SearchService.search("customer")
    │
    ├─► SearchRepository queries FTS5 index
    │
    ├─► BM25 ranking applied
    │
    └─► Returns list of SearchResult
```

## Core Library

### Services

Services contain all business logic. They are the primary interface for operations.

| Service | Responsibility |
|---------|---------------|
| `CatalogService` | Scan sources, manage catalog objects, CRUD operations |
| `SourceService` | Manage data source configurations |
| `SearchService` | Full-text search, index management |
| `DocumentationService` | Object descriptions and tags |
| `LineageService` | Dependency graph traversal |
| `DQService` | Data quality configs, expectations, runs, breaches |
| `DeprecationService` | Deprecation campaigns, impact analysis |
| `SchedulingService` | Job scheduling, cron management |
| `NotificationService` | Notification channels and rules |

Services follow these patterns:
- Accept a database session in constructor
- Wrap async adapter calls with `asyncio.run()` for sync CLI
- Raise domain-specific exceptions (e.g., `ObjectNotFoundError`)
- Return Pydantic models for type safety

### Repositories

Repositories encapsulate data access patterns using SQLAlchemy.

```python
class ObjectRepository:
    """Data access for CatalogObject entities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, object_id: int) -> CatalogObject | None:
        return self.session.get(CatalogObject, object_id)

    def upsert(self, source_id: int, objects: list[dict]) -> int:
        """Insert or update objects, returns count."""
        # UPSERT logic using SQLAlchemy
```

Key responsibilities:
- CRUD operations for entities
- Complex queries (e.g., lineage graph traversal)
- Upsert logic for scan operations
- FTS5 index management

### Models

Models are SQLAlchemy ORM classes representing database entities.

```python
class CatalogObject(Base):
    __tablename__ = "catalog_objects"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    schema_name: Mapped[str] = mapped_column(String(255))
    object_name: Mapped[str] = mapped_column(String(255))
    object_type: Mapped[str] = mapped_column(String(50))
    source_metadata: Mapped[dict | None] = mapped_column(JSON)
    user_metadata: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    source: Mapped["DataSource"] = relationship(back_populates="objects")
    columns: Mapped[list["Column"]] = relationship(back_populates="object")
```

Each model module also exports Pydantic schemas for API responses:

```python
class CatalogObjectResponse(BaseModel):
    """API response schema for catalog objects."""
    id: int
    source_name: str
    schema_name: str
    object_name: str
    object_type: str
    description: str | None
    tags: list[str]
```

### Adapters

Adapters are plugins that know how to communicate with specific data sources.

```python
class SourceAdapter(ABC):
    """Abstract interface for data source adapters."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...

    @abstractmethod
    async def get_objects(
        self, object_types: list[str] | None = None
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_columns(
        self, objects: list[tuple[str, str]]
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def execute_query(self, query: str) -> list[dict[str, Any]]: ...
```

Adapters are registered via decorator:

```python
@AdapterRegistry.register("databricks", "Databricks", ["TABLE", "VIEW"])
class DatabricksAdapter(SourceAdapter):
    ...
```

See [adapter-implementation-guide.md](adapter-implementation-guide.md) for building custom adapters.

## Database Schema

Data Compass uses SQLite for local development and supports PostgreSQL for production.

### Core Tables

```
data_sources
├── id (PK)
├── name (unique)
├── display_name
├── source_type
├── connection_info (JSON)
├── sync_config (JSON)
├── is_active
├── last_scan_at
├── last_scan_status
└── timestamps

catalog_objects
├── id (PK)
├── source_id (FK → data_sources)
├── schema_name
├── object_name
├── object_type
├── source_metadata (JSON)
├── user_metadata (JSON)
├── deleted_at
└── timestamps

columns
├── id (PK)
├── object_id (FK → catalog_objects)
├── column_name
├── position
├── source_metadata (JSON)
└── user_metadata (JSON)
```

### Search (FTS5)

```
catalog_objects_fts (FTS5 virtual table)
├── rowid → catalog_objects.id
├── source_name
├── schema_name
├── object_name
├── object_type
├── description
└── tags
```

### Lineage

```
dependencies
├── id (PK)
├── source_object_id (FK → catalog_objects)
├── target_object_id (FK → catalog_objects, nullable)
├── target_external (JSON, for external refs)
├── dependency_type
├── parsing_source
└── timestamps
```

### Data Quality

```
dq_configs
├── id (PK)
├── object_id (FK → catalog_objects)
├── date_column
├── grain
├── is_enabled
└── timestamps

dq_expectations
├── id (PK)
├── config_id (FK → dq_configs)
├── expectation_type
├── column_name
├── threshold_strategy
├── params (JSON)
└── priority

dq_results
├── id (PK)
├── expectation_id (FK → dq_expectations)
├── snapshot_date
├── metric_value
├── threshold values
├── status
└── timestamps

dq_breaches
├── id (PK)
├── result_id (FK → dq_results)
├── status
├── priority
├── event_log (JSON)
└── timestamps
```

### Deprecation

```
deprecation_campaigns
├── id (PK)
├── source_id (FK → data_sources)
├── name
├── description
├── status (draft/active/completed)
├── target_date
└── timestamps

deprecations
├── id (PK)
├── campaign_id (FK → deprecation_campaigns)
├── object_id (FK → catalog_objects)
├── replacement_object_id (FK, nullable)
├── notes
└── timestamps
```

### Scheduling

```
schedules
├── id (PK)
├── name (unique)
├── job_type
├── target_id
├── cron_expression
├── is_enabled
├── params (JSON)
└── timestamps

notification_channels
├── id (PK)
├── name (unique)
├── channel_type
├── config (JSON)
└── is_enabled

notification_rules
├── id (PK)
├── name
├── event_type
├── channel_id (FK → notification_channels)
├── filters (JSON)
└── is_enabled
```

## CLI Layer

The CLI uses Typer for argument parsing and Rich for output formatting.

```
datacompass
├── source (group)
│   ├── add
│   ├── list
│   ├── test
│   └── remove
├── objects (group)
│   ├── list
│   ├── show
│   ├── describe
│   └── tag
├── scan (command)
├── search (command)
├── reindex (command)
├── lineage (command)
├── dq (group)
│   ├── init
│   ├── apply
│   ├── list
│   ├── run
│   ├── status
│   └── breaches (subgroup)
├── deprecate (group)
│   ├── campaign (subgroup)
│   ├── add
│   ├── remove
│   ├── list
│   └── check
├── schedule (group)
├── scheduler (group)
├── notify (group)
└── adapters (group)
```

CLI commands follow this pattern:

```python
@app.command()
def scan(
    source: Annotated[str, typer.Argument(help="Source name")],
    full: Annotated[bool, typer.Option(help="Full scan")] = False,
    format: Annotated[OutputFormat, typer.Option()] = OutputFormat.json,
) -> None:
    """Scan a data source to update the catalog."""
    try:
        with get_session() as session:
            service = CatalogService(session)
            result = service.scan_source(source, full=full)
            session.commit()
            output_result(result.model_dump(), format)
    except Exception as e:
        handle_error(e)
```

Key patterns:
- All commands support `--format json|table`
- JSON is the default output format
- Errors go to stderr with appropriate exit codes
- Commands are thin wrappers around services

## API Layer

The API uses FastAPI with automatic OpenAPI documentation.

### Route Structure

```
/health                           # Health check
/api/v1/sources                   # Source management
/api/v1/sources/{name}/scan       # Trigger scan
/api/v1/objects                   # Object CRUD
/api/v1/objects/{id}              # Object detail
/api/v1/objects/{id}/lineage      # Lineage graph
/api/v1/search                    # Full-text search
/api/v1/dq/...                    # Data quality
/api/v1/deprecations/...          # Deprecation campaigns
/api/v1/schedules/...             # Job scheduling
/api/v1/notifications/...         # Notification management
```

### Dependency Injection

```python
def get_db() -> Generator[Session, None, None]:
    """Database session dependency."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@router.get("/objects")
def list_objects(
    session: Annotated[Session, Depends(get_db)],
    source: str | None = None,
    object_type: str | None = None,
) -> list[CatalogObjectResponse]:
    service = CatalogService(session)
    return service.list_objects(source=source, object_type=object_type)
```

### Exception Handling

```python
@app.exception_handler(ObjectNotFoundError)
def object_not_found_handler(request: Request, exc: ObjectNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )
```

## Web Layer

The frontend is a React SPA using:
- **Vite** - Build tool
- **React 19** - UI framework
- **TanStack Query** - Server state management
- **React Router** - Client-side routing
- **Ant Design** - Component library

### Structure

```
frontend/src/
├── api/
│   ├── client.ts        # Fetch wrapper
│   └── types.ts         # TypeScript types
├── hooks/
│   ├── useSources.ts    # Source queries
│   ├── useObjects.ts    # Object queries
│   ├── useSearch.ts     # Search queries
│   ├── useLineage.ts    # Lineage queries
│   ├── useDQ.ts         # DQ queries
│   └── useDeprecation.ts
├── components/
│   ├── Layout.tsx       # App shell
│   ├── SearchBar.tsx    # Global search
│   ├── ObjectTable.tsx  # Object list
│   └── ...
└── pages/
    ├── HomePage.tsx
    ├── BrowsePage.tsx
    ├── ObjectDetailPage.tsx
    ├── DQHubPage.tsx
    └── DeprecationHubPage.tsx
```

### Data Fetching Pattern

```typescript
// hooks/useObjects.ts
export function useObjects(filters: ObjectFilters) {
  return useQuery({
    queryKey: ['objects', filters],
    queryFn: () => fetchObjects(filters),
  });
}

// Usage in component
function ObjectTable() {
  const { data, isLoading, error } = useObjects({ source: 'prod' });
  // ...
}
```

## Extension Points

### Adding a New Adapter

1. Create adapter class implementing `SourceAdapter`
2. Create Pydantic config schema
3. Register with `@AdapterRegistry.register`
4. Add to exports in `adapters/__init__.py`

See [adapter-implementation-guide.md](adapter-implementation-guide.md).

### Adding a New Service

1. Create service class in `core/services/`
2. Create repository if new entities needed
3. Add CLI commands in `cli/main.py`
4. Add API routes in `api/routes/`
5. Export from `core/services/__init__.py`

### Adding New DQ Metrics

1. Add metric type to `DQExpectationType` enum
2. Implement collection logic in adapter's `execute_dq_query`
3. Add threshold computation in `DQService`

### Adding Notification Channels

1. Add channel type to `NotificationChannelType` enum
2. Create channel class implementing delivery
3. Register in `NotificationService`

## Testing Strategy

Tests are organized to mirror the architecture:

```
tests/
├── core/
│   ├── services/          # Service unit tests
│   ├── repositories/      # Repository tests
│   └── adapters/          # Adapter tests
├── cli/                   # CLI integration tests
├── api/                   # API integration tests
└── conftest.py            # Shared fixtures
```

### Testing Pyramid

1. **Unit tests** - Core services and repositories
2. **Integration tests** - CLI commands, API endpoints
3. **Component tests** - Frontend components (Vitest)

### Fixtures

```python
@pytest.fixture
def session():
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture
def catalog_service(session):
    return CatalogService(session)
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATACOMPASS_DATA_DIR` | `~/.datacompass` | Data directory |
| `DATACOMPASS_DATABASE_URL` | `sqlite:///{data_dir}/datacompass.db` | Database URL |
| `DATACOMPASS_DEFAULT_FORMAT` | `json` | CLI output format |
| `DATACOMPASS_LOG_LEVEL` | `INFO` | Log level |

### Source Configuration (YAML)

```yaml
connection:
  host: ${DATABRICKS_HOST}
  http_path: ${DATABRICKS_HTTP_PATH}
  token: ${DATABRICKS_TOKEN}

catalogs:
  - name: analytics
    schemas:
      - core
      - reporting
```

### DQ Configuration (YAML)

```yaml
object: source.schema.table
date_column: created_at
grain: daily
enabled: true

expectations:
  - type: row_count
    threshold_strategy: dow_adjusted
    lookback_days: 28
    priority: high
```

## Migrations

Database migrations use Alembic.

```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision -m "description"
```

Migration files are in `src/datacompass/core/migrations/versions/`.
