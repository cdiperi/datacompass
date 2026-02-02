# Data Compass

**Terminal-first metadata catalog with data quality monitoring and lineage visualization.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Data Compass is a metadata catalog that helps you understand, document, and monitor your data. Built with a terminal-first philosophy, every feature works from the command line before it gets a web interface.

## Features

- **Metadata Catalog** - Scan data sources to discover tables, views, and columns with their types and statistics
- **Full-Text Search** - Find any object in your catalog with instant, typo-tolerant search using SQLite FTS5
- **Lineage Tracking** - Visualize upstream dependencies and downstream impact of your data assets
- **Data Quality Monitoring** - Define expectations, track metrics over time, and detect breaches automatically
- **Deprecation Campaigns** - Plan and communicate data deprecations with impact analysis
- **Scheduling** - Automate scans, DQ checks, and notifications with cron expressions
- **Configuration as Code** - Define sources and rules in version-controlled YAML files
- **JSON Output** - All commands output JSON by default for pipeline integration

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web UI (React)                           │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                      REST API (FastAPI)                         │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        CLI (Typer)                              │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                     Core Library                                │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │  Catalog  │  │  Lineage  │  │    DQ     │  │Deprecation│    │
│  │  Service  │  │  Service  │  │  Service  │  │  Service  │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Repositories                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Adapters (Databricks, more coming...)           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                SQLite (local) / PostgreSQL (prod)               │
└─────────────────────────────────────────────────────────────────┘
```

The core library contains all business logic. CLI, API, and Web are thin interfaces.

## Quick Start

### Installation

```bash
pip install datacompass
```

For development installation:

```bash
git clone https://github.com/yourorg/data-compass.git
cd data-compass
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### First Steps

```bash
# Verify installation
datacompass --version

# Add a data source
datacompass source add prod --type databricks --config prod.yaml

# Scan to populate the catalog
datacompass scan prod

# Browse objects
datacompass objects list --source prod

# Search the catalog
datacompass search "customer"

# View object details
datacompass objects show prod.analytics.customers

# Explore lineage
datacompass lineage prod.analytics.customers --direction upstream --format tree
```

## Configuration

### Source Configuration (YAML)

Create a YAML file to configure your data source:

```yaml
# prod.yaml
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

Environment variables are substituted at runtime using `${VAR}` syntax.

### Data Quality Configuration

```yaml
# dq/orders.yaml
object: demo.core.orders
date_column: created_at
grain: daily
enabled: true

expectations:
  - type: row_count
    warn_threshold: 10000
    error_threshold: 5000
    priority: high

  - type: null_count
    column: customer_id
    error_threshold: 0
    priority: critical
```

Apply configurations:

```bash
datacompass dq apply dq/orders.yaml
datacompass dq run demo.core.orders
```

## CLI Reference

### Source Management

```bash
# Add a source
datacompass source add <name> --type <adapter> --config <yaml>

# List sources
datacompass source list

# Test connection
datacompass source test <name>

# Remove source
datacompass source remove <name>
```

### Catalog Operations

```bash
# Scan a source
datacompass scan <source> [--full]

# List objects
datacompass objects list [--source <name>] [--type TABLE|VIEW] [--schema <name>]

# Show object details
datacompass objects show <source.schema.object>

# Manage descriptions
datacompass objects describe <object> --set "Description text"

# Manage tags
datacompass objects tag <object> --add pii --add core
datacompass objects tag <object> --remove deprecated
```

### Search

```bash
# Full-text search
datacompass search "customer"

# With filters
datacompass search "orders" --source prod --type TABLE

# Rebuild index
datacompass reindex
```

### Lineage

```bash
# View upstream dependencies
datacompass lineage <object> --direction upstream

# View downstream impact
datacompass lineage <object> --direction downstream

# With depth and format
datacompass lineage <object> --depth 5 --format tree
```

### Data Quality

```bash
# Generate template
datacompass dq init <object> --output dq/config.yaml

