# CLI Reference

Complete reference for all Data Compass CLI commands.

## Global Options

All commands support these options:

```
--version, -v     Show version and exit
--config, -c      Path to configuration file
--help            Show help and exit
```

## Output Formats

Most commands support two output formats:

```
--format, -f      Output format: json (default) or table
```

**JSON** (default): Structured output for scripting and pipelines
**Table**: Human-readable formatted tables

Set default via environment variable:

```bash
export DATACOMPASS_DEFAULT_FORMAT=table
```

---

## source

Manage data sources.

### source add

Add a new data source.

```bash
datacompass source add <name> --type <type> --config <yaml> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Unique name for the data source |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Source type (e.g., `databricks`) **(required)** |
| `--config` | `-c` | Path to source configuration YAML **(required)** |
| `--display-name` | `-d` | Human-readable display name |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Add a Databricks source
datacompass source add prod --type databricks --config prod.yaml

# Add with display name
datacompass source add prod --type databricks --config prod.yaml \
    --display-name "Production Databricks"
```

**Exit codes:**
- `0`: Success
- `1`: Configuration error or source already exists

---

### source list

List configured data sources.

```bash
datacompass source list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass source list --format table
```

**Output fields:**
- `name`: Source identifier
- `type`: Adapter type
- `display_name`: Human-readable name
- `is_active`: Whether source is active
- `last_scan_at`: Timestamp of last scan
- `last_scan_status`: Status of last scan

---

### source test

Test connection to a data source.

```bash
datacompass source test <name> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Name of the source to test |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass source test prod
```

**Exit codes:**
- `0`: Connection successful
- `1`: Connection failed or source not found

---

### source remove

Remove a data source and all its catalog objects.

```bash
datacompass source remove <name> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Name of the source to remove |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation prompt |

**Example:**

```bash
datacompass source remove prod
datacompass source remove prod --force
```

---

## scan

Scan a data source to update the catalog.

```bash
datacompass scan <source> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `source` | Name of the source to scan |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--full` | | Perform full scan instead of incremental |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Incremental scan
datacompass scan prod

# Full rescan
datacompass scan prod --full
```

**Exit codes:**
- `0`: Scan completed successfully
- `1`: Scan failed or source not found

---

## objects

Browse and inspect catalog objects.

### objects list

List catalog objects.

```bash
datacompass objects list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Filter by source name |
| `--type` | `-t` | Filter by object type (TABLE, VIEW) |
| `--schema` | | Filter by schema name |
| `--limit` | `-l` | Maximum number of results |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# List all objects
datacompass objects list

# Filter by source and type
datacompass objects list --source prod --type TABLE

# Filter by schema
datacompass objects list --source prod --schema analytics

# Limit results
datacompass objects list --limit 20
```

---

### objects show

Show details for a specific object.

```bash
datacompass objects show <object_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (`source.schema.name`) or numeric ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
datacompass objects show prod.analytics.customers
datacompass objects show prod.analytics.customers --format table
```

**Exit codes:**
- `0`: Success
- `1`: Object not found

---

### objects describe

Get or set the description for an object.

```bash
datacompass objects describe <object_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (`source.schema.name`) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--set` | | Set description to this value |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Get current description
datacompass objects describe prod.analytics.customers

# Set description
datacompass objects describe prod.analytics.customers \
    --set "Main customer dimension table"
```

---

### objects tag

Manage tags on an object.

```bash
datacompass objects tag <object_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (`source.schema.name`) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--add` | `-a` | Tag(s) to add (repeatable) |
| `--remove` | `-r` | Tag(s) to remove (repeatable) |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# View tags
datacompass objects tag prod.analytics.customers

# Add tags
datacompass objects tag prod.analytics.customers --add pii --add core

# Remove tags
datacompass objects tag prod.analytics.customers --remove deprecated

# Add and remove
datacompass objects tag prod.analytics.customers --add critical --remove test
```

---

## search

Search the catalog using full-text search.

```bash
datacompass search <query> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Search query string |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Filter by source name |
| `--type` | `-t` | Filter by object type |
| `--limit` | `-l` | Maximum results (default: 50) |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Basic search
datacompass search "customer"

# Filtered search
datacompass search "orders" --source prod --type TABLE

# Limit results
datacompass search "revenue" --limit 10
```

---

## reindex

Rebuild the search index.

```bash
datacompass reindex [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Reindex specific source only |

**Examples:**

```bash
# Rebuild entire index
datacompass reindex

