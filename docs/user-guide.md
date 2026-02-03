# User Guide

This guide covers how to use Data Compass to catalog, monitor, and govern your data assets.

## Getting Started

### Installation

Install Data Compass using pip:

```bash
pip install datacompass
```

For development or to use optional features:

```bash
# Clone the repository
git clone https://github.com/yourorg/data-compass.git
cd data-compass

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install with development dependencies
pip install -e ".[dev]"

# Install with Databricks support
pip install -e ".[databricks]"

# Install with all optional dependencies
pip install -e ".[all]"
```

### Verify Installation

```bash
datacompass --version
# datacompass 0.1.0

datacompass --help
```

### Data Directory

Data Compass stores its data in `~/.datacompass/` by default:

```
~/.datacompass/
├── datacompass.db      # SQLite database
└── config.yaml         # Global configuration (optional)
```

Override with the `DATACOMPASS_DATA_DIR` environment variable:

```bash
export DATACOMPASS_DATA_DIR=/custom/path
```

## Authentication

Data Compass supports optional authentication to secure access to your catalog.

### Auth Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `disabled` | No authentication (default) | Development, single-user |
| `local` | Email/password authentication | Small teams, self-hosted |
| `oidc` | Enterprise SSO via OAuth2/OIDC | Enterprise (coming soon) |

### Enabling Local Authentication

Set the auth mode via environment variable:

```bash
export DATACOMPASS_AUTH_MODE=local
export DATACOMPASS_AUTH_SECRET_KEY="your-secure-secret-key"
```

### Creating the First User

When local auth is enabled, create a superuser:

```bash
datacompass auth user create admin@example.com --password --superuser
```

### Logging In (CLI)

```bash
# Log in with email/password
datacompass auth login --email admin@example.com --password

# Check who you're logged in as
datacompass auth whoami

# Log out
datacompass auth logout
```

### Creating API Keys

API keys are useful for CI/CD pipelines and automated scripts:

```bash
# Create an API key
datacompass auth apikey create "CI/CD Key" --scopes read,write --expires-days 90

# The key is shown once - save it securely!
# Use it via environment variable
export DATACOMPASS_API_KEY=dc_abc123...

# Or via header in API calls
curl -H "X-API-Key: dc_abc123..." http://localhost:8000/api/v1/sources
```

### Managing Users (Admin)

Superusers can manage other users:

```bash
# List users
datacompass auth user list

# Create a user
datacompass auth user create user@example.com --password

# Disable a user
datacompass auth user disable user@example.com

# Enable a user
datacompass auth user enable user@example.com

# Grant superuser privileges
datacompass auth user set-superuser user@example.com
```

### Web UI Authentication

When auth is enabled, the web UI will display a login page. Users must authenticate before accessing the catalog.

### Auth Disabled Mode

By default (`DATACOMPASS_AUTH_MODE=disabled`), no authentication is required. This is suitable for:
- Local development
- Single-user deployments
- Trusted internal networks

---

## Configuring Data Sources

### Source Configuration Files

Data sources are configured using YAML files with environment variable substitution.

**Example: Databricks configuration**

```yaml
# databricks-prod.yaml
connection:
  host: ${DATABRICKS_HOST}
  http_path: ${DATABRICKS_HTTP_PATH}
  token: ${DATABRICKS_TOKEN}

# Optional: Azure Active Directory authentication
# auth_method: azure_ad
# azure:
#   tenant_id: ${AZURE_TENANT_ID}
#   client_id: ${AZURE_CLIENT_ID}
#   client_secret: ${AZURE_CLIENT_SECRET}

catalogs:
  - name: analytics
    schemas:
      - core
      - reporting
      - staging
```

Environment variables are substituted at runtime using `${VAR}` syntax. Set them before running commands:

```bash
export DATABRICKS_HOST="adb-123456.1.azuredatabricks.net"
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/abc123"
export DATABRICKS_TOKEN="dapi..."
```

### Adding Sources

```bash
# Add a data source
datacompass source add prod --type databricks --config databricks-prod.yaml

# Add with a display name
datacompass source add prod --type databricks --config databricks-prod.yaml \
    --display-name "Production Databricks"
```

### Managing Sources

```bash
# List all sources
datacompass source list

# Test connection to a source
datacompass source test prod

# Remove a source (and all its catalog objects)
datacompass source remove prod
```

