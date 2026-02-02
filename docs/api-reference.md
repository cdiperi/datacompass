# API Reference

Complete reference for the Data Compass REST API.

## Overview

### Base URL

```
http://localhost:8000
```

### API Prefix

All resource endpoints use the `/api/v1` prefix:

```
http://localhost:8000/api/v1/sources
http://localhost:8000/api/v1/objects
```

### Authentication

Currently no authentication is required. Authentication will be added in Phase 9.

### Response Format

All responses are JSON. Successful responses return the requested data. Error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `204` | No Content (successful delete) |
| `400` | Bad Request |
| `404` | Not Found |
| `409` | Conflict (duplicate resource) |
| `422` | Validation Error |
| `500` | Internal Server Error |

### Interactive Documentation

When the server is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Health

### GET /health

Health check endpoint.

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

## Sources

Manage data source configurations.

### GET /api/v1/sources

List all configured data sources.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `active_only` | boolean | Only return active sources (default: false) |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "name": "prod",
    "display_name": "Production Databricks",
    "source_type": "databricks",
    "is_active": true,
    "last_scan_at": "2025-01-15T10:30:00Z",
    "last_scan_status": "success",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
]
```

---

### POST /api/v1/sources

Create a new data source.

**Request Body:**

```json
{
  "name": "prod",
  "source_type": "databricks",
  "display_name": "Production Databricks",
  "connection_info": {
    "host": "adb-123456.1.azuredatabricks.net",
    "http_path": "/sql/1.0/warehouses/abc123",
    "token": "dapi..."
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique source identifier |
| `source_type` | string | Yes | Adapter type (e.g., "databricks") |
| `display_name` | string | No | Human-readable name |
| `connection_info` | object | Yes | Adapter-specific connection config |

**Response:** `201 Created`

**Errors:**
- `409 Conflict`: Source name already exists
- `400 Bad Request`: Invalid adapter type

---

### GET /api/v1/sources/{name}

Get a data source by name.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Source name |

**Response:** `200 OK`

**Errors:**
- `404 Not Found`: Source not found

---

### DELETE /api/v1/sources/{name}

Delete a data source and all its catalog objects.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Source name |

**Response:** `204 No Content`

**Errors:**
- `404 Not Found`: Source not found

---

### POST /api/v1/sources/{name}/scan

Trigger a scan of a data source.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Source name |

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `full` | boolean | Full scan (soft-delete missing objects) |

**Response:** `200 OK`

```json
{
  "source": "prod",
  "status": "success",
  "objects_discovered": 42,
  "objects_created": 5,
  "objects_updated": 37,
  "objects_deleted": 0,
  "columns_discovered": 350,
  "duration_ms": 1234,
  "error": null
}
```

**Errors:**
- `404 Not Found`: Source not found

---

## Objects

Browse and manage catalog objects.

### GET /api/v1/objects

List catalog objects with optional filters.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | string | Filter by source name |
| `object_type` | string | Filter by type (TABLE, VIEW) |
| `schema` | string | Filter by schema name |
| `limit` | integer | Maximum results (default: none) |
| `offset` | integer | Results to skip (default: 0) |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "source_name": "prod",
    "schema_name": "analytics",
    "object_name": "customers",
    "object_type": "TABLE",
    "description": "Main customer dimension table",
    "tags": ["pii", "core"],
    "column_count": 15,
    "updated_at": "2025-01-15T10:30:00Z"
  }
]
```

---

### GET /api/v1/objects/{object_id}

Get detailed information about a catalog object.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `object_id` | string | Numeric ID or `source.schema.name` |

**Response:** `200 OK`

```json
{
  "id": 1,
  "source_name": "prod",
  "source_id": 1,
  "schema_name": "analytics",
  "object_name": "customers",
  "object_type": "TABLE",
  "description": "Main customer dimension table",
  "tags": ["pii", "core"],
  "source_metadata": {
    "created_at": "2024-06-15T00:00:00Z",
    "row_count": 1500000
  },
  "columns": [
    {
      "id": 1,
      "column_name": "customer_id",
      "position": 1,
      "data_type": "BIGINT",
      "nullable": false,
      "description": "Primary key"
    }
  ],
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Errors:**
- `404 Not Found`: Object not found

---

### PATCH /api/v1/objects/{object_id}

Update a catalog object's documentation.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `object_id` | string | Numeric ID or `source.schema.name` |

**Request Body:**

```json
{
  "description": "Updated description",
  "tags_to_add": ["new-tag"],
  "tags_to_remove": ["old-tag"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | No | New description |
| `tags_to_add` | array | No | Tags to add |
| `tags_to_remove` | array | No | Tags to remove |

**Response:** `200 OK` - Returns updated object detail

**Errors:**
- `404 Not Found`: Object not found

---

## Search

Full-text search across the catalog.

### GET /api/v1/search

Search the catalog using full-text search.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (min 1 char) |
| `source` | string | No | Filter by source name |
| `object_type` | string | No | Filter by object type |
| `limit` | integer | No | Maximum results (1-200, default: 50) |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "source_name": "prod",
    "schema_name": "analytics",
    "object_name": "customers",
    "object_type": "TABLE",
    "description": "Main customer dimension table",
    "tags": ["pii", "core"],
    "rank": 0.95
  }
]
```

Results are ordered by relevance (BM25 ranking).

---

## Lineage

Explore data dependencies.

### GET /api/v1/objects/{object_id}/lineage

Get lineage graph for a catalog object.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `object_id` | string | Numeric ID or `source.schema.name` |

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `direction` | string | `upstream` (default) or `downstream` |
| `depth` | integer | Max traversal depth (1-10, default: 3) |

**Response:** `200 OK`

```json
{
  "root": {
    "id": 1,
    "source_name": "prod",
    "schema_name": "analytics",
    "object_name": "daily_revenue",
    "object_type": "VIEW",
    "full_name": "prod.analytics.daily_revenue"
  },
  "nodes": [
    {
      "id": 2,
      "source_name": "prod",
      "schema_name": "core",
      "object_name": "orders",
      "object_type": "TABLE",
      "full_name": "prod.core.orders",
      "distance": 1
    }
  ],
  "external_nodes": [
    {
      "schema_name": "external_db",
      "object_name": "exchange_rates",
      "object_type": "TABLE",
      "distance": 2
    }
  ],
  "edges": [
    {
      "from_id": 1,
      "to_id": 2,
      "to_external": null,
      "dependency_type": "direct"
    }
  ],
  "depth": 3,
  "truncated": false
}
```

**Errors:**
- `404 Not Found`: Object not found

---

### GET /api/v1/objects/{object_id}/lineage/summary

Get lineage summary counts for a catalog object.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `object_id` | string | Numeric ID or `source.schema.name` |

**Response:** `200 OK`

```json
{
  "upstream_count": 5,
  "downstream_count": 12,
  "external_count": 2
}
```

---

## Data Quality

Data quality monitoring and breach management.

### GET /api/v1/dq/configs

List DQ configurations.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_id` | integer | Filter by source ID |
| `enabled_only` | boolean | Only enabled configs (default: false) |
| `limit` | integer | Maximum results (1-1000, default: 100) |
| `offset` | integer | Results to skip (default: 0) |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "source_name": "prod",
    "schema_name": "core",
    "object_name": "orders",
    "date_column": "created_at",
    "grain": "daily",
    "is_enabled": true,
    "expectation_count": 5,
    "open_breach_count": 2
  }
]
```

---

### POST /api/v1/dq/configs

Create a new DQ configuration.

**Request Body:**

```json
{
  "object_id": 1,
  "date_column": "created_at",
  "grain": "daily"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `object_id` | integer | Yes | Catalog object ID |
| `date_column` | string | No | Column for date partitioning |
| `grain` | string | No | Check granularity (default: "daily") |

**Response:** `201 Created`

**Errors:**
- `404 Not Found`: Object not found
- `409 Conflict`: Config already exists for object

---

### GET /api/v1/dq/configs/{config_id}

Get DQ configuration by ID.

**Response:** `200 OK`

```json
{
  "id": 1,
  "object_id": 1,
  "source_name": "prod",
  "schema_name": "core",
  "object_name": "orders",
  "date_column": "created_at",
  "grain": "daily",
  "is_enabled": true,
  "expectations": [
    {
      "id": 1,
      "expectation_type": "row_count",
      "column_name": null,
      "priority": "high",
      "is_enabled": true,
      "threshold_config": {
        "type": "dow_adjusted",
        "lookback_days": 28,
        "warn_threshold_percent": 20,
        "error_threshold_percent": 50
      }
    }
  ]
}
```

**Errors:**
- `404 Not Found`: Config not found

---

### DELETE /api/v1/dq/configs/{config_id}

Delete a DQ configuration.

**Response:** `204 No Content`

---

### POST /api/v1/dq/expectations

Create a new DQ expectation.

**Request Body:**

```json
{
  "config_id": 1,
  "expectation_type": "row_count",
  "column_name": null,
  "priority": "high",
  "threshold_config": {
    "type": "dow_adjusted",
    "lookback_days": 28,
    "warn_threshold_percent": 20,
    "error_threshold_percent": 50
  }
}
```

**Response:** `201 Created`

---

### PATCH /api/v1/dq/expectations/{expectation_id}

Update a DQ expectation.

**Request Body:** (all fields optional)

```json
{
  "expectation_type": "null_count",
  "column_name": "customer_id",
  "priority": "critical",
  "is_enabled": true,
  "threshold_config": { ... }
}
```

**Response:** `200 OK`

---

### DELETE /api/v1/dq/expectations/{expectation_id}

Delete a DQ expectation.

**Response:** `204 No Content`

---

### POST /api/v1/dq/configs/{config_id}/run

Run DQ checks for a configuration.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `snapshot_date` | date | Check date (default: today) |

**Response:** `200 OK`

```json
{
  "config_id": 1,
  "source_name": "prod",
  "schema_name": "core",
  "object_name": "orders",
  "snapshot_date": "2025-01-15",
  "total_checks": 5,
  "passed": 4,
  "breached": 1,
  "results": [
    {
      "expectation_id": 1,
      "expectation_type": "row_count",
      "column_name": null,
      "metric_value": 95000,
      "computed_threshold_low": 100000,
      "computed_threshold_high": null,
      "status": "breach"
    }
  ]
}
```

---

### GET /api/v1/dq/breaches

List DQ breaches.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (open, acknowledged, dismissed, resolved) |
| `priority` | string | Filter by priority (critical, high, medium, low) |
| `source_id` | integer | Filter by source ID |
| `limit` | integer | Maximum results (default: 100) |
| `offset` | integer | Results to skip (default: 0) |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "source_name": "prod",
    "schema_name": "core",
    "object_name": "orders",
    "expectation_type": "row_count",
    "column_name": null,
    "snapshot_date": "2025-01-15",
    "metric_value": 95000,
    "threshold_value": 100000,
    "breach_direction": "low",
    "deviation_percent": 5.0,
    "priority": "high",
    "status": "open",
    "detected_at": "2025-01-15T10:00:00Z"
  }
]
```

---

### GET /api/v1/dq/breaches/{breach_id}

Get breach details.

**Response:** `200 OK`

```json
{
  "id": 1,
  "source_name": "prod",
  "schema_name": "core",
  "object_name": "orders",
  "expectation_type": "row_count",
  "column_name": null,
  "snapshot_date": "2025-01-15",
  "metric_value": 95000,
  "threshold_value": 100000,
  "breach_direction": "low",
  "deviation_percent": 5.0,
  "priority": "high",
  "status": "open",
  "detected_at": "2025-01-15T10:00:00Z",
  "lifecycle_events": [
    {
      "status": "open",
      "at": "2025-01-15T10:00:00Z",
      "by": "system"
    }
  ]
}
```

---

### PATCH /api/v1/dq/breaches/{breach_id}/status

Update breach status.

**Request Body:**

```json
{
  "status": "acknowledged",
  "notes": "Investigating the issue"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | Yes | New status: acknowledged, dismissed, resolved |
| `notes` | string | No | Notes for the change |

**Response:** `200 OK` - Returns updated breach

---

### GET /api/v1/dq/hub/summary

Get DQ hub dashboard summary.

**Response:** `200 OK`

```json
{
  "total_configs": 15,
  "enabled_configs": 12,
  "total_expectations": 45,
  "open_breaches": 5,
  "breaches_by_priority": {
    "critical": 1,
    "high": 2,
    "medium": 2,
    "low": 0
  },
  "breaches_by_status": {
    "open": 5,
    "acknowledged": 3,
    "dismissed": 1,
    "resolved": 10
  }
}
```

---

## Deprecations

Deprecation campaign management.

### GET /api/v1/deprecations/campaigns

List deprecation campaigns.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_id` | integer | Filter by source ID |
| `status` | string | Filter by status (draft, active, completed) |
| `limit` | integer | Maximum results (default: 100) |
| `offset` | integer | Results to skip (default: 0) |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "source_name": "prod",
    "name": "Q2 Cleanup",
    "status": "active",
    "target_date": "2025-06-01",
    "object_count": 5,
    "days_remaining": 137
  }
]
```

---

### POST /api/v1/deprecations/campaigns

Create a new deprecation campaign.

**Request Body:**

```json
{
  "source_id": 1,
  "name": "Q2 Cleanup",
  "target_date": "2025-06-01",
  "description": "Remove legacy reporting tables"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | integer | Yes | Source ID |
| `name` | string | Yes | Campaign name (unique per source) |
| `target_date` | date | Yes | Target retirement date |
| `description` | string | No | Campaign description |

**Response:** `201 Created`

**Errors:**
- `404 Not Found`: Source not found
- `409 Conflict`: Campaign name exists for source

---

### GET /api/v1/deprecations/campaigns/{campaign_id}

Get campaign details.

**Response:** `200 OK`

```json
{
  "id": 1,
  "source_id": 1,
  "source_name": "prod",
  "name": "Q2 Cleanup",
  "description": "Remove legacy reporting tables",
  "status": "active",
  "target_date": "2025-06-01",
  "days_remaining": 137,
  "deprecations": [
    {
      "id": 1,
      "object_id": 10,
      "schema_name": "reporting",
      "object_name": "legacy_revenue",
      "object_type": "VIEW",
      "replacement_name": "analytics.revenue_v2",
      "migration_notes": "Use new analytics table"
    }
  ],
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T00:00:00Z"
}
```

---

### PATCH /api/v1/deprecations/campaigns/{campaign_id}

Update a campaign.

**Request Body:** (all fields optional)

```json
{
  "name": "Q2 Cleanup (Extended)",
  "description": "Updated description",
  "status": "active",
  "target_date": "2025-07-01"
}
```

**Response:** `200 OK`

---

### DELETE /api/v1/deprecations/campaigns/{campaign_id}

Delete a campaign and all its deprecations.

**Response:** `204 No Content`

---

### POST /api/v1/deprecations/campaigns/{campaign_id}/objects

Add an object to a campaign.

**Request Body:**

```json
{
  "object_id": "prod.reporting.legacy_table",
  "replacement_id": "prod.analytics.new_table",
  "migration_notes": "Use new analytics table"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `object_id` | string | Yes | Object identifier |
| `replacement_id` | string | No | Replacement object identifier |
| `migration_notes` | string | No | Migration notes |

**Response:** `201 Created`

**Errors:**
- `404 Not Found`: Campaign or object not found
- `409 Conflict`: Object already in campaign

---

### DELETE /api/v1/deprecations/objects/{deprecation_id}

Remove an object from a campaign.

**Response:** `204 No Content`

---

### GET /api/v1/deprecations/objects

List deprecated objects.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `campaign_id` | integer | Filter by campaign ID |
| `limit` | integer | Maximum results (default: 100) |
| `offset` | integer | Results to skip (default: 0) |

**Response:** `200 OK`

---

### GET /api/v1/deprecations/campaigns/{campaign_id}/impact

Get impact analysis for a campaign.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `depth` | integer | Max traversal depth (1-10, default: 3) |

**Response:** `200 OK`

```json
{
  "campaign_id": 1,
  "campaign_name": "Q2 Cleanup",
  "total_deprecated": 3,
  "total_impacted": 12,
  "impacts": [
    {
      "deprecated_object_id": 10,
      "deprecated_object_name": "prod.reporting.legacy_revenue",
      "downstream_count": 5,
      "impacted_objects": [
        {
          "id": 15,
          "full_name": "prod.analytics.monthly_report",
          "object_type": "VIEW",
          "distance": 1
        }
      ]
    }
  ]
}
```

---

### GET /api/v1/deprecations/hub/summary

Get deprecation hub dashboard summary.

**Response:** `200 OK`

```json
{
  "total_campaigns": 5,
  "campaigns_by_status": {
    "draft": 1,
    "active": 3,
    "completed": 1
  },
  "total_deprecated_objects": 15,
  "upcoming_deadlines": [
    {
      "campaign_id": 1,
      "campaign_name": "Q2 Cleanup",
      "target_date": "2025-06-01",
      "days_remaining": 137
    }
  ]
}
```

---

## Schedules

Job scheduling management.

### GET /api/v1/schedules

List scheduled jobs.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_type` | string | Filter by type (scan, dq_run, deprecation_check) |
| `enabled_only` | boolean | Only enabled schedules (default: false) |
| `limit` | integer | Maximum results (default: 100) |
| `offset` | integer | Results to skip (default: 0) |

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "name": "daily-prod-scan",
    "job_type": "scan",
    "target_id": 1,
    "cron_expression": "0 6 * * *",
    "timezone": "UTC",
    "is_enabled": true,
    "next_run_at": "2025-01-16T06:00:00Z",
    "last_run_at": "2025-01-15T06:00:00Z",
    "last_run_status": "success"
  }
]
```

---

### POST /api/v1/schedules

Create a new schedule.

**Request Body:**

```json
{
  "name": "daily-prod-scan",
  "job_type": "scan",
  "target_id": 1,
  "cron_expression": "0 6 * * *",
  "timezone": "UTC",
  "description": "Daily production scan"
}
```

**Response:** `201 Created`

---

### GET /api/v1/schedules/{schedule_id}

Get schedule details.

**Response:** `200 OK`

---

### PATCH /api/v1/schedules/{schedule_id}

Update a schedule.

**Response:** `200 OK`

---

### DELETE /api/v1/schedules/{schedule_id}

Delete a schedule.

**Response:** `204 No Content`

---

### POST /api/v1/schedules/{schedule_id}/run

Run a scheduled job immediately.

**Response:** `200 OK`

---

## Notifications

Notification channel and rule management.

### GET /api/v1/notifications/channels

List notification channels.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel_type` | string | Filter by type (email, slack, webhook) |

