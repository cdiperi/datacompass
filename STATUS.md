# Data Compass - Project Status

Last updated: 2026-02-03
Current Phase: **Phase 9.2 Complete** - CLI Authentication Implemented

## Completed: Phase 9.1 & 9.2 - Core Auth Infrastructure & CLI Authentication

### Deliverables
- [x] Database schema for users, api_keys, sessions, refresh_tokens (migration 007)
- [x] `User`, `APIKey`, `Session`, `RefreshToken` SQLAlchemy models
- [x] `UserRepository`, `APIKeyRepository`, `SessionRepository`, `RefreshTokenRepository` for CRUD
- [x] Pluggable auth provider system (`LocalAuthProvider`, `DisabledAuthProvider`)
- [x] `AuthService` for authentication, token management, user/API key management
- [x] JWT-based access tokens with bcrypt password hashing
- [x] Refresh token rotation for extended sessions
- [x] CLI commands: `auth login/logout/whoami/status`, `auth user create/list/show/disable/enable/set-superuser`, `auth apikey create/list/revoke`
- [x] Credential storage (`~/.datacompass/.credentials`) with secure permissions
- [x] Environment variable support (`DATACOMPASS_API_KEY`, `DATACOMPASS_ACCESS_TOKEN`)

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth mode | Configurable (disabled/local/oidc/ldap) | Default disabled for backwards compatibility |
| Password hashing | bcrypt | Industry standard, secure |
| Token format | JWT with HS256 | Stateless access tokens, easy validation |
| API keys | Prefix + hash storage | Show prefix for identification, hash for security |
| Refresh tokens | Rotation on use | Enhanced security, detect token reuse |

### New Files Added
```
src/datacompass/core/
├── auth/
│   ├── __init__.py                    # Provider factory
│   └── providers/
│       ├── __init__.py
│       ├── base.py                    # AuthProvider ABC, AuthResult
│       ├── local.py                   # Password auth + JWT
│       └── disabled.py                # No-op for auth_mode=disabled
├── models/auth.py                     # User, APIKey, Session, RefreshToken models
├── repositories/auth.py               # CRUD operations
├── services/auth_service.py           # Business logic
└── migrations/versions/
    └── 20260203_0007_007_authentication.py  # Alembic migration

tests/
├── core/repositories/test_auth.py     # 21 repository tests
├── core/services/test_auth_service.py # 26 service tests
└── cli/test_auth_commands.py          # 25 CLI tests
```

### CLI Commands
```bash
# Authentication
datacompass auth login --email user@example.com
datacompass auth logout
datacompass auth whoami
datacompass auth status

# User management (admin)
datacompass auth user create admin@example.com --password --superuser
datacompass auth user list [--include-inactive]
datacompass auth user show admin@example.com
datacompass auth user disable user@example.com
datacompass auth user enable user@example.com
datacompass auth user set-superuser user@example.com [--remove]

# API key management
datacompass auth apikey create "CI/CD Key" --scopes read,write --expires-days 30
datacompass auth apikey list
datacompass auth apikey revoke <key-id>
```

### Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `DATACOMPASS_AUTH_MODE` | `disabled` | Auth mode: disabled, local, oidc, ldap |
| `DATACOMPASS_AUTH_SECRET_KEY` | (random) | JWT signing key (change in production) |
| `DATACOMPASS_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `DATACOMPASS_AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `DATACOMPASS_AUTH_AUTO_REGISTER` | `false` | Auto-register on first OIDC/LDAP login |

### Tests
- **442 backend tests passing** (up from 368)
- 21 new repository tests
- 26 new service tests
- 25 new CLI tests

### Deferred to Later
- OIDC provider implementation (Phase 9.3)
- LDAP provider implementation (Phase 9.3)
- API middleware for authenticated endpoints (Phase 9.4)
- Frontend authentication UI (Phase 9.5)
- Role-based access control (Phase 10)

---

## Completed: Phase 8 - Scheduling & Notifications (Scaffolded)

### Deliverables
- [x] Database schema for schedules, schedule_runs, notification_channels, notification_rules, notification_log (migration 006)
- [x] `Schedule`, `ScheduleRun`, `NotificationChannel`, `NotificationRule`, `NotificationLog` SQLAlchemy models
- [x] `SchedulingRepository`, `NotificationRepository` for CRUD operations
- [x] `SchedulingService`, `NotificationService` for business logic
- [x] CLI commands: `schedule create/list/show/update/delete/enable/disable`, `notify channel/rule/log/apply`
- [x] API endpoints: `/api/v1/schedules`, `/api/v1/notifications`