### Available Adapters

View installed adapters:

```bash
datacompass adapters list
```

Current adapters:
- `databricks` - Databricks Unity Catalog

## Cataloging Your Data

### Scanning Sources

After adding a source, scan it to discover objects:

```bash
# Scan a source
datacompass scan prod

# Full scan (re-fetch all metadata)
datacompass scan prod --full
```

The scan operation:
1. Connects to the data source
2. Discovers tables, views, and other objects
3. Fetches column metadata
4. Updates the local catalog database
5. Rebuilds the search index

### Browsing Objects

```bash
# List all objects
datacompass objects list

# Filter by source
datacompass objects list --source prod

# Filter by type
datacompass objects list --type TABLE
datacompass objects list --type VIEW

# Filter by schema
datacompass objects list --source prod --schema analytics

# Limit results
datacompass objects list --source prod --limit 10
```

### Viewing Object Details

```bash
# Show object details (includes columns)
datacompass objects show prod.analytics.customers

# Human-readable format
datacompass objects show prod.analytics.customers --format table
```

Output includes:
- Object metadata (type, schema, source)
- Source-provided descriptions
- User documentation (descriptions, tags)
- Column information with data types

### Documenting Objects

Add descriptions to help others understand your data:

```bash
# Get current description
datacompass objects describe prod.analytics.customers

# Set a description
datacompass objects describe prod.analytics.customers \
    --set "Main customer dimension table. Contains one row per customer."
```

### Managing Tags

Tags help categorize and filter objects:

```bash
# View current tags
datacompass objects tag prod.analytics.customers

# Add tags
datacompass objects tag prod.analytics.customers --add pii --add core

# Remove tags
datacompass objects tag prod.analytics.customers --remove deprecated

# Add and remove in one command
datacompass objects tag prod.analytics.customers --add critical --remove test
```

## Searching the Catalog

Data Compass provides full-text search across all object metadata.

### Basic Search

```bash
# Search for objects
datacompass search "customer"

# Search is case-insensitive and supports partial matches
datacompass search "order"
```

### Filtered Search

```bash
# Search within a source
datacompass search "customer" --source prod

# Search by object type
datacompass search "orders" --type TABLE

# Combine filters
datacompass search "revenue" --source prod --type VIEW

# Limit results
datacompass search "customer" --limit 20
```

### Rebuilding the Search Index

If search results seem stale:

```bash
# Rebuild entire index
datacompass reindex

# Rebuild for a specific source
datacompass reindex --source prod
```

## Exploring Lineage

Lineage shows the dependencies between data objects - what tables feed into a view, or what downstream objects depend on a table.

### Viewing Upstream Dependencies

See what objects are used to create a given object:

```bash
# View upstream dependencies
datacompass lineage prod.analytics.daily_revenue

# Default direction is upstream
datacompass lineage prod.analytics.daily_revenue --direction upstream
```

### Viewing Downstream Impact

See what objects depend on a given object:

```bash
# View downstream dependents
datacompass lineage prod.core.customers --direction downstream
```

### Controlling Depth

Limit how far to traverse the dependency graph:

```bash
# Default depth is 3
datacompass lineage prod.analytics.revenue --depth 5

# Maximum depth is 10
datacompass lineage prod.analytics.revenue --depth 10
```

### Output Formats

```bash
# JSON (default, for pipelines)
datacompass lineage prod.analytics.revenue

# Table format
datacompass lineage prod.analytics.revenue --format table

# Tree format (visual hierarchy)
datacompass lineage prod.analytics.revenue --format tree
```

## Data Quality Monitoring

Data quality monitoring helps you track metrics over time and detect anomalies.

### Creating DQ Configurations

Generate a configuration template:

```bash
# Generate template for an object
datacompass dq init prod.core.orders

# Save to a file
datacompass dq init prod.core.orders --output dq/orders.yaml
```

### DQ Configuration Format

```yaml
# dq/orders.yaml
object: prod.core.orders
date_column: created_at
grain: daily
enabled: true

expectations:
  # Track row count
  - type: row_count
    threshold_strategy: dow_adjusted
    lookback_days: 28
    warn_threshold_percent: 20
    error_threshold_percent: 50
    priority: high

  # Track null values
  - type: null_count
    column: customer_id
    threshold_strategy: absolute
    error_threshold: 0
    priority: critical

  # Track distinct values
  - type: distinct_count
    column: status
    threshold_strategy: simple_average
    lookback_days: 14
    warn_threshold_percent: 10
    error_threshold_percent: 25
    priority: medium
```

