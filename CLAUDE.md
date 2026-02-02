# Data Compass - AI Engineering Context

You are a staff-level software engineer working on Data Compass, a terminal-first metadata catalog with data quality monitoring and lineage visualization for cloud databases.

## Project Status

**Current State:** Phases 0-7 complete, Phase 8 (Scheduling) scaffolded

- **368 tests passing** across CLI, API, and core services
- **~17,500 lines of Python** implementing the core catalog
- **React frontend** with TanStack Query for data fetching
- **PostgreSQL and Databricks adapters** implemented; PostgreSQL is tested and production-ready

**Read `STATUS.md`** for detailed phase completion status and recent changes.

## Quick Reference

### Virtual Environment

**Always use the virtual environment for all Python operations:**

```bash
# Virtual environment location
.venv/

# Common commands
.venv/bin/pip install -e ".[dev]"     # Install package
.venv/bin/pytest tests/               # Run tests
.venv/bin/pytest tests/ -v --tb=short # Verbose with short traceback
.venv/bin/datacompass --help          # Run CLI
.venv/bin/ruff check src tests        # Lint code
.venv/bin/ruff format src tests       # Format code
.venv/bin/mypy src                    # Type check

# Start servers
.venv/bin/uvicorn datacompass.api:app --reload  # API server (port 8000)
cd frontend && npm run dev                       # Frontend (port 5173)
```

### Key CLI Commands

```bash
# Sources
.venv/bin/datacompass source add <name> --type postgresql --config <yaml>
.venv/bin/datacompass source list
.venv/bin/datacompass source test <name>
.venv/bin/datacompass scan <name> [--full]

# Objects
.venv/bin/datacompass objects list [--source <name>] [--type TABLE]
.venv/bin/datacompass objects show <source.schema.object>
.venv/bin/datacompass objects describe <object> --set "Description"
.venv/bin/datacompass objects tag <object> --add <tag>

# Search
.venv/bin/datacompass search "query" [--source <name>]
.venv/bin/datacompass reindex

# Lineage
.venv/bin/datacompass lineage <object> [--direction upstream|downstream] [--format tree]

# Data Quality
.venv/bin/datacompass dq init <object> --output dq/config.yaml
.venv/bin/datacompass dq apply dq/config.yaml
.venv/bin/datacompass dq run <object>
.venv/bin/datacompass dq run --all
.venv/bin/datacompass dq breaches list --status open

# Deprecation
.venv/bin/datacompass deprecate campaign create "Name" --source <name> --target-date YYYY-MM-DD
.venv/bin/datacompass deprecate add <object> --campaign <id>
.venv/bin/datacompass deprecate check <campaign-id>
```

### API Endpoints

```
GET  /health                              # Health check
GET  /api/v1/sources                      # List sources
POST /api/v1/sources                      # Create source
POST /api/v1/sources/{name}/scan          # Trigger scan
GET  /api/v1/objects                      # List objects
GET  /api/v1/objects/{id}                 # Object detail
GET  /api/v1/objects/{id}/lineage         # Lineage graph
GET  /api/v1/search?q=...                 # Full-text search
GET  /api/v1/dq/configs                   # List DQ configs
POST /api/v1/dq/configs/{id}/run          # Run DQ checks
GET  /api/v1/dq/breaches                  # List breaches
GET  /api/v1/deprecations/campaigns       # List campaigns
GET  /api/v1/deprecations/campaigns/{id}/impact  # Impact analysis
```

Interactive docs at http://localhost:8000/docs when server is running.

## Documentation

| Document | Purpose |
|----------|---------|
| [STATUS.md](STATUS.md) | Current phase, recent changes, next steps |
| [docs/architecture.md](docs/architecture.md) | System design, data flow, extension points |
| [docs/user-guide.md](docs/user-guide.md) | Feature walkthroughs and examples |
| [docs/cli-reference.md](docs/cli-reference.md) | Complete CLI command reference |
| [docs/api-reference.md](docs/api-reference.md) | REST API documentation |
| [docs/terminal-first-design-philosophy.md](docs/terminal-first-design-philosophy.md) | Core architectural principles |
| [docs/adapter-implementation-guide.md](docs/adapter-implementation-guide.md) | Building source adapters |
| [specs/foundation/technical-specification.md](specs/foundation/technical-specification.md) | Original spec (reference only) |