### Note
Phase 8 is scaffolded with full CRUD operations but the actual scheduler daemon and notification delivery are not yet implemented. The infrastructure is in place for scheduling jobs and managing notification rules.

---

## Completed: Phase 7 - Deprecation Campaign Management

### Deliverables
- [x] Database schema for campaigns and deprecations (migration 005)
- [x] `DeprecationCampaign`, `Deprecation` SQLAlchemy models
- [x] `DeprecationRepository` for CRUD operations
- [x] `DeprecationService` for business logic + impact analysis
- [x] Campaign lifecycle management (draft → active → completed)
- [x] Object-to-campaign assignment with optional replacements
- [x] Impact analysis using existing lineage data (BFS traversal)
- [x] CLI commands: `deprecate campaign create/list/show/update/delete`, `add`, `remove`, `list`, `check`
- [x] API endpoints: `/api/v1/deprecations/campaigns`, `/objects`, `/impact`, `/hub/summary`
- [x] Web UI: Deprecation hub page with campaign management

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Campaign scoping | Source-scoped with unique name | Campaigns manage objects from a single source |
| Impact analysis | Reuse LineageService BFS | Leverage existing dependency graph traversal |
| Replacement tracking | Optional object reference | Not all deprecations have direct replacements |
| Status workflow | draft → active → completed | Simple state machine for campaign lifecycle |

### New Files Added
```
src/datacompass/core/
├── models/deprecation.py                     # Campaign + Deprecation models + Pydantic schemas
├── repositories/deprecation.py               # CRUD operations + aggregates
├── services/deprecation_service.py           # Business logic + impact analysis
└── migrations/versions/
    └── 20260201_0005_005_deprecation.py      # Alembic migration

src/datacompass/api/routes/
└── deprecation.py                            # Deprecation API endpoints

frontend/src/
├── hooks/useDeprecation.ts                   # TanStack Query hooks for deprecation
├── components/CampaignTable.tsx              # Campaign list component
├── components/ImpactAnalysis.tsx             # Impact visualization component
└── pages/DeprecationHubPage.tsx              # Deprecation dashboard page

tests/
├── core/repositories/test_deprecation.py
├── core/services/test_deprecation_service.py
└── api/test_deprecation.py
```

### CLI Commands
```bash
# Campaign management
datacompass deprecate campaign create "Q2 Cleanup" --source demo --target-date 2025-06-01
datacompass deprecate campaign list [--source <name>] [--status <status>]
datacompass deprecate campaign show <campaign-id>
datacompass deprecate campaign update <campaign-id> [--name "..."] [--status active]
datacompass deprecate campaign delete <campaign-id>

# Object management
datacompass deprecate add <object> --campaign <id> [--replacement <object>] [--notes "..."]
datacompass deprecate remove <deprecation-id>
datacompass deprecate list [--campaign <id>]

# Impact analysis
datacompass deprecate check <campaign-id> [--depth 3] [--format json|table]
```

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/deprecations/campaigns` | List campaigns |
| POST | `/api/v1/deprecations/campaigns` | Create campaign |
| GET | `/api/v1/deprecations/campaigns/{id}` | Get campaign detail |
| PATCH | `/api/v1/deprecations/campaigns/{id}` | Update campaign |
| DELETE | `/api/v1/deprecations/campaigns/{id}` | Delete campaign |
| POST | `/api/v1/deprecations/campaigns/{id}/objects` | Add object to campaign |
| GET | `/api/v1/deprecations/objects` | List deprecations |
| DELETE | `/api/v1/deprecations/objects/{id}` | Remove object from campaign |
| GET | `/api/v1/deprecations/campaigns/{id}/impact` | Get impact analysis |
| GET | `/api/v1/deprecations/hub/summary` | Hub summary dashboard |

### Tests
- 18 repository tests
- 14 service tests
- 13 API tests

### Deferred to Later
- Notifications when target date approaches (Phase 8)
- Automated deadline reminders (Phase 8)
- Governance/approval workflows (Phase 10)

---

## Completed: Phase 6 - Data Quality

### Deliverables
- [x] Database schema for DQ configs, expectations, results, breaches (migration 004)
- [x] `DQConfig`, `DQExpectation`, `DQResult`, `DQBreach` SQLAlchemy models
- [x] `DQRepository` for CRUD operations
- [x] `DQService` for business logic, threshold computation, breach detection
- [x] Three threshold strategies: absolute, simple_average, dow_adjusted
- [x] Breach lifecycle management (open, acknowledged, dismissed, resolved)
- [x] CLI commands: `dq init`, `apply`, `list`, `run`, `status`, `breaches list/update/show`
- [x] API endpoints: `/api/v1/dq/configs`, `/expectations`, `/breaches`, `/hub/summary`
- [x] Web UI: DQ Hub page with summary cards and breach table

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Threshold strategies | absolute, simple_average, dow_adjusted | Cover common use cases with increasing sophistication |
| Metric execution | Mock values (Phase 6.0) | Defer adapter integration to reduce scope |
| Breach lifecycle | 4 states with event log | Full auditability of status changes |
| YAML config | Object-centric with expectations list | Matches mental model, easy to version control |

### New Files Added
```
src/datacompass/core/
├── models/dq.py                       # DQ models + Pydantic schemas
├── repositories/dq.py                 # CRUD operations for DQ entities
├── services/dq_service.py             # Business logic + threshold computation
└── migrations/versions/
    └── 20260201_0004_004_data_quality.py  # Alembic migration