**Expectation types:**
- `row_count` - Number of rows
- `null_count` - Count of NULL values in a column
- `distinct_count` - Count of distinct values in a column

**Threshold strategies:**
- `absolute` - Fixed threshold values
- `simple_average` - Compare against average of recent values
- `dow_adjusted` - Compare against same day-of-week average

**Priority levels:**
- `critical` - Requires immediate attention
- `high` - Should be addressed soon
- `medium` - Standard priority
- `low` - Informational

### Applying Configurations

```bash
# Apply a DQ configuration
datacompass dq apply dq/orders.yaml
```

### Running DQ Checks

```bash
# Run checks for a specific object
datacompass dq run prod.core.orders

# Run all enabled checks
datacompass dq run --all

# Run for a specific date
datacompass dq run prod.core.orders --date 2025-01-15
```

### Viewing DQ Status

```bash
# Hub summary (all objects)
datacompass dq status

# Status for a specific object
datacompass dq status prod.core.orders

# Human-readable format
datacompass dq status --format table
```

### Managing Breaches

When metrics fall outside thresholds, breaches are created.

```bash
# List open breaches
datacompass dq breaches list --status open

# Filter by priority
datacompass dq breaches list --priority critical

# View breach details
datacompass dq breaches show 42

# Update breach status
datacompass dq breaches update 42 --status acknowledged
datacompass dq breaches update 42 --status resolved --notes "Fixed upstream data issue"
```

**Breach statuses:**
- `open` - Newly detected, needs attention
- `acknowledged` - Someone is working on it
- `dismissed` - False positive or accepted risk
- `resolved` - Issue has been fixed

### Listing DQ Configurations

```bash
# List all configs
datacompass dq list

# Filter by source
datacompass dq list --source prod

# Only enabled configs
datacompass dq list --enabled
```

## Deprecation Management

Deprecation campaigns help you plan and communicate when data objects will be retired.

### Creating Campaigns

```bash
# Create a deprecation campaign
datacompass deprecate campaign create "Q2 Cleanup" \
    --source prod \
    --target-date 2025-06-01 \
    --description "Removing legacy reporting tables"
```

### Managing Campaigns

```bash
# List campaigns
datacompass deprecate campaign list

# Filter by source or status
datacompass deprecate campaign list --source prod --status active

# View campaign details
datacompass deprecate campaign show 1

# Update campaign status
datacompass deprecate campaign update 1 --status active
datacompass deprecate campaign update 1 --name "Q2 Cleanup (Extended)"

# Delete a campaign
datacompass deprecate campaign delete 1
```

**Campaign statuses:**
- `draft` - Planning phase
- `active` - Communication has started
- `completed` - Deprecation finished

### Adding Objects to Campaigns

```bash
# Add an object to deprecate
datacompass deprecate add prod.reporting.legacy_revenue --campaign 1

# Specify a replacement
datacompass deprecate add prod.reporting.legacy_revenue \
    --campaign 1 \
    --replacement prod.analytics.revenue_v2

# Add notes
datacompass deprecate add prod.reporting.old_customers \
    --campaign 1 \
    --notes "Use customer_dim instead"
```

### Listing Deprecations

```bash
# List all deprecations
datacompass deprecate list

# Filter by campaign
datacompass deprecate list --campaign 1
```

### Impact Analysis

See what objects will be affected by deprecations:

```bash
# Check impact of a campaign
datacompass deprecate check 1

# Limit depth of analysis
datacompass deprecate check 1 --depth 5

# Human-readable format
datacompass deprecate check 1 --format table
```

### Removing Objects from Campaigns

```bash
# Remove a deprecation (by deprecation ID)
datacompass deprecate remove 5
```

## Scheduling & Automation

Scheduling allows you to automate catalog scans, DQ checks, and other jobs.

### Creating Schedules

```bash
# Create a daily scan schedule
datacompass schedule create \
    --name "daily-prod-scan" \
    --job-type scan \
    --target prod \
    --cron "0 6 * * *"

# Create a DQ run schedule
datacompass schedule create \
    --name "hourly-dq-checks" \
    --job-type dq_run \
    --target all \
    --cron "0 * * * *"
```

