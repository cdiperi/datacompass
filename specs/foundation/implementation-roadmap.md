# Data Compass - Implementation Roadmap

## Overview

This document provides an ordered implementation guide for building Data Compass from scratch. It follows the **terminal-first design philosophy**: build the core library, expose via CLI, add API layer, then web interface.

Each phase is independently testable and delivers working functionality before moving to the next.

---

## Architecture Reminder

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Interface                          │
│           (Visualization, collaboration, dashboards)        │
└─────────────────────────────────┬───────────────────────────┘
                                  │ calls
┌─────────────────────────────────▼───────────────────────────┐
│                        API Layer                            │
│              (HTTP translation of core capabilities)        │
└─────────────────────────────────┬───────────────────────────┘
                                  │ calls
┌─────────────────────────────────▼───────────────────────────┐
│                           CLI                               │
│                  (First-class product surface)              │
└─────────────────────────────────┬───────────────────────────┘
                                  │ calls
┌─────────────────────────────────▼───────────────────────────┐
│                      Core Library                           │
│    (ALL business logic: scanning, DQ, lineage, search)      │
└─────────────────────────────────────────────────────────────┘
```

**Key principle**: The core library is the product. CLI, API, and web are interfaces to it.

---

## Phase 0: Project Setup

**Goal**: Establish project structure, tooling, and development environment.

### Tasks

- [ ] Initialize repository structure
- [ ] Set up Python package structure for core library
- [ ] Set up CLI framework (consider: Click, Typer, or similar)
- [ ] Configure development tooling (linting, formatting, testing)
- [ ] Set up local SQLite for catalog storage
- [ ] Create configuration file schema (YAML/TOML)
- [ ] Write initial README with setup instructions

### Deliverable

A project skeleton where you can run `datacompass --help` and see available commands (even if they're stubs).

### Suggestions

- **CLI framework**: Typer is ergonomic and generates help docs automatically
- **Config format**: YAML is readable; TOML is stricter - either works
- **Local storage**: SQLite is perfect for local-first; can migrate to Postgres later

---

## Phase 1: Core Catalog (Terminal-First)

**Goal**: Scan data sources and browse metadata from the command line.

This is the foundation. Everything else builds on it.

### 1.1 Core Library - Data Models

- [ ] Define core domain models (DataSource, Object, Column, etc.)
- [ ] Implement local storage layer (SQLite with migrations)
- [ ] Define source adapter interface (abstract base class)
- [ ] Implement adapter registry for plugin discovery
- [ ] Create first adapter for your primary cloud database type

> **See**: `technical-specification.md` Section 6 for detailed adapter interface, registry pattern, config schemas, and a complete Databricks adapter example.

### 1.2 Core Library - Scanning

- [ ] Implement metadata extraction in adapter (tables, views, columns)
- [ ] Implement UPSERT logic (preserve user metadata on re-scan)
- [ ] Support incremental vs full scan modes
- [ ] Handle connection errors gracefully

### 1.3 CLI - Source Management

```bash
# Target commands for this phase
datacompass source add <name> --type <type> --config <path>
datacompass source list
datacompass source remove <name>
datacompass source test <name>  # Verify connection
```

- [ ] Implement source registration commands
- [ ] Store source configs (connection info should support secrets/env vars)
- [ ] Output as JSON by default, `--format table` for human-readable

### 1.4 CLI - Scanning

```bash
datacompass scan <source-name>
datacompass scan <source-name> --full  # Force full re-scan
datacompass scan --all  # Scan all registered sources
```

- [ ] Implement scan command that calls core library
- [ ] Show progress during scan
- [ ] Output scan summary (objects found, updated, unchanged)

### 1.5 CLI - Browsing Catalog

```bash
datacompass objects list --source <name>
datacompass objects list --type TABLE
datacompass objects show <source>.<schema>.<name>
datacompass columns list <source>.<schema>.<table>
```

- [ ] Implement catalog browsing commands
- [ ] Support filtering (by source, type, schema)
- [ ] JSON output by default, table format optional

### Milestone Checkpoint

✅ You can register a cloud data source, scan it, and browse the resulting catalog entirely from the terminal. No web app, no API.

**Test**: Run `datacompass scan my-source && datacompass objects list --source my-source --format json | jq '.[] | .object_name'`

---

## Phase 2: Search & Documentation (Terminal-First)

**Goal**: Find objects quickly and add user documentation.

### 2.1 Core Library - Search

- [ ] Implement full-text search on object names, descriptions, tags
- [ ] Support filtering (type, schema, source)
- [ ] Return ranked results

### 2.2 Core Library - User Metadata

- [ ] Implement description/tags update logic
- [ ] Preserve user metadata during re-scans (already done in 1.2, but verify)

### 2.3 CLI - Search

```bash
datacompass search "customer"
datacompass search "customer" --type TABLE --source prod
```

- [ ] Implement search command
- [ ] Show relevance-ranked results

### 2.4 CLI - Documentation

```bash
datacompass describe <object> "This table contains..."
datacompass tag <object> --add "pii" --add "customer-data"
datacompass tag <object> --remove "deprecated"
```

- [ ] Implement commands to update user metadata
- [ ] Changes should persist across re-scans

### Milestone Checkpoint

✅ You can search the catalog and document objects from the terminal.

**Test**: `datacompass describe prod.sales.customers "Customer master data" && datacompass search "customer" | grep "Customer master data"`

---

## Phase 3: API Layer

**Goal**: Expose core capabilities over HTTP for programmatic access and future web UI.

### 3.1 API Setup

- [ ] Set up web framework (FastAPI recommended)
- [ ] Create API app that imports core library
- [ ] Implement health check endpoint

### 3.2 Catalog API

- [ ] `GET /sources` - List sources
- [ ] `POST /sources` - Add source
- [ ] `GET /objects` - List/search objects
- [ ] `GET /objects/{id}` - Object detail
- [ ] `PATCH /objects/{id}` - Update user metadata
- [ ] `POST /scan/{source}` - Trigger scan

### 3.3 API Patterns

- [ ] Implement consistent response envelope (`data`, `meta`, `errors`)
- [ ] Add pagination support
- [ ] Generate OpenAPI documentation

### Key Principle

The API should be a thin translation layer. If you're writing business logic in an API route, stop - that belongs in the core library.

### Milestone Checkpoint

✅ The API provides the same capabilities as the CLI. You could swap the CLI for curl commands.

**Test**: `curl localhost:8000/objects?search=customer` returns same data as `datacompass search "customer" --format json`

---

## Phase 4: Web Interface - Catalog Browser

**Goal**: Visual interface for browsing and searching the catalog.

The web layer earns its existence by providing things terminals can't: visual browsing, faceted search, and interactive exploration.

### 4.1 Frontend Setup

- [ ] Initialize frontend project (React + Vite recommended)
- [ ] Set up routing
- [ ] Create API client (or generate from OpenAPI spec)
- [ ] Implement layout shell with source selector

### 4.2 Core Pages

- [ ] **Home**: Search-first landing page
- [ ] **Browse**: Object list with filtering and pagination
- [ ] **Object Detail**: Show metadata, columns, user documentation
- [ ] **Search Results**: Full-text search with facets

### 4.3 Documentation Features

- [ ] Inline editing for descriptions
- [ ] Tag management UI
- [ ] Column-level documentation

### Milestone Checkpoint

✅ You have a working data catalog web application. Users can browse, search, and document database objects.

**Test**: Non-technical users can navigate the catalog and add documentation without touching the terminal.

---

## Phase 5: Lineage (Terminal-First)

**Goal**: Track and visualize data dependencies.

### 5.1 Core Library - Lineage

- [ ] Extend adapter interface for dependency extraction
- [ ] Implement dependency storage model
- [ ] Support multiple parsing sources (source-provided, SQL parsing, manual)
- [ ] Implement graph traversal (upstream/downstream with depth limit)

### 5.2 CLI - Lineage

```bash
datacompass lineage <object> --direction upstream --depth 3
datacompass lineage <object> --direction downstream
datacompass lineage <object> --format dot  # GraphViz format
```

- [ ] Implement lineage commands
- [ ] Support text tree output and structured formats (JSON, DOT)

### 5.3 API - Lineage

- [ ] `GET /objects/{id}/lineage` - Return lineage graph data

### 5.4 Web - Lineage Visualization

- [ ] Interactive lineage graph (ReactFlow or similar)
- [ ] Click-to-expand nodes
- [ ] Filter by depth and type

### Milestone Checkpoint

✅ Users can trace data flow from terminal or visual graph.

**Test**: `datacompass lineage prod.analytics.customer_360 --direction upstream` shows the source tables feeding this view.

---

## Phase 6: Data Quality Monitoring (Terminal-First)

**Goal**: Define expectations, detect anomalies, track breaches.

This is a significant feature. Build it incrementally.

### 6.1 Core Library - DQ Configuration

- [ ] Define DQ config and expectation models
- [ ] Implement configuration file format for DQ rules
- [ ] Store configs in catalog database

### 6.2 Core Library - DQ Execution

- [ ] Extend adapter interface for metric queries
- [ ] Implement query builder for expectations
- [ ] Implement metric storage (results by date)

### 6.3 Core Library - Breach Detection

- [ ] Implement threshold strategies (absolute, statistical, DOW-adjusted)
- [ ] Implement breach detection with immutable threshold snapshots
- [ ] Support breach lifecycle (open, acknowledged, dismissed, resolved)

### 6.4 CLI - DQ Commands

```bash
# Configuration
datacompass dq init <object>  # Create config file template
datacompass dq apply <config-file>  # Apply DQ config from file
datacompass dq list  # List configured objects