src/datacompass/api/routes/
└── dq.py                              # DQ API endpoints

frontend/src/
├── hooks/useDQ.ts                     # TanStack Query hooks for DQ
├── components/BreachTable.tsx         # Breach list with filtering
├── components/DQStatusBadge.tsx       # Status/priority badge components
└── pages/DQHubPage.tsx                # DQ dashboard page
```

### CLI Commands
```bash
# Configuration
datacompass dq init demo.core.orders              # Generate YAML template
datacompass dq apply dq/orders.yaml               # Apply config from YAML
datacompass dq list [--source <name>]             # List configured objects
datacompass dq status [<object>]                  # Show DQ status/summary

# Execution
datacompass dq run <object>                       # Run checks for object
datacompass dq run --all                          # Run all enabled checks

# Breach Management
datacompass dq breaches list [--status open]      # List breaches
datacompass dq breaches show <id>                 # Show breach details
datacompass dq breaches update <id> --status acknowledged
```

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dq/configs` | List DQ configurations |
| POST | `/api/v1/dq/configs` | Create DQ configuration |
| GET | `/api/v1/dq/configs/{id}` | Get config with expectations |
| DELETE | `/api/v1/dq/configs/{id}` | Delete configuration |
| POST | `/api/v1/dq/configs/{id}/run` | Run DQ checks |
| POST | `/api/v1/dq/expectations` | Create expectation |
| PATCH | `/api/v1/dq/expectations/{id}` | Update expectation |
| DELETE | `/api/v1/dq/expectations/{id}` | Delete expectation |
| GET | `/api/v1/dq/breaches` | List breaches |
| GET | `/api/v1/dq/breaches/{id}` | Get breach details |
| PATCH | `/api/v1/dq/breaches/{id}/status` | Update breach status |
| GET | `/api/v1/dq/hub/summary` | Get hub dashboard data |

### Deferred to Later
- Adapter `execute_dq_query()` integration (using mock execution)
- Backfill command for historical data
- Trend charts in web UI (starting with breach table)
- Notifications on breach detection (Phase 8)

---

## Completed: Phase 5 - Lineage

### Deliverables
- [x] Database schema for storing dependencies (migration 003)
- [x] `Dependency` SQLAlchemy model with relationships
- [x] `DependencyRepository` for CRUD operations and graph traversal
- [x] `LineageService` for BFS graph building and dependency ingestion
- [x] CLI: `datacompass lineage <object> [--direction] [--depth] [--format]`
- [x] API: `GET /api/v1/objects/{id}/lineage` and `/lineage/summary`
- [x] Web UI: Lineage tab on object detail page

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Graph traversal | BFS with depth limit | Efficient exploration, prevents infinite loops |
| External references | JSON column `target_external` | Tracks dependencies outside catalog |
| Parsing sources | `source_metadata`, `sql_parsing`, `manual` | Multiple ways to discover dependencies |
| Output formats | JSON, table, tree | CLI flexibility for scripting vs human reading |

### New Files Added
```
src/datacompass/core/
├── models/dependency.py           # Dependency model + Pydantic schemas
├── repositories/dependency.py     # CRUD + graph traversal queries
├── services/lineage_service.py    # Business logic for lineage operations
└── migrations/versions/
    └── 20260201_0003_003_lineage.py  # Alembic migration

src/datacompass/api/routes/
└── lineage.py                     # GET /api/v1/objects/{id}/lineage

frontend/src/
├── hooks/useLineage.ts            # TanStack Query hook
└── components/LineageList.tsx     # Upstream/downstream list component

tests/
├── core/repositories/test_dependency.py
├── core/services/test_lineage_service.py
├── api/test_lineage.py
└── cli/test_lineage_commands.py
```