**Response:** `200 OK`

---

### POST /api/v1/notifications/channels

Create a notification channel.

**Request Body:**

```json
{
  "name": "slack-alerts",
  "channel_type": "webhook",
  "config": {
    "url": "https://hooks.slack.com/services/..."
  }
}
```

**Response:** `201 Created`

---

### GET /api/v1/notifications/rules

List notification rules.

**Response:** `200 OK`

---

### POST /api/v1/notifications/rules

Create a notification rule.

**Request Body:**

```json
{
  "name": "critical-breaches",
  "event_type": "dq_breach",
  "channel_id": 1,
  "filters": {
    "priority": "critical"
  }
}
```

**Response:** `201 Created`

---

## Example: curl Commands

### List sources

```bash
curl http://localhost:8000/api/v1/sources
```

### Create a source

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod",
    "source_type": "databricks",
    "connection_info": {
      "host": "adb-123.azuredatabricks.net",
      "http_path": "/sql/1.0/warehouses/abc",
      "token": "dapi..."
    }
  }'
```

### Trigger a scan

```bash
curl -X POST "http://localhost:8000/api/v1/sources/prod/scan?full=true"
```

### Search the catalog

```bash
curl "http://localhost:8000/api/v1/search?q=customer&limit=10"
```

### Get object lineage

```bash
curl "http://localhost:8000/api/v1/objects/prod.analytics.revenue/lineage?direction=upstream&depth=5"
```

### Run DQ checks

```bash
curl -X POST http://localhost:8000/api/v1/dq/configs/1/run
```

### Update breach status

```bash
curl -X PATCH http://localhost:8000/api/v1/dq/breaches/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "acknowledged", "notes": "Investigating"}'
```

### Create deprecation campaign

```bash
curl -X POST http://localhost:8000/api/v1/deprecations/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": 1,
    "name": "Q2 Cleanup",
    "target_date": "2025-06-01"
  }'
```