# Execution
datacompass dq run <object>
datacompass dq run --all
datacompass dq backfill <object> --days 30

# Results
datacompass dq status <object>  # Current breach status
datacompass dq history <object>  # Historical results
datacompass dq breaches list --status open
```

- [ ] Implement DQ CLI commands
- [ ] Support config-file-driven setup (version-controllable)

### 6.5 API - DQ Endpoints

- [ ] DQ config CRUD
- [ ] Trigger execution
- [ ] Breach listing and status updates

### 6.6 Web - DQ Hub

- [ ] DQ dashboard with status overview
- [ ] Breach table with filtering
- [ ] Trend charts for metrics
- [ ] Config editor (generates config files)

### Milestone Checkpoint

✅ Full DQ monitoring: define rules in config files, run checks from CLI or scheduled, investigate breaches in web UI.

**Test**: Define DQ rules in YAML, apply with `datacompass dq apply rules.yaml`, run with `datacompass dq run --all`, see breaches with `datacompass dq breaches list`.

---

## Phase 7: Deprecation Management

**Goal**: Manage object deprecation campaigns with dependency awareness.

### 7.1 Core Library

- [ ] Implement campaign and deprecation models
- [ ] Implement dependency impact analysis

### 7.2 CLI

```bash
datacompass deprecate campaign create <name> --target-date 2025-06-01
datacompass deprecate add <object> --campaign <name> --replacement <object>
datacompass deprecate check <campaign>  # Show dependency warnings
datacompass deprecate list --campaign <name>
```

### 7.3 API & Web

- [ ] Campaign management API
- [ ] Web UI for campaign creation and tracking
- [ ] Dependency warning visualization

---

## Phase 8: Scheduling & Notifications

**Goal**: Automate scans and DQ checks, alert on issues.

### 8.1 Scheduling

- [ ] Implement task scheduler for background jobs
- [ ] Schedule metadata scans
- [ ] Schedule DQ execution

### 8.2 Notifications

- [ ] Implement notification service with channel plugins (email, Slack, webhook)
- [ ] Define notification rules (which events, which channels)
- [ ] CLI command to test notifications

```bash
datacompass notify test --channel slack-alerts
```

### 8.3 Web

- [ ] Notification configuration UI
- [ ] Sync/DQ execution history

---

## Phase 9: Polish & Production Readiness

**Goal**: Harden for production use.

### Tasks

- [ ] Add authentication hooks (org verification middleware)
- [ ] Add audit trail (who changed what)
- [ ] Improve error handling and logging
- [ ] Add observability (metrics, structured logs)
- [ ] Performance optimization (query efficiency, caching)
- [ ] Documentation (user guide, API reference)
- [ ] Deployment configuration (Docker, environment management)

---

## Adapter Development Guide

As you build phases 1-6, you'll need source adapters. Each adapter implements:

```python
class SourceAdapter(ABC):
    def connect(self, config: dict) -> bool
    def get_objects(self, object_types: list[str]) -> list[dict]
    def get_columns(self, objects: list[str]) -> list[dict]
    def get_dependencies(self) -> list[dict]
    def execute_dq_query(self, query: DQQuery) -> list[dict]
    def get_supported_object_types(self) -> list[str]
    def get_supported_dq_metrics(self) -> list[str]