### Tests
- **210 backend tests passing** (up from 171)
- New tests for DependencyRepository, LineageService, CLI commands, API endpoints
- Integration tests with actual dependency data

---

## Completed: Phase 4 - Web Catalog

### Deliverables
- [x] Browse sources in web UI (Home page with source cards)
- [x] List and filter objects by source/type/schema (Browse page)
- [x] View object details with columns (Object detail page)
- [x] Edit object descriptions (inline editing)
- [x] Add/remove tags on objects (tag editor component)
- [x] Search with instant results (debounced search)

### Technology Stack
| Technology | Choice | Version |
|------------|--------|---------|
| Frontend Framework | React | 19 |
| Build Tool | Vite | 7 |
| UI Components | Ant Design | 6 |
| Server State | TanStack Query | 5 |
| Routing | React Router | 7 |
| Testing | Vitest + React Testing Library | 4 |

### New Files Added
```
frontend/
├── package.json                    # Dependencies and scripts
├── vite.config.ts                  # Vite + proxy config
├── tsconfig.json                   # TypeScript config
├── index.html                      # Entry HTML
├── src/
│   ├── main.tsx                    # App entry point
│   ├── App.tsx                     # Router + providers setup
│   ├── index.css                   # Global styles
│   ├── api/
│   │   ├── types.ts                # TypeScript types (matches backend)
│   │   └── client.ts               # Fetch wrapper functions
│   ├── hooks/
│   │   ├── useSources.ts           # TanStack Query hooks for sources
│   │   ├── useObjects.ts           # TanStack Query hooks for objects
│   │   └── useSearch.ts            # TanStack Query hooks for search
│   ├── components/
│   │   ├── Layout.tsx              # App shell (sidebar + header)
│   │   ├── SearchBar.tsx           # Global search input
│   │   ├── SourceCard.tsx          # Source display card
│   │   ├── ObjectTable.tsx         # Objects data table
│   │   ├── ObjectDetail.tsx        # Object info + columns table
│   │   └── TagEditor.tsx           # Add/remove tags UI
│   ├── pages/
│   │   ├── HomePage.tsx            # Dashboard with sources overview
│   │   ├── BrowsePage.tsx          # Browse objects with filters
│   │   ├── ObjectDetailPage.tsx    # Object details + columns
│   │   └── SearchResultsPage.tsx   # Search results display
│   └── test/
│       └── setup.ts                # Vitest setup (matchMedia mock)
└── tests/
    ├── HomePage.test.tsx           # Home page tests
    ├── BrowsePage.test.tsx         # Browse page tests
    └── ObjectDetailPage.test.tsx   # Object detail tests
```

### Tests
- **171 backend tests passing** (unchanged)
- **20 frontend tests passing** (new)
- Component tests with mocked API hooks
- User interaction tests

---

## Completed: Phase 3 - API Layer

### Deliverables
- [x] `GET /health` - Health check endpoint
- [x] `GET /api/v1/sources` - List sources
- [x] `POST /api/v1/sources` - Add source
- [x] `GET /api/v1/sources/{name}` - Get source details
- [x] `DELETE /api/v1/sources/{name}` - Remove source
- [x] `POST /api/v1/sources/{name}/scan` - Trigger scan
- [x] `GET /api/v1/objects` - List objects (with filters)
- [x] `GET /api/v1/objects/{id}` - Get object details
- [x] `PATCH /api/v1/objects/{id}` - Update description/tags
- [x] `GET /api/v1/search?q=...` - Full-text search

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | FastAPI | Modern, async-first, automatic OpenAPI docs |
| Dependency Injection | FastAPI Depends | Clean service injection per request |
| Error Handling | Exception handlers | Maps service exceptions to HTTP status codes |
| CORS | Allow all origins | Web client development flexibility |
| Response Schemas | Reuse core Pydantic models | Consistency between CLI and API |

---

## Completed: Phase 2 - Search & Documentation (CLI)

### Deliverables
- [x] `datacompass search "customer"` - Full-text search
- [x] `datacompass search "pii" --source prod` - Search with source filter
- [x] `datacompass search "orders" --type TABLE` - Search with type filter
- [x] `datacompass objects describe prod.schema.table` - Get description
- [x] `datacompass objects describe prod.schema.table --set "..."` - Set description
- [x] `datacompass objects tag prod.schema.table --add pii` - Add tag
- [x] `datacompass objects tag prod.schema.table --remove pii` - Remove tag
- [x] `datacompass reindex` - Rebuild search index

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Full-text search | SQLite FTS5 | Built-in, fast, supports porter stemming |
| FTS sync | Manual reindex on scan/update | Full control, avoids triggers |
| Search result ranking | FTS5 BM25 (via `rank`) | Industry standard relevance ranking |
| User documentation storage | `user_metadata` JSON column | Flexible, no schema changes needed |