# Rebuild for specific source
datacompass reindex --source prod
```

---

## lineage

Show lineage (dependencies) for a catalog object.

```bash
datacompass lineage <object_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (`source.schema.name`) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--direction` | `-d` | Traversal direction: `upstream` (default), `downstream`, or `both` |
| `--depth` | | Maximum traversal depth (1-10, default: 3) |
| `--format` | `-f` | Output format: `json`, `table`, or `tree` |

**Examples:**

```bash
# View upstream dependencies
datacompass lineage prod.analytics.daily_sales

# View downstream impact
datacompass lineage prod.core.customers --direction downstream

# View both upstream and downstream
datacompass lineage prod.core.customers --direction both

# Deep traversal with tree view
datacompass lineage prod.analytics.revenue --depth 5 --format tree
```

---

## adapters

List and inspect available adapters.

### adapters list

List available adapter types.

```bash
datacompass adapters list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass adapters list
```

---

## auth

Authentication management commands.

### auth login

Log in to Data Compass.

```bash
datacompass auth login [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--email` | `-e` | Email address for local auth |
| `--password` | `-p` | Prompt for password (local auth) |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Local authentication (prompts for password)
datacompass auth login --email user@example.com --password

# Check login status
datacompass auth whoami
```

**Exit codes:**
- `0`: Login successful
- `1`: Authentication failed

---

### auth logout

Log out and clear stored credentials.

```bash
datacompass auth logout
```

**Example:**

```bash
datacompass auth logout
```

---

### auth whoami

Show the current authenticated user.

```bash
datacompass auth whoami [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass auth whoami
```

**Output:**

```json
{
  "authenticated": true,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "John Doe",
    "is_superuser": false
  }
}
```

---

### auth status

Show authentication configuration status.

```bash
datacompass auth status [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass auth status
```

**Output:**

```json
{
  "auth_mode": "local",
  "auth_enabled": true
}
```

---

### auth user create

Create a new user (superuser only).

```bash
datacompass auth user create <email> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `email` | User email address |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--password` | `-p` | Prompt for password |
| `--display-name` | `-d` | Display name |
| `--superuser` | | Create as superuser |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass auth user create admin@example.com --password --superuser
```

---

### auth user list

List all users (superuser only).

```bash
datacompass auth user list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--include-inactive` | | Include disabled users |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass auth user list --format table
```

---

### auth user show

Show user details (superuser only).

```bash
datacompass auth user show <email> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `email` | User email address |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass auth user show user@example.com
```

---

### auth user disable

Disable a user account (superuser only).

```bash
datacompass auth user disable <email>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `email` | User email address |

**Example:**

```bash
datacompass auth user disable user@example.com
```

---

### auth user enable

Enable a user account (superuser only).

```bash
datacompass auth user enable <email>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `email` | User email address |

**Example:**

```bash
datacompass auth user enable user@example.com
```

---

### auth user set-superuser

Set or remove superuser status (superuser only).

```bash
datacompass auth user set-superuser <email> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `email` | User email address |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--remove` | | Remove superuser status |

**Examples:**

```bash
# Grant superuser
datacompass auth user set-superuser user@example.com

# Revoke superuser
datacompass auth user set-superuser user@example.com --remove
```

---

### auth apikey create

Create a new API key.

```bash
datacompass auth apikey create <name> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Name for the API key |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--scopes` | `-s` | Comma-separated scopes (default: `read`) |
| `--expires-days` | | Days until expiration (1-365) |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Create a read-only key
datacompass auth apikey create "Read-only Key"

# Create a key with write access
datacompass auth apikey create "CI/CD Key" --scopes read,write

# Create an expiring key
datacompass auth apikey create "Temp Key" --expires-days 30
```

**Note:** The full key is only shown once. Store it securely.

---

### auth apikey list

List your API keys.

```bash
datacompass auth apikey list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--include-inactive` | | Include revoked keys |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass auth apikey list --format table
```

---

### auth apikey revoke

Revoke an API key.

```bash
datacompass auth apikey revoke <key_id>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `key_id` | API key ID |

**Example:**

```bash
datacompass auth apikey revoke 1
```

---

## dq

Data quality monitoring commands.

### dq init

Generate a DQ configuration template for an object.

```bash
datacompass dq init <object_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (`source.schema.name`) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output path for YAML file |

**Examples:**

```bash
# Output to stdout
datacompass dq init prod.core.orders

# Save to file
datacompass dq init prod.core.orders --output dq/orders.yaml
```

---

### dq apply

Apply a DQ configuration from YAML file.

```bash
datacompass dq apply <config_file> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `config_file` | Path to DQ configuration YAML |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass dq apply dq/orders.yaml
```

---

### dq list

List DQ configurations.

```bash
datacompass dq list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Filter by source name |
| `--enabled` | | Only show enabled configs |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
datacompass dq list
datacompass dq list --source prod --enabled
```

---

### dq run

Run data quality checks.

```bash
datacompass dq run [object_id] [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (optional if using `--all`) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | | Run checks for all enabled configs |
| `--date` | | Snapshot date (YYYY-MM-DD) |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Run for specific object
datacompass dq run prod.core.orders

# Run all enabled
datacompass dq run --all

# Run for specific date
datacompass dq run prod.core.orders --date 2025-01-15
```

---

### dq status

Show DQ status for an object or overall summary.

```bash
datacompass dq status [object_id] [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (optional) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Overall hub summary
datacompass dq status

# Specific object
datacompass dq status prod.core.orders
```

---

### dq breaches list

List DQ breaches.

```bash
datacompass dq breaches list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--status` | `-s` | Filter by status: `open`, `acknowledged`, `dismissed`, `resolved` |
| `--priority` | `-p` | Filter by priority: `critical`, `high`, `medium`, `low` |
| `--limit` | `-l` | Maximum results (default: 50) |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
datacompass dq breaches list --status open
datacompass dq breaches list --priority critical
```

---

### dq breaches show

Show breach details.

```bash
datacompass dq breaches show <breach_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `breach_id` | Breach ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass dq breaches show 42
```

---

### dq breaches update

Update breach status.

```bash
datacompass dq breaches update <breach_id> --status <status> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `breach_id` | Breach ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--status` | `-s` | New status: `acknowledged`, `dismissed`, `resolved` **(required)** |
| `--notes` | `-n` | Notes for the status change |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
datacompass dq breaches update 42 --status acknowledged
datacompass dq breaches update 42 --status resolved --notes "Fixed upstream issue"
```

---

## deprecate

Deprecation campaign management.

### deprecate campaign create

Create a new deprecation campaign.

```bash
datacompass deprecate campaign create <name> --source <source> --target-date <date> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Campaign name |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Source name **(required)** |
| `--target-date` | `-t` | Target date (YYYY-MM-DD) **(required)** |
| `--description` | `-d` | Campaign description |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass deprecate campaign create "Q2 Cleanup" \
    --source prod \
    --target-date 2025-06-01 \
    --description "Remove legacy reporting tables"
```

---

### deprecate campaign list

List deprecation campaigns.

```bash
datacompass deprecate campaign list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Filter by source name |
| `--status` | | Filter by status: `draft`, `active`, `completed` |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass deprecate campaign list --source prod --status active
```

---

### deprecate campaign show

Show campaign details.

```bash
datacompass deprecate campaign show <campaign_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `campaign_id` | Campaign ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass deprecate campaign show 1
```

---

### deprecate campaign update

Update a campaign.

```bash
datacompass deprecate campaign update <campaign_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `campaign_id` | Campaign ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--name` | `-n` | New name |
| `--status` | `-s` | New status: `draft`, `active`, `completed` |
| `--target-date` | `-t` | New target date |
| `--description` | `-d` | New description |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass deprecate campaign update 1 --status active
```

---

### deprecate campaign delete

Delete a campaign.

```bash
datacompass deprecate campaign delete <campaign_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `campaign_id` | Campaign ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation |

**Example:**

```bash
datacompass deprecate campaign delete 1 --force
```

---

### deprecate add

Add an object to a deprecation campaign.

```bash
datacompass deprecate add <object_id> --campaign <id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (`source.schema.name`) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--campaign` | `-c` | Campaign ID **(required)** |
| `--replacement` | `-r` | Replacement object identifier |
| `--notes` | `-n` | Migration notes |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
datacompass deprecate add prod.reporting.old_table --campaign 1

datacompass deprecate add prod.reporting.old_table --campaign 1 \
    --replacement prod.analytics.new_table \
    --notes "Use new analytics table"
```

---

### deprecate remove

Remove an object from a campaign.

```bash
datacompass deprecate remove <deprecation_id>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `deprecation_id` | Deprecation ID |

**Example:**

```bash
datacompass deprecate remove 5
```

---

### deprecate list

List deprecated objects.

```bash
datacompass deprecate list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--campaign` | `-c` | Filter by campaign ID |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass deprecate list --campaign 1
```

---

### deprecate check

Check downstream impact of a deprecation campaign.

```bash
datacompass deprecate check <campaign_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `campaign_id` | Campaign ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--depth` | `-d` | Maximum traversal depth (1-10, default: 3) |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass deprecate check 1 --depth 5 --format table
```

---

## schedule

Manage scheduled jobs.

### schedule list

List scheduled jobs.

```bash
datacompass schedule list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Filter by job type: `scan`, `dq_run`, `deprecation_check` |
| `--enabled` | | Filter by enabled status |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass schedule list --type scan --enabled
```

---

### schedule show

Show schedule details.

```bash
datacompass schedule show <schedule_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `schedule_id` | Schedule ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass schedule show 1
```

---

### schedule create

Create a new scheduled job.

```bash
datacompass schedule create <name> --type <type> --cron <expression> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Schedule name (unique) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Job type: `scan`, `dq_run`, `deprecation_check` **(required)** |
| `--cron` | `-c` | Cron expression **(required)** |
| `--target` | | Target ID (source_id, config_id, or campaign_id) |
| `--timezone` | | Timezone (default: UTC) |
| `--description` | `-d` | Description |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Daily scan at 6 AM
datacompass schedule create "daily-scan" --type scan --cron "0 6 * * *" --target 1

# Hourly DQ checks
datacompass schedule create "hourly-dq" --type dq_run --cron "0 * * * *"
```

---

### schedule update

Update a schedule.

```bash
datacompass schedule update <schedule_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `schedule_id` | Schedule ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--name` | `-n` | New name |
| `--cron` | `-c` | New cron expression |
| `--enabled/--disabled` | | Enable or disable |
| `--timezone` | | New timezone |
| `--description` | `-d` | New description |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
datacompass schedule update 1 --cron "0 8 * * *"
datacompass schedule update 1 --disabled
```

---

### schedule delete

Delete a schedule.

```bash
datacompass schedule delete <schedule_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `schedule_id` | Schedule ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation |

**Example:**

```bash
datacompass schedule delete 1 --force
```

---

### schedule run

Run a scheduled job immediately.

```bash
datacompass schedule run <schedule_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `schedule_id` | Schedule ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass schedule run 1
```

---

### schedule apply

Apply schedules from YAML configuration file.

```bash
datacompass schedule apply <config_file> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `config_file` | Path to schedules YAML file |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass schedule apply schedules.yaml
```

---

## scheduler

Control the scheduler daemon.

### scheduler start

Start the scheduler daemon.

```bash
datacompass scheduler start [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--background` | `-b` | Run in background |

**Examples:**

```bash
# Foreground (Ctrl+C to stop)
datacompass scheduler start

# Background
datacompass scheduler start --background
```

---

### scheduler status

Show scheduler status.

```bash
datacompass scheduler status [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass scheduler status
```

---

## notify

Manage notifications.

### notify channel list

List notification channels.

```bash
datacompass notify channel list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Filter by type: `email`, `slack`, `webhook` |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass notify channel list --type slack
```

---

### notify channel create

Create a notification channel.

```bash
datacompass notify channel create <name> --type <type> --config <json> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Channel name (unique) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Channel type: `email`, `slack`, `webhook` **(required)** |
| `--config` | `-c` | Channel config as JSON string **(required)** |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass notify channel create "slack-alerts" \
    --type webhook \
    --config '{"url": "https://hooks.slack.com/services/..."}'
```

---

### notify rule list

List notification rules.

```bash
datacompass notify rule list [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--event-type` | `-e` | Filter by event type |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass notify rule list
```

---

### notify rule create

Create a notification rule.

```bash
datacompass notify rule create <name> --event-type <type> --channel <id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Rule name |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--event-type` | `-e` | Event type: `dq_breach`, `scan_failed`, etc. **(required)** |
| `--channel` | `-c` | Channel ID **(required)** |
| `--filters` | | Filters as JSON string |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass notify rule create "critical-breaches" \
    --event-type dq_breach \
    --channel 1 \
    --filters '{"priority": "critical"}'
```

---

### notify log

View notification log.

```bash
datacompass notify log [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--limit` | `-l` | Maximum entries (default: 50) |
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass notify log --limit 100
```

---

### notify apply

Apply notifications from YAML configuration file.

```bash
datacompass notify apply <config_file> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `config_file` | Path to notifications YAML file |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass notify apply notifications.yaml
```

---

## usage

Usage metrics commands for tracking object-level statistics.

### usage collect

Collect usage metrics for all objects in a source.

```bash
datacompass usage collect <source> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `source` | Name of the source to collect metrics from |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Output format: `json` or `table` |

**Example:**

```bash
datacompass usage collect prod
```

**Output (JSON):**

```json
{
  "source_name": "prod",
  "collected_count": 42,
  "skipped_count": 3,
  "error_count": 0,
  "collected_at": "2025-01-15T10:30:00Z"
}
```

**Exit codes:**
- `0`: Collection successful
- `1`: Source not found or collection error

---

### usage show

Show usage metrics for a specific object.

```bash
datacompass usage show <object_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `object_id` | Object identifier (`source.schema.name`) or numeric ID |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--history` | `-h` | Number of days of history to show |
| `--limit` | `-l` | Maximum number of records (for history) |
| `--format` | `-f` | Output format: `json` or `table` |

**Examples:**

```bash
# Show latest metrics
datacompass usage show prod.analytics.customers

# Show 30 days of history
datacompass usage show prod.analytics.customers --history 30

# Limit historical records
datacompass usage show prod.analytics.customers --history 30 --limit 10
```

**Output (JSON - latest):**

```json
{
  "id": 1,
  "object_id": 42,
  "object_name": "customers",
  "schema_name": "analytics",
  "source_name": "prod",
  "collected_at": "2025-01-15T10:30:00Z",
  "row_count": 1500000,
  "size_bytes": 524288000,
  "read_count": 150,
  "write_count": 5,
  "last_read_at": "2025-01-15T09:00:00Z",
  "last_written_at": "2025-01-14T22:00:00Z",
  "distinct_users": 12,
  "query_count": 250
}
```

**Exit codes:**
- `0`: Success
- `1`: Object not found

---

### usage hot

Show the most accessed tables (hot tables).

```bash
datacompass usage hot [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Filter by source name |
| `--days` | `-d` | Look back period in days (default: 7) |
| `--limit` | `-l` | Maximum number of results (default: 20) |
| `--order-by` | `-o` | Metric to order by (default: `read_count`) |
| `--format` | `-f` | Output format: `json` or `table` |

**Order-by options:** `read_count`, `write_count`, `row_count`, `size_bytes`

**Examples:**

```bash
# Show hot tables across all sources
datacompass usage hot

# Filter by source
datacompass usage hot --source prod

# Custom lookback and ordering
datacompass usage hot --days 30 --order-by size_bytes --limit 10

# Table format for readability
datacompass usage hot --format table
```

**Output (table):**

```
Hot Tables (last 7 days, ordered by read_count)

#   Object                           Row Count   Size (MB)   Reads   Writes
1   prod.analytics.customers         1,500,000   500.00      150     5
2   prod.core.orders                 5,000,000   1,200.00    120     25
3   prod.reporting.daily_revenue     365,000     50.00       95      1
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATACOMPASS_DATA_DIR` | `~/.datacompass` | Data directory location |
| `DATACOMPASS_DATABASE_URL` | `sqlite:///{data_dir}/datacompass.db` | Database URL |
| `DATACOMPASS_CONFIG_FILE` | `{data_dir}/config.yaml` | Global config file path |
| `DATACOMPASS_DEFAULT_FORMAT` | `json` | Default output format |
| `DATACOMPASS_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `DATACOMPASS_AUTH_MODE` | `disabled` | Auth mode: `disabled`, `local`, `oidc` |
| `DATACOMPASS_AUTH_SECRET_KEY` | (auto) | JWT signing key (change in production) |
| `DATACOMPASS_API_KEY` | | API key for CLI authentication |
| `DATACOMPASS_ACCESS_TOKEN` | | Access token for CLI authentication |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (entity not found, validation error, etc.) |
| `2` | Invalid usage (missing arguments) |

---

## Cron Expression Reference

Cron expressions use 5 fields: minute, hour, day-of-month, month, day-of-week.

| Expression | Description |
|------------|-------------|
| `0 6 * * *` | Daily at 6:00 AM |
| `0 * * * *` | Every hour |
| `*/15 * * * *` | Every 15 minutes |
| `0 0 * * 0` | Weekly on Sunday at midnight |
| `0 0 1 * *` | Monthly on the 1st at midnight |
| `0 9-17 * * 1-5` | Every hour 9-5 on weekdays |