```

### Suggested Adapter Development Order

1. **Your primary cloud database** - Build this first during Phase 1
2. **Second cloud database** - Validates your adapter interface is generic
3. **Additional sources as needed**

### Cloud-Specific Considerations

#### Authentication

Cloud sources differ from on-prem databases:

| On-Prem | Cloud |
|---------|-------|
| Username/password in config | OAuth 2.0 / OIDC tokens |
| | Service account JSON keys |
| | IAM roles (same-cloud deployment) |
| | Short-lived tokens requiring refresh |

**Adapter design**: Authentication should be pluggable per adapter. Consider supporting:
- Environment variables for secrets
- Credential files (with secure permissions)
- Cloud SDK default credentials (e.g., `gcloud auth`, AWS credential chain)

#### Connection Patterns

| On-Prem | Cloud |
|---------|-------|
| Direct TCP, always available | May require VPN or private networking |
| | API rate limits on metadata endpoints |
| | Network latency |
| | Some metadata via REST APIs, not SQL |

**Adapter design**:
- Implement retry logic with exponential backoff
- Cache metadata locally to reduce API calls
- Support async operations for slow sources

#### Supported Platforms (Examples)

| Platform | Metadata Access | DQ Query Execution |
|----------|-----------------|-------------------|
| Snowflake | INFORMATION_SCHEMA or REST API | SQL via connector |
| BigQuery | INFORMATION_SCHEMA or REST API | SQL via client |
| Redshift | INFORMATION_SCHEMA | SQL via connector |
| Databricks | Unity Catalog REST API | SQL via connector |
| dbt | Manifest JSON files | N/A (metadata only) |

Each requires a specific adapter, but the core remains unchanged.

---

## Testing Strategy

Following the terminal-first philosophy, test from the inside out:

| Layer | Test Type | Focus |
|-------|-----------|-------|
| Core Library | Unit tests | Business logic, UPSERT, breach detection |
| Core Library | Integration tests | Adapter implementations against test databases |
| CLI | Integration tests | Command execution, output format |
| API | Integration tests | HTTP translation correctness |
| Web | Component tests | Rendering, user interaction |
| Web | E2E tests | Critical user flows only |

**Principle**: Never test business logic through the web layer. If your only test for "DQ rule catches nulls" requires a browser, the architecture is wrong.

---

## Configuration-as-Code Examples

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
      # Credentials via environment variables
      user: ${SNOWFLAKE_USER}
      password: ${SNOWFLAKE_PASSWORD}
    sync:
      enabled: true
      schedule: "0 6 * * *"  # 6 AM daily

  - name: staging
    type: snowflake
    config:
      # ...
```

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