---

## Completed: Phase 1 - Core Catalog (CLI)

### Deliverables
- [x] `datacompass source add prod --type databricks --config prod.yaml` - Add a data source
- [x] `datacompass source list` - List configured sources
- [x] `datacompass source test prod` - Test connection to a source
- [x] `datacompass source remove prod` - Remove a data source
- [x] `datacompass scan prod` - Scan source to discover objects
- [x] `datacompass objects list --source prod` - List catalog objects
- [x] `datacompass objects show prod.schema.table_name` - Show object details

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database migrations | Alembic | Reversible migrations, production-ready |
| Async/sync bridge | Services wrap async with `asyncio.run()` | Adapters async, CLI sync (Typer) |
| Data access | Repository pattern | Encapsulates UPSERT logic, enables DB swap |
| Adapter discovery | Decorator-based registry | Clean registration, supports `adapters list` |
| Config format | YAML with `${VAR}` env substitution | Secure secrets handling |

---

## Completed: Phase 0 - Project Setup

### Deliverables
- [x] `datacompass --help` works
- [x] `datacompass --version` shows `0.1.0`
- [x] All command groups have placeholder commands
- [x] Virtual environment configured with Python 3.11

---

## Project Structure
```
data-compass/
├── pyproject.toml              # Dependencies, entry points, tool config
├── README.md                   # Project overview
├── CLAUDE.md                   # AI engineering context
├── STATUS.md                   # This file
├── alembic.ini                 # Alembic migration config
├── .venv/                      # Python 3.11 virtual environment
├── frontend/                   # Phase 4 - React web UI
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── api/                # API client + types
│   │   ├── hooks/              # TanStack Query hooks
│   │   ├── components/         # Reusable UI components
│   │   └── pages/              # Page components
│   └── tests/                  # Component tests
├── src/
│   └── datacompass/
│       ├── __init__.py         # Version: 0.1.0
│       ├── cli/                # CLI commands
│       ├── config/             # Settings
│       ├── api/                # FastAPI routes
│       └── core/               # Business logic
└── tests/
    ├── api/                    # API tests
    ├── cli/                    # CLI tests
    └── core/                   # Core logic tests
```

---

## Next: Phase 9.3+ - Extended Authentication & Production Hardening

### Phase 9.3: External Auth Providers
- OIDC provider implementation
- LDAP provider implementation
- Auto-registration flows

### Phase 9.4: API Authentication
- JWT middleware for API endpoints
- API key authentication for routes
- Permission checking

### Phase 9.5: Frontend Authentication
- Login/logout UI
- Session management
- Protected routes

### Phase 10: Governance & RBAC
- Role-based access control
- Object ownership
- Data classification

---

## Quick Reference

### Running Commands
```bash
# Always use the virtual environment
.venv/bin/datacompass --help
.venv/bin/pytest tests/ -v
.venv/bin/ruff check src tests
.venv/bin/mypy src

# Start API server
.venv/bin/uvicorn datacompass.api:app --reload

# API documentation
# http://localhost:8000/docs

# Start frontend dev server
cd frontend && npm run dev

# Run frontend tests
cd frontend && npm test

# Build frontend
cd frontend && npm run build
```

### Installing After Changes
```bash
.venv/bin/pip install -e ".[dev]"

# With optional dependencies
.venv/bin/pip install -e ".[dev,databricks,azure]"
```

### Running Migrations
```bash
.venv/bin/alembic upgrade head
```

### Package Version
Current: `0.1.0` (defined in `src/datacompass/__init__.py`)

### Configuration
- `DATACOMPASS_DATA_DIR` - Default: `~/.datacompass/`
- `DATACOMPASS_DATABASE_URL` - Default: `sqlite:///{data_dir}/datacompass.db`
- `DATACOMPASS_DEFAULT_FORMAT` - Default: `json` (options: json, table)
- `DATACOMPASS_LOG_LEVEL` - Default: `INFO`
- `DATACOMPASS_AUTH_MODE` - Default: `disabled` (options: disabled, local, oidc, ldap)
- `DATACOMPASS_AUTH_SECRET_KEY` - JWT signing key (auto-generated if not set)
- `DATACOMPASS_API_KEY` - API key for authentication (CI/CD)
- `DATACOMPASS_ACCESS_TOKEN` - Direct access token (scripting)