# Apply configuration
datacompass dq apply dq/config.yaml

# Run checks
datacompass dq run <object>
datacompass dq run --all

# View status
datacompass dq status
datacompass dq status <object>

# Manage breaches
datacompass dq breaches list [--status open]
datacompass dq breaches show <id>
datacompass dq breaches update <id> --status acknowledged
```

### Deprecation Campaigns

```bash
# Create campaign
datacompass deprecate campaign create "Q2 Cleanup" --source prod --target-date 2025-06-01

# Add objects
datacompass deprecate add <object> --campaign <id> --replacement <new-object>

# Check impact
datacompass deprecate check <campaign-id> --depth 3

# List campaigns
datacompass deprecate campaign list [--status active]
```

### Output Formats

All commands default to JSON output. Use `--format table` for human-readable output:

```bash
# JSON (default, for pipelines)
datacompass objects list --source prod | jq '.[0]'

# Table (for humans)
datacompass objects list --source prod --format table
```

## API Server

Start the API server:

```bash
uvicorn datacompass.api:app --reload
```

The API is available at `http://localhost:8000`:

- **Interactive docs**: http://localhost:8000/docs
- **OpenAPI spec**: http://localhost:8000/openapi.json

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/sources` | List sources |
| `POST /api/v1/sources/{name}/scan` | Trigger scan |
| `GET /api/v1/objects` | List objects |
| `GET /api/v1/objects/{id}` | Object details |
| `GET /api/v1/search?q=...` | Search catalog |
| `GET /api/v1/objects/{id}/lineage` | Get lineage |
| `GET /api/v1/dq/configs` | List DQ configs |
| `POST /api/v1/dq/configs/{id}/run` | Run DQ checks |
| `GET /api/v1/deprecations/campaigns` | List campaigns |

## Web Interface

Start the frontend development server:

```bash
cd frontend
npm install
npm run dev
```

The web UI runs at `http://localhost:5173` and proxies API requests to the backend.

Build for production:

```bash
npm run build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATACOMPASS_DATA_DIR` | `~/.datacompass` | Data directory location |
| `DATACOMPASS_DATABASE_URL` | `sqlite:///{data_dir}/datacompass.db` | Database connection URL |
| `DATACOMPASS_DEFAULT_FORMAT` | `json` | Default CLI output format |
| `DATACOMPASS_LOG_LEVEL` | `INFO` | Logging verbosity |

## Development

```bash
# Install with all dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=datacompass --cov-report=term-missing

# Lint
ruff check src tests

# Type check
mypy src

# Format
ruff format src tests
```

### Project Structure

```
data-compass/
├── src/datacompass/
│   ├── cli/              # CLI commands (Typer)
│   ├── api/              # REST API (FastAPI)
│   ├── config/           # Settings
│   └── core/             # Business logic
│       ├── adapters/     # Source adapters
│       ├── models/       # Domain models
│       ├── repositories/ # Data access
│       └── services/     # Business logic
├── frontend/             # React web UI
├── tests/                # Test suite
├── docs/                 # Documentation
└── specs/                # Design specifications
```

## Documentation

- [User Guide](docs/user-guide.md) - Getting started and feature walkthroughs
- [CLI Reference](docs/cli-reference.md) - Complete command documentation
- [API Reference](docs/api-reference.md) - REST API documentation
- [Architecture](docs/architecture.md) - System design and extension points
- [Adapter Guide](docs/adapter-implementation-guide.md) - Building source adapters
- [Design Philosophy](docs/terminal-first-design-philosophy.md) - Architectural principles

## Adapters

Currently supported:

- **Databricks** - Unity Catalog metadata extraction

Coming soon:

- Snowflake
- BigQuery
- PostgreSQL
- dbt

See the [Adapter Guide](docs/adapter-implementation-guide.md) for building custom adapters.

## License

MIT License - see [LICENSE](LICENSE) for details.