---

## Phase 10: Governance Foundation

**Goal**: Add enterprise governance capabilities - classification, ownership, access control, and audit.

This phase transforms Data Compass from a data catalog into a governance platform.

### 10.1 Core Library - Classification System

- [ ] Define classification models (levels, compliance labels)
- [ ] Implement classification assignment (object and column level)
- [ ] Support classification inheritance (table inherits from columns)
- [ ] Implement classification rules (auto-classify based on patterns)

```python
class ClassificationLevel(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class ComplianceLabel(Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOX = "sox"
```

### 10.2 Core Library - Ownership Model

- [ ] Define ownership models (Owner, Steward, Domain)
- [ ] Implement owner/steward assignment
- [ ] Support domain hierarchy (Business Unit → Domain → Sub-domain)
- [ ] Link objects to domains

```python
class DataOwner(Base):
    object_id: int
    user_id: str          # Email or username
    role: OwnerRole       # owner, steward, delegate
    assigned_at: datetime
    assigned_by: str

class Domain(Base):
    id: int
    name: str             # "Customer Data", "Finance", etc.
    parent_id: int | None # Hierarchy support
    owners: list[str]     # Domain-level owners
```

### 10.3 Core Library - RBAC

- [ ] Define permission model (roles, permissions, grants)
- [ ] Implement permission checking in core services
- [ ] Support object-level permissions
- [ ] Integrate with auth middleware

```python
class Role(Enum):
    VIEWER = "viewer"       # Read catalog, search
    EDITOR = "editor"       # Add descriptions, tags
    STEWARD = "steward"     # Manage DQ, classification
    ADMIN = "admin"         # Full access

class Permission(Base):
    id: int
    user_id: str
    role: Role
    scope_type: str         # "global", "source", "domain", "object"
    scope_id: int | None    # ID of scoped entity
```

### 10.4 Core Library - Audit Logging

- [ ] Define audit event model
- [ ] Implement audit logging service
- [ ] Log all state changes (who, what, when, before/after)
- [ ] Log access events (who viewed what)