### Managing Schedules

```bash
# List schedules
datacompass schedule list

# Show schedule details
datacompass schedule show daily-prod-scan

# Update a schedule
datacompass schedule update daily-prod-scan --cron "0 7 * * *"

# Enable/disable
datacompass schedule update daily-prod-scan --enabled false

# Delete a schedule
datacompass schedule delete daily-prod-scan
```

### Running Jobs Manually

```bash
# Run a scheduled job immediately
datacompass schedule run daily-prod-scan
```

### Scheduler Daemon

```bash
# Start the scheduler (foreground)
datacompass scheduler start

# Check scheduler status
datacompass scheduler status
```

### Applying Schedules from YAML

```yaml
# schedules.yaml
schedules:
  - name: daily-prod-scan
    job_type: scan
    target: prod
    cron: "0 6 * * *"
    enabled: true

  - name: hourly-dq
    job_type: dq_run
    target: all
    cron: "0 * * * *"
    enabled: true
```

```bash
datacompass schedule apply schedules.yaml
```

## Notifications

Configure notifications to be alerted about events.

### Creating Channels

```bash
# Create a webhook channel
datacompass notify channel create \
    --name "slack-alerts" \
    --type webhook \
    --config '{"url": "https://hooks.slack.com/..."}'
```

### Creating Rules

```bash
# Create a notification rule
datacompass notify rule create \
    --name "critical-breaches" \
    --event-type dq_breach \
    --channel slack-alerts \
    --filters '{"priority": "critical"}'
```

### Managing Notifications

```bash
# List channels
datacompass notify channel list

# List rules
datacompass notify rule list

# View notification log
datacompass notify log --limit 50
```

### Applying from YAML

```yaml
# notifications.yaml
channels:
  - name: slack-alerts
    type: webhook
    config:
      url: ${SLACK_WEBHOOK_URL}
    enabled: true

rules:
  - name: critical-breaches
    event_type: dq_breach
    channel: slack-alerts
    filters:
      priority: critical
    enabled: true
```

```bash
datacompass notify apply notifications.yaml
```

## Web Interface

Data Compass includes a web UI for visual exploration.

### Starting the Server

```bash
# Start the API server
uvicorn datacompass.api:app --reload --host 0.0.0.0 --port 8000

# Start the frontend (development)
cd frontend
npm install
npm run dev
```

Access the UI at `http://localhost:5173`

### Available Pages

- **Home** - Overview with source statistics
- **Browse** - Filter and explore catalog objects
- **Object Detail** - View metadata, columns, lineage
- **DQ Hub** - Data quality status and breaches
- **Deprecation Hub** - Campaign management and impact analysis

### API Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Output Formats

All CLI commands support JSON and table output.

### JSON Output (Default)

```bash
# JSON is the default for pipeline integration
datacompass objects list --source prod | jq '.[0]'

# Explicit JSON format
datacompass objects list --source prod --format json
```

### Table Output

```bash
# Human-readable tables
datacompass objects list --source prod --format table
```

### Environment Default

Set a default format:

```bash
export DATACOMPASS_DEFAULT_FORMAT=table
```

## Troubleshooting

### Connection Issues

If you can't connect to a data source:

```bash
# Test the connection
datacompass source test prod

# Check adapter configuration
datacompass adapters list

# Verify environment variables are set
echo $DATABRICKS_HOST
```

### Search Problems

If search results seem wrong:

```bash
# Rebuild the search index
datacompass reindex

# For a specific source
datacompass reindex --source prod
```

### Stale Metadata

If metadata seems outdated:

```bash
# Force a full rescan
datacompass scan prod --full
```

### Debug Logging

Enable verbose logging:

```bash
export DATACOMPASS_LOG_LEVEL=DEBUG
datacompass scan prod
```

### Database Issues

Reset the database:

```bash
# Remove the database (CAUTION: loses all data)
rm ~/.datacompass/datacompass.db

# Re-run migrations
alembic upgrade head

# Re-scan sources
datacompass scan prod
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Source not found` | Source doesn't exist | Run `datacompass source add` |
| `Object not found` | Object not in catalog | Run `datacompass scan` |
| `Connection failed` | Network/auth issue | Check credentials, run `source test` |
| `Config file not found` | YAML path wrong | Check file path exists |
| `Invalid YAML` | Syntax error in config | Validate YAML syntax |