## Architecture

### Layer Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    Web UI (React)                           │
│              frontend/src/pages/*.tsx                       │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                   REST API (FastAPI)                        │
│              src/datacompass/api/routes/*.py                │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                      CLI (Typer)                            │
│              src/datacompass/cli/main.py                    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Core Library                             │
│                                                             │
│  Services (business logic)                                  │
│    src/datacompass/core/services/                           │
│    ├── catalog_service.py      # Scan, object CRUD         │
│    ├── search_service.py       # FTS5 search               │
│    ├── lineage_service.py      # Dependency graph          │
│    ├── dq_service.py           # Data quality              │
│    ├── deprecation_service.py  # Campaign management       │
│    ├── scheduling_service.py   # Job scheduling            │
│    └── notification_service.py # Alerts                    │
│                                                             │
│  Repositories (data access)                                 │
│    src/datacompass/core/repositories/                       │
│                                                             │
│  Models (SQLAlchemy + Pydantic)                            │
│    src/datacompass/core/models/                             │
│                                                             │
│  Adapters (source plugins)                                  │
│    src/datacompass/core/adapters/                           │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              SQLite (local) / PostgreSQL (prod)             │
└─────────────────────────────────────────────────────────────┘
```

### Key Principle: Core Library is the Product

All business logic lives in `src/datacompass/core/services/`. CLI commands and API routes are thin wrappers that:
1. Parse input
2. Call service methods
3. Format output

**If you're writing business logic in a CLI command or API route, stop.** Move it to a service.

### Project Structure

```
data-compass/
├── src/datacompass/
│   ├── __init__.py              # Version: 0.1.0
│   ├── cli/
│   │   ├── main.py              # All CLI commands
│   │   └── helpers.py           # Output formatting, session management
│   ├── api/
│   │   ├── app.py               # FastAPI app factory
│   │   ├── dependencies.py      # Dependency injection
│   │   ├── exceptions.py        # Exception handlers
│   │   ├── schemas.py           # Request schemas
│   │   └── routes/              # Route modules by resource
│   ├── config/
│   │   └── settings.py          # Pydantic settings
│   └── core/
│       ├── adapters/            # Source adapters (plugin pattern)
│       │   ├── base.py          # SourceAdapter ABC
│       │   ├── registry.py      # Adapter registration
│       │   ├── postgresql.py    # PostgreSQL implementation (tested)
│       │   └── databricks.py    # Databricks implementation
│       ├── models/              # SQLAlchemy models + Pydantic schemas
│       │   ├── data_source.py
│       │   ├── catalog_object.py
│       │   ├── column.py
│       │   ├── dependency.py
│       │   ├── dq.py
│       │   ├── deprecation.py
│       │   └── scheduling.py
│       ├── repositories/        # Data access layer
│       ├── services/            # Business logic
│       └── migrations/          # Alembic migrations
│           └── versions/
├── frontend/                    # React + Vite + Ant Design
│   ├── src/
│   │   ├── api/                 # API client + types
│   │   ├── hooks/               # TanStack Query hooks
│   │   ├── components/          # Reusable components
│   │   └── pages/               # Page components
│   └── package.json
├── tests/
│   ├── core/                    # Service + repository tests
│   ├── cli/                     # CLI integration tests
│   └── api/                     # API integration tests
├── docs/                        # Documentation
├── specs/                       # Original specifications
└── pyproject.toml               # Project config
```

## Database Schema

Six migrations define the schema:

| Migration | Tables |
|-----------|--------|
| 001_initial | `data_sources`, `catalog_objects`, `columns` |
| 002_fts5 | `catalog_objects_fts` (FTS5 virtual table) |
| 003_lineage | `dependencies` |
| 004_data_quality | `dq_configs`, `dq_expectations`, `dq_results`, `dq_breaches` |
| 005_deprecation | `deprecation_campaigns`, `deprecations` |
| 006_scheduling | `schedules`, `schedule_runs`, `notification_channels`, `notification_rules`, `notification_log` |

Run migrations: `.venv/bin/alembic upgrade head`

## Core Principles

### Terminal-First

Every feature must work from the CLI before it gets an API endpoint or web UI:

```bash
# This pattern must always work
.venv/bin/datacompass <command> --format json | jq '...'
```

### Configuration as Code

Sources and DQ rules are defined in YAML files:

```yaml
# Source config (PostgreSQL example)
connection:
  host: ${POSTGRES_HOST}
  port: 5432
  database: ${POSTGRES_DATABASE}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASSWORD}

# DQ config
object: source.schema.table
expectations:
  - type: row_count
    threshold_strategy: dow_adjusted
```

### Output is Data

CLI output is JSON by default. Human-readable tables are `--format table`. This makes the CLI immediately useful in pipelines.

### Idempotent Operations

All operations are safe to re-run:
- Scans use UPSERT logic
- DQ checks create new results, don't modify old ones
- Search index rebuilds are atomic

## Code Standards

### Python

- **Type hints** on all public functions
- **Docstrings** on public classes and functions
- **`pathlib.Path`** not string paths
- **Async** for adapters; services wrap with `asyncio.run()`

### Patterns

**Services:**
```python
class MyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = MyRepository(session)

    def do_something(self, ...) -> ResultModel:
        # Business logic here
        return result
```

**CLI Commands:**
```python
@app.command()
def my_command(
    arg: Annotated[str, typer.Argument(help="...")],
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.json,
) -> None:
    """Command description."""
    try:
        with get_session() as session:
            service = MyService(session)
            result = service.do_something(arg)
            session.commit()
            output_result(result.model_dump(), format)
    except MyError as e:
        handle_error(e)
```

**API Routes:**
```python
@router.get("/resource", response_model=list[ResponseModel])
async def list_resources(
    service: MyServiceDep,
    filter: str | None = None,
) -> list[ResponseModel]:
    """Endpoint description."""
    return service.list_resources(filter=filter)
```

## Testing

### Running Tests

```bash
# All tests
.venv/bin/pytest tests/

# Specific area
.venv/bin/pytest tests/core/services/
.venv/bin/pytest tests/cli/
.venv/bin/pytest tests/api/

# Single test file
.venv/bin/pytest tests/core/services/test_catalog_service.py -v

# With coverage
.venv/bin/pytest tests/ --cov=datacompass --cov-report=term-missing
```

### Test Structure

Tests mirror the source structure:
- `tests/core/services/` - Service unit tests
- `tests/core/repositories/` - Repository tests
- `tests/cli/` - CLI integration tests
- `tests/api/` - API integration tests

### Fixtures

Common fixtures in `tests/conftest.py`:
- `session` - In-memory SQLite session
- `source` - Test data source
- `catalog_object` - Test catalog object

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATACOMPASS_DATA_DIR` | `~/.datacompass` | Data directory |
| `DATACOMPASS_DATABASE_URL` | `sqlite:///{data_dir}/datacompass.db` | Database URL |
| `DATACOMPASS_DEFAULT_FORMAT` | `json` | CLI output format |
| `DATACOMPASS_LOG_LEVEL` | `INFO` | Log level |

## Build Order (Remaining Phases)

```
Phase 8: Scheduling    → Cron jobs, notifications (scaffolded)
Phase 9: Production    → Auth, observability, hardening
Phase 10: Governance   → Classification, ownership, RBAC
```

## Anti-Patterns to Avoid

- **Business logic in CLI/API** - Move to services
- **Direct DB queries in routes** - Use repositories
- **Web-only features** - CLI must work first
- **Interactive prompts** - CLI should be scriptable
- **PostgreSQL-only features** - Keep SQLite compatible

## When Adding Features

1. **Design the CLI command first** - What's the user interface?
2. **Implement in core service** - Business logic goes here
3. **Add repository methods** - If new data access needed
4. **Create CLI command** - Thin wrapper around service
5. **Add API endpoint** - Thin wrapper around service
6. **Add frontend** - Calls API, displays results
7. **Write tests** - Services first, then CLI/API integration

## Troubleshooting

### Tests Failing

```bash
# Check if DB needs migration
.venv/bin/alembic upgrade head

# Reinstall package
.venv/bin/pip install -e ".[dev]"
```

### Import Errors

```bash
# Ensure package is installed in editable mode
.venv/bin/pip install -e ".[dev]"
```

### Frontend Not Loading

```bash
# Check API is running
curl http://localhost:8000/health

# Check frontend proxy config in vite.config.ts
```