```python
class AuditEvent(Base):
    id: int
    timestamp: datetime
    user_id: str
    action: str             # "view", "update", "delete", "classify", etc.
    entity_type: str        # "object", "dq_config", "breach", etc.
    entity_id: int
    changes: dict | None    # {"field": {"old": x, "new": y}}
    context: dict | None    # Additional context (IP, user agent, etc.)
```

### 10.5 CLI - Governance Commands

```bash
# Classification
datacompass classify <object> --level confidential
datacompass classify <object> --compliance gdpr pci_dss
datacompass classify list --level restricted
datacompass classify rules apply classification-rules.yaml

# Ownership
datacompass owner assign <object> --owner user@company.com
datacompass steward assign <object> --steward user@company.com
datacompass domain create "Customer Data" --parent "Sales"
datacompass domain assign <object> --domain "Customer Data"

# Audit
datacompass audit log --entity-type object --entity-id 123
datacompass audit log --user user@company.com --since 2024-01-01
datacompass audit export --format json --since 2024-01-01
```

### 10.6 API - Governance Endpoints

```
/api/v1/
├── classification/
│   ├── GET    /levels                  List classification levels
│   ├── GET    /objects/{id}            Get object classification
│   ├── PUT    /objects/{id}            Set object classification
│   ├── GET    /rules                   List classification rules
│   └── POST   /rules/apply             Apply classification rules
│
├── ownership/
│   ├── GET    /objects/{id}/owners     Get object owners
│   ├── POST   /objects/{id}/owners     Assign owner
│   ├── DELETE /objects/{id}/owners/{user}  Remove owner
│   ├── GET    /domains                 List domains
│   ├── POST   /domains                 Create domain
│   └── GET    /domains/{id}/objects    Objects in domain
│
├── permissions/
│   ├── GET    /users/{id}/permissions  Get user permissions
│   ├── POST   /grants                  Grant permission
│   ├── DELETE /grants/{id}             Revoke permission
│   └── GET    /roles                   List available roles
│
└── audit/
    ├── GET    /events                  Query audit log
    └── GET    /events/export           Export audit log
```

### 10.7 Web - Governance UI

- [ ] Classification badge on object cards and detail pages
- [ ] Classification editor (dropdown for level, checkboxes for compliance)
- [ ] Ownership panel on object detail
- [ ] Domain browser/navigator
- [ ] Audit log viewer with filtering
- [ ] Admin panel for RBAC management

### 10.8 Configuration - Classification Rules

```yaml
# classification-rules.yaml
rules:
  - name: "PII Detection - Email"
    match:
      column_name_pattern: "(?i)(email|e_mail|email_address)"
    apply:
      level: confidential
      compliance: [gdpr]

  - name: "PII Detection - SSN"
    match:
      column_name_pattern: "(?i)(ssn|social_security)"
    apply:
      level: restricted
      compliance: [gdpr, hipaa]

  - name: "Financial Data"
    match:
      schema_pattern: "(?i)(finance|accounting)"
    apply:
      level: confidential
      compliance: [sox]
```

Apply with: `datacompass classify rules apply classification-rules.yaml`

### Milestone Checkpoint

✅ Data Compass is now a governance platform with classification, ownership, access control, and audit capabilities.

**Test**:
- `datacompass classify prod.customers.users --level confidential --compliance gdpr`
- `datacompass owner assign prod.customers.users --owner data-team@company.com`
- `datacompass audit log --entity-type object --since 2024-01-01 | jq '.[] | .action'`

---

## Summary

| Phase | Deliverable | Testable Outcome |
|-------|-------------|------------------|
| 0 | Project skeleton | `datacompass --help` works |
| 1 | Core catalog (CLI) | Scan and browse from terminal |
| 2 | Search & docs (CLI) | Find and document objects from terminal |
| 3 | API layer | Same capabilities via HTTP |
| 4 | Web catalog | Visual browsing and search |
| 5 | Lineage | Trace dependencies (CLI + web graph) |
| 6 | Data quality | Full DQ monitoring pipeline |
| 7 | Deprecation | Manage deprecation campaigns |
| 8 | Scheduling | Automated operations and alerts |
| 9 | Production | Auth, audit, observability |
| 10 | Governance | Classification, ownership, RBAC, audit |

Each phase builds on the previous. Each phase is independently valuable. Don't skip ahead - the terminal-first approach ensures clean architecture.
