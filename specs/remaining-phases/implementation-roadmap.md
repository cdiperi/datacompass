# Data Compass - Remaining Phases Implementation Roadmap

## Overview

This document provides the implementation guide for completing Data Compass. It covers:
- **Phase 6 Completion**: DQ adapter integration, backfill command, trend charts
- **Phase 8 Completion**: Scheduler daemon and notification delivery
- **Phase 9 Completion**: Audit trail, observability, deployment
- **Phase 10**: Governance foundation (classification, ownership, RBAC)

**Current State**: Phases 0-7 complete, Phase 8 scaffolded, Phase 9.1-9.3 & 9.5 complete (authentication)

---

## Phase 8 Completion: Scheduling & Notifications

**Goal**: Make the scaffolded scheduling and notification system operational.

**What exists**: Database schema, models, repositories, services (CRUD), CLI commands, API endpoints.

**What's missing**: Background scheduler daemon, notification delivery handlers.

### 8.1 Scheduler Daemon

The scheduler needs a background process that:
1. Reads enabled schedules from the database
2. Evaluates cron expressions to determine what's due
3. Executes scheduled tasks (scans, DQ runs)
4. Records run history and handles failures

#### Option A: APScheduler (Recommended for Single-Instance)

```python
# src/datacompass/core/scheduler/daemon.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

class SchedulerDaemon:
    """Background scheduler that executes scheduled tasks."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory
        self.scheduler = BackgroundScheduler()
        self._job_map: dict[int, str] = {}  # schedule_id -> apscheduler_job_id

    def start(self) -> None:
        """Start the scheduler and load all enabled schedules."""
        self.scheduler.start()
        self._sync_schedules()
        # Re-sync every 60 seconds to pick up changes
        self.scheduler.add_job(self._sync_schedules, 'interval', seconds=60)

    def stop(self) -> None:
        """Gracefully shutdown the scheduler."""
        self.scheduler.shutdown(wait=True)

    def _sync_schedules(self) -> None:
        """Sync database schedules with APScheduler jobs."""
        with self.session_factory() as session:
            repo = SchedulingRepository(session)
            schedules = repo.list_schedules(enabled_only=True)

            # Add/update jobs for enabled schedules
            for schedule in schedules:
                self._ensure_job(schedule)

            # Remove jobs for disabled/deleted schedules
            active_ids = {s.id for s in schedules}
            for schedule_id in list(self._job_map.keys()):
                if schedule_id not in active_ids:
                    self._remove_job(schedule_id)

    def _ensure_job(self, schedule: Schedule) -> None:
        """Add or update a job for a schedule."""
        job_id = f"schedule_{schedule.id}"
        trigger = CronTrigger.from_crontab(schedule.cron_expression)

        if schedule.id in self._job_map:
            self.scheduler.reschedule_job(job_id, trigger=trigger)
        else:
            self.scheduler.add_job(
                self._execute_schedule,
                trigger=trigger,
                id=job_id,
                args=[schedule.id],
                misfire_grace_time=300,  # 5 minutes
            )
            self._job_map[schedule.id] = job_id

    def _execute_schedule(self, schedule_id: int) -> None:
        """Execute a scheduled task."""
        with self.session_factory() as session:
            service = SchedulingService(session)
            try:
                service.execute_schedule(schedule_id)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.exception(f"Schedule {schedule_id} failed: {e}")
```

#### Tasks

- [ ] Install APScheduler: `pip install apscheduler`
- [ ] Create `SchedulerDaemon` class with schedule sync
- [ ] Implement `SchedulingService.execute_schedule()` to dispatch to appropriate service
- [ ] Add CLI command: `datacompass scheduler start` (foreground)
- [ ] Add CLI command: `datacompass scheduler run-once <schedule-id>` (manual trigger)
- [ ] Handle task types: `metadata_scan`, `dq_run`
- [ ] Record `ScheduleRun` with status, started_at, completed_at, error_message
- [ ] Add retry logic with exponential backoff for transient failures

#### Option B: Celery + Redis (For Distributed/Production)

If horizontal scaling is needed:

```python
# src/datacompass/tasks/scheduling.py
from celery import Celery
from celery.schedules import crontab

celery = Celery('datacompass')

@celery.task(bind=True, max_retries=3)
def execute_scheduled_task(self, schedule_id: int):
    """Execute a scheduled task."""
    # ... implementation
```

**Decision**: Start with APScheduler. Migrate to Celery only if multi-instance deployment is required.

### 8.2 Notification Delivery Handlers

The notification system needs handlers that actually send messages to external systems.

#### Handler Interface

```python
# src/datacompass/core/notifications/handlers/base.py
from abc import ABC, abstractmethod

class NotificationHandler(ABC):
    """Base class for notification delivery handlers."""

    @abstractmethod
    async def send(self, config: dict, message: NotificationMessage) -> bool:
        """Send a notification. Returns True if successful."""
        ...

    @abstractmethod
    def validate_config(self, config: dict) -> list[str]:
        """Validate channel configuration. Returns list of errors."""
        ...
```

#### Slack Handler

```python
# src/datacompass/core/notifications/handlers/slack.py
import httpx

class SlackHandler(NotificationHandler):
    """Send notifications to Slack via webhooks."""

    async def send(self, config: dict, message: NotificationMessage) -> bool:
        webhook_url = config["webhook_url"]

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
        ]

        if message.link:
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View in Data Compass"},
                    "url": message.link
                }]
            })

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json={"blocks": blocks})
            return response.status_code == 200

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        if "webhook_url" not in config:
            errors.append("webhook_url is required")
        elif not config["webhook_url"].startswith("https://hooks.slack.com/"):
            errors.append("webhook_url must be a Slack webhook URL")
        return errors
```

#### Email Handler

```python
# src/datacompass/core/notifications/handlers/email.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailHandler(NotificationHandler):
    """Send notifications via SMTP email."""

    async def send(self, config: dict, message: NotificationMessage) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.title
        msg["From"] = config["from_address"]
        msg["To"] = ", ".join(config["to_addresses"])

        # Plain text version
        text_body = f"{message.body}\n\n{message.link or ''}"
        msg.attach(MIMEText(text_body, "plain"))

        # HTML version
        html_body = f"""
        <html>
        <body>
            <h2>{message.title}</h2>
            <p><strong>Priority:</strong> {message.priority}</p>
            <p><strong>Source:</strong> {message.source}</p>
            <p>{message.body}</p>
            {f'<p><a href="{message.link}">View in Data Compass</a></p>' if message.link else ''}
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(config["smtp_host"], config.get("smtp_port", 587)) as server:
            if config.get("smtp_tls", True):
                server.starttls()
            if config.get("smtp_username"):
                server.login(config["smtp_username"], config["smtp_password"])
            server.send_message(msg)

        return True

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        if "smtp_host" not in config:
            errors.append("smtp_host is required")
        if "from_address" not in config:
            errors.append("from_address is required")
        if "to_addresses" not in config:
            errors.append("to_addresses is required")
        return errors
```

#### Webhook Handler

```python
# src/datacompass/core/notifications/handlers/webhook.py
import httpx

class WebhookHandler(NotificationHandler):
    """Send notifications to a generic webhook endpoint."""

    async def send(self, config: dict, message: NotificationMessage) -> bool:
        url = config["url"]
        headers = config.get("headers", {})

        payload = {
            "event_type": message.event_type,
            "title": message.title,
            "body": message.body,
            "priority": message.priority,
            "source": message.source,
            "link": message.link,
            "timestamp": message.timestamp.isoformat(),
            "metadata": message.metadata,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            return 200 <= response.status_code < 300

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        if "url" not in config:
            errors.append("url is required")
        return errors
```

#### Tasks

- [ ] Create handler base class and registry
- [ ] Implement `SlackHandler` with webhook support
- [ ] Implement `EmailHandler` with SMTP support
- [ ] Implement `WebhookHandler` for generic integrations
- [ ] Update `NotificationService.send_notification()` to use handlers
- [ ] Add handler registry to discover available handlers
- [ ] Create `NotificationMessage` dataclass for message structure
- [ ] Add rate limiting (max 1 notification per rule per 5 minutes)
- [ ] Add deduplication for repeated events
- [ ] Log all notification attempts to `notification_log` table
- [ ] Add CLI command: `datacompass notify test <channel-id>`

### 8.3 Event Integration

Connect DQ breaches and scan events to the notification system.

```python
# In DQService after breach detection
async def _notify_breach(self, breach: DQBreach) -> None:
    """Send notification for a new breach."""
    message = NotificationMessage(
        event_type="breach_detected",
        title=f"DQ Breach: {breach.expectation.config.object.display_name}",
        body=f"Metric {breach.expectation.metric_type} exceeded threshold. "
             f"Value: {breach.metric_value}, Expected: {breach.threshold_snapshot}",
        priority=breach.expectation.priority,
        source=breach.expectation.config.object.source.name,
        link=f"/dq/breaches/{breach.id}",
        metadata={"breach_id": breach.id, "expectation_id": breach.expectation_id},
    )
    await self.notification_service.send_notification(message)
```

#### Tasks

- [ ] Add `NotificationService` dependency to `DQService`
- [ ] Emit `breach_detected` event when new breach is created
- [ ] Emit `breach_bulk` event when multiple breaches in single run
- [ ] Add `NotificationService` dependency to `CatalogService`
- [ ] Emit `sync_failed` event when scan fails
- [ ] Emit `sync_completed` event (opt-in) when scan completes
- [ ] Add notification for deprecation deadline approaching

### Phase 8 Milestone

✅ Schedules execute automatically on cron expressions
✅ Notifications deliver to Slack, email, and webhooks
✅ DQ breaches trigger alerts
✅ Scan failures trigger alerts

**Test**:
```bash
# Create a DQ breach and verify Slack notification arrives
datacompass dq run --all
# Check Slack channel for breach notification
```

---

## Phase 9 Completion: Production Readiness

### 9.1 Audit Trail

Track all changes with who/what/when/before/after.

#### Database Schema (Migration 008)

```python
# Already defined in technical-specification.md Section 3
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    user_id: Mapped[str] = mapped_column(String(255))  # Email or "system"
    action: Mapped[str] = mapped_column(String(50))  # view, create, update, delete, etc.
    entity_type: Mapped[str] = mapped_column(String(50))  # object, dq_config, breach, etc.
    entity_id: Mapped[int] = mapped_column()
    changes: Mapped[dict | None] = mapped_column(JSON)  # {"field": {"old": x, "new": y}}
    context: Mapped[dict | None] = mapped_column(JSON)  # {ip, user_agent, request_id}

    __table_args__ = (
        Index("ix_audit_user", "user_id"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_timestamp", "timestamp"),
    )
```

#### Audit Service

```python
# src/datacompass/core/services/audit_service.py
class AuditService:
    """Service for recording and querying audit events."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = AuditRepository(session)

    def log_event(
        self,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: int,
        changes: dict | None = None,
        context: dict | None = None,
    ) -> AuditEvent:
        """Log an audit event."""
        event = AuditEvent(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            context=context,
        )
        self.session.add(event)
        return event

    def log_change(
        self,
        user_id: str,
        entity_type: str,
        entity_id: int,
        old_value: dict,
        new_value: dict,
        context: dict | None = None,
    ) -> AuditEvent:
        """Log a change event with before/after diff."""
        changes = self._compute_diff(old_value, new_value)
        if not changes:
            return None  # No actual changes

        return self.log_event(
            user_id=user_id,
            action="update",
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            context=context,
        )

    def _compute_diff(self, old: dict, new: dict) -> dict:
        """Compute field-level diff between old and new values."""
        changes = {}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        return changes

    def query_events(
        self,
        entity_type: str | None = None,
        entity_id: int | None = None,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events with filters."""
        return self.repo.query_events(
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            action=action,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
```

#### Integration Pattern

```python
# In services that modify data, inject AuditService
class CatalogService:
    def __init__(self, session: Session, user_id: str = "system") -> None:
        self.session = session
        self.user_id = user_id
        self.audit = AuditService(session)

    def update_object_metadata(
        self,
        object_id: int,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> CatalogObject:
        obj = self.repo.get_by_id(object_id)
        old_metadata = obj.user_metadata.copy()

        # Apply changes
        if description is not None:
            obj.user_metadata["description"] = description
        if tags is not None:
            obj.user_metadata["tags"] = tags

        # Log audit event
        self.audit.log_change(
            user_id=self.user_id,
            entity_type="object",
            entity_id=object_id,
            old_value={"user_metadata": old_metadata},
            new_value={"user_metadata": obj.user_metadata},
        )

        return obj
```

#### Tasks

- [ ] Create migration 008 for `audit_events` table
- [ ] Create `AuditEvent` SQLAlchemy model
- [ ] Create `AuditRepository` with query methods
- [ ] Create `AuditService` with logging and query methods
- [ ] Add `user_id` parameter to all services (from auth context)
- [ ] Instrument `CatalogService` (object updates, tag changes)
- [ ] Instrument `DQService` (config changes, breach status updates)
- [ ] Instrument `DeprecationService` (campaign changes)
- [ ] Instrument `AuthService` (user creation, API key creation)
- [ ] Add CLI: `datacompass audit log [--entity-type] [--user] [--since]`
- [ ] Add CLI: `datacompass audit export --format json --since <date>`
- [ ] Add API: `GET /api/v1/audit/events` with query parameters
- [ ] Add request context middleware to capture IP, user agent

### 9.2 Observability

#### Prometheus Metrics

```python
# src/datacompass/api/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Request metrics
REQUEST_COUNT = Counter(
    "datacompass_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "datacompass_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# Business metrics
OBJECTS_TOTAL = Gauge(
    "datacompass_objects_total",
    "Total catalog objects",
    ["source", "type"]
)
DQ_BREACHES_OPEN = Gauge(
    "datacompass_dq_breaches_open",
    "Open DQ breaches",
    ["source", "priority"]
)
SCAN_DURATION = Histogram(
    "datacompass_scan_duration_seconds",
    "Metadata scan duration",
    ["source"]
)
```

#### Structured Logging

```python
# src/datacompass/config/logging.py
import structlog

def configure_logging(json_format: bool = True) -> None:
    """Configure structured logging."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

#### Tasks

- [ ] Install prometheus-client and structlog
- [ ] Create metrics definitions module
- [ ] Add metrics middleware to FastAPI app
- [ ] Add `GET /metrics` endpoint (Prometheus format)
- [ ] Configure structured logging with JSON output option
- [ ] Add request_id to all log entries
- [ ] Add metrics for: requests, latency, object counts, breach counts, scan duration
- [ ] Add CLI: `datacompass metrics` to show current metrics
- [ ] Document Prometheus/Grafana setup

### 9.3 Deployment Configuration

#### Docker Setup

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

# Create non-root user
RUN useradd -m datacompass && chown -R datacompass:datacompass /app
USER datacompass

# Environment
ENV DATACOMPASS_DATA_DIR=/data
ENV DATACOMPASS_LOG_FORMAT=json

EXPOSE 8000

CMD ["uvicorn", "datacompass.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: "3.8"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATACOMPASS_DATABASE_URL=postgresql://datacompass:secret@db:5432/datacompass
      - DATACOMPASS_AUTH_MODE=local
      - DATACOMPASS_AUTH_SECRET_KEY=${AUTH_SECRET_KEY}
    volumes:
      - datacompass-data:/data
    depends_on:
      - db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  scheduler:
    build: .
    command: ["python", "-m", "datacompass.scheduler"]
    environment:
      - DATACOMPASS_DATABASE_URL=postgresql://datacompass:secret@db:5432/datacompass
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=datacompass
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=datacompass
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U datacompass"]
      interval: 10s
      timeout: 5s
      retries: 5

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - api

volumes:
  datacompass-data:
  postgres-data:
```

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

#### Tasks

- [ ] Create `Dockerfile` for API/scheduler
- [ ] Create `frontend/Dockerfile` for web UI
- [ ] Create `docker-compose.yml` for local development
- [ ] Create `docker-compose.prod.yml` for production
- [ ] Create `nginx.conf` for frontend with API proxy
- [ ] Add health check endpoint improvements (db connectivity, scheduler status)
- [ ] Create `.env.example` with all configuration options
- [ ] Document deployment process in `docs/deployment.md`

### Phase 9 Milestone

✅ All changes are audited with user attribution
✅ Prometheus metrics available at /metrics
✅ Structured JSON logging in production
✅ Docker deployment ready

**Test**:
```bash
docker-compose up -d
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

---

## Phase 10: Governance Foundation

**Goal**: Add enterprise governance capabilities - classification, ownership, access control.

### 10.1 Database Schema (Migration 009)

```python
# src/datacompass/core/models/governance.py
from sqlalchemy import String, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

class ClassificationLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class ComplianceLabel(str, Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOX = "sox"
    CCPA = "ccpa"

class OwnerRole(str, Enum):
    OWNER = "owner"
    STEWARD = "steward"
    DELEGATE = "delegate"

class Classification(Base):
    """Classification assignment for objects or columns."""
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("catalog_objects.id"))
    column_id: Mapped[int | None] = mapped_column(ForeignKey("columns.id"))
    level: Mapped[ClassificationLevel] = mapped_column(SQLEnum(ClassificationLevel))
    compliance_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    classified_by: Mapped[str] = mapped_column(String(255))
    classified_at: Mapped[datetime] = mapped_column(default=func.now())
    source: Mapped[str] = mapped_column(String(20))  # manual, rule, inherited

    # Relationships
    object: Mapped["CatalogObject"] = relationship(back_populates="classification")
    column: Mapped["Column"] = relationship(back_populates="classification")

    __table_args__ = (
        UniqueConstraint("object_id", "column_id", name="uq_classification_target"),
    )

class Domain(Base):
    """Business domain hierarchy."""
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("domains.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    created_by: Mapped[str] = mapped_column(String(255))

    # Self-referential relationship
    parent: Mapped["Domain"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["Domain"]] = relationship(back_populates="parent")
    objects: Mapped[list["ObjectOwner"]] = relationship(back_populates="domain")

class ObjectOwner(Base):
    """Ownership assignments for objects."""
    __tablename__ = "object_owners"

    id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("catalog_objects.id"))
    domain_id: Mapped[int | None] = mapped_column(ForeignKey("domains.id"))
    user_id: Mapped[str] = mapped_column(String(255))  # Email
    role: Mapped[OwnerRole] = mapped_column(SQLEnum(OwnerRole))
    assigned_by: Mapped[str] = mapped_column(String(255))
    assigned_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    object: Mapped["CatalogObject"] = relationship(back_populates="owners")
    domain: Mapped["Domain"] = relationship(back_populates="objects")

    __table_args__ = (
        UniqueConstraint("object_id", "user_id", "role", name="uq_owner_assignment"),
    )

class ClassificationRule(Base):
    """Auto-classification rules based on patterns."""
    __tablename__ = "classification_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(default=100)  # Lower = higher priority

    # Match conditions (JSON for flexibility)
    match_conditions: Mapped[dict] = mapped_column(JSON)
    # e.g., {"column_name_pattern": "(?i)(email|ssn)", "schema_pattern": "(?i)pii"}

    # Classification to apply
    apply_level: Mapped[ClassificationLevel] = mapped_column(SQLEnum(ClassificationLevel))
    apply_compliance: Mapped[list[str]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    created_by: Mapped[str] = mapped_column(String(255))
```

### 10.2 Classification Service

```python
# src/datacompass/core/services/classification_service.py
import re
from typing import Optional

class ClassificationService:
    """Service for managing data classification."""

    def __init__(self, session: Session, user_id: str = "system") -> None:
        self.session = session
        self.user_id = user_id
        self.repo = ClassificationRepository(session)
        self.audit = AuditService(session)

    def classify_object(
        self,
        object_id: int,
        level: ClassificationLevel,
        compliance_labels: list[str] | None = None,
        source: str = "manual",
    ) -> Classification:
        """Classify an object."""
        # Check existing classification
        existing = self.repo.get_by_object(object_id)

        if existing:
            old_data = existing.to_dict()
            existing.level = level
            existing.compliance_labels = compliance_labels or []
            existing.classified_by = self.user_id
            existing.classified_at = datetime.utcnow()
            existing.source = source

            self.audit.log_change(
                user_id=self.user_id,
                entity_type="classification",
                entity_id=existing.id,
                old_value=old_data,
                new_value=existing.to_dict(),
            )
            return existing

        classification = Classification(
            object_id=object_id,
            level=level,
            compliance_labels=compliance_labels or [],
            classified_by=self.user_id,
            source=source,
        )
        self.session.add(classification)

        self.audit.log_event(
            user_id=self.user_id,
            action="create",
            entity_type="classification",
            entity_id=classification.id,
        )

        return classification

    def classify_column(
        self,
        object_id: int,
        column_id: int,
        level: ClassificationLevel,
        compliance_labels: list[str] | None = None,
    ) -> Classification:
        """Classify a specific column."""
        # Similar to classify_object but with column_id
        ...

    def apply_rules(self, source_id: int | None = None) -> dict:
        """Apply classification rules to objects/columns."""
        rules = self.repo.get_enabled_rules()
        results = {"classified": 0, "skipped": 0, "errors": 0}

        # Get objects to classify
        objects = self._get_unclassified_objects(source_id)

        for obj in objects:
            for rule in sorted(rules, key=lambda r: r.priority):
                if self._matches_rule(obj, rule):
                    try:
                        self.classify_object(
                            object_id=obj.id,
                            level=rule.apply_level,
                            compliance_labels=rule.apply_compliance,
                            source="rule",
                        )
                        results["classified"] += 1
                    except Exception as e:
                        results["errors"] += 1
                    break
            else:
                results["skipped"] += 1

        return results

    def _matches_rule(self, obj: CatalogObject, rule: ClassificationRule) -> bool:
        """Check if an object matches a classification rule."""
        conditions = rule.match_conditions

        # Column name pattern
        if "column_name_pattern" in conditions:
            pattern = re.compile(conditions["column_name_pattern"])
            if not any(pattern.match(col.column_name) for col in obj.columns):
                return False

        # Schema pattern
        if "schema_pattern" in conditions:
            if not re.match(conditions["schema_pattern"], obj.schema_name):
                return False

        # Object name pattern
        if "object_name_pattern" in conditions:
            if not re.match(conditions["object_name_pattern"], obj.object_name):
                return False

        # Tag match
        if "tags" in conditions:
            obj_tags = set(obj.user_metadata.get("tags", []))
            if not obj_tags.intersection(set(conditions["tags"])):
                return False

        return True

    def get_effective_classification(self, object_id: int) -> Classification | None:
        """Get the effective classification for an object.

        If no object-level classification exists, derive from column classifications.
        """
        obj_classification = self.repo.get_by_object(object_id)
        if obj_classification:
            return obj_classification

        # Derive from columns (highest classification wins)
        column_classifications = self.repo.get_by_object_columns(object_id)
        if not column_classifications:
            return None

        # Return highest classification level
        level_order = [
            ClassificationLevel.PUBLIC,
            ClassificationLevel.INTERNAL,
            ClassificationLevel.CONFIDENTIAL,
            ClassificationLevel.RESTRICTED,
        ]

        highest = max(column_classifications, key=lambda c: level_order.index(c.level))
        return highest
```

### 10.3 Ownership Service

```python
# src/datacompass/core/services/ownership_service.py
class OwnershipService:
    """Service for managing data ownership."""

    def __init__(self, session: Session, user_id: str = "system") -> None:
        self.session = session
        self.user_id = user_id
        self.repo = OwnershipRepository(session)
        self.audit = AuditService(session)

    def assign_owner(
        self,
        object_id: int,
        owner_email: str,
        role: OwnerRole,
        domain_id: int | None = None,
    ) -> ObjectOwner:
        """Assign an owner/steward to an object."""
        # Check if already assigned
        existing = self.repo.get_assignment(object_id, owner_email, role)
        if existing:
            raise ValueError(f"User {owner_email} already has role {role} on this object")

        assignment = ObjectOwner(
            object_id=object_id,
            user_id=owner_email,
            role=role,
            domain_id=domain_id,
            assigned_by=self.user_id,
        )
        self.session.add(assignment)

        self.audit.log_event(
            user_id=self.user_id,
            action="assign_owner",
            entity_type="object",
            entity_id=object_id,
            changes={"owner": owner_email, "role": role.value},
        )

        return assignment

    def remove_owner(self, object_id: int, owner_email: str, role: OwnerRole) -> bool:
        """Remove an owner assignment."""
        assignment = self.repo.get_assignment(object_id, owner_email, role)
        if not assignment:
            return False

        self.session.delete(assignment)

        self.audit.log_event(
            user_id=self.user_id,
            action="remove_owner",
            entity_type="object",
            entity_id=object_id,
            changes={"owner": owner_email, "role": role.value},
        )

        return True

    def get_owners(self, object_id: int) -> list[ObjectOwner]:
        """Get all owners for an object."""
        return self.repo.get_by_object(object_id)

    def get_owned_objects(self, user_email: str) -> list[CatalogObject]:
        """Get all objects owned by a user."""
        return self.repo.get_objects_by_owner(user_email)

    # Domain management
    def create_domain(
        self,
        name: str,
        description: str | None = None,
        parent_id: int | None = None,
    ) -> Domain:
        """Create a business domain."""
        domain = Domain(
            name=name,
            description=description,
            parent_id=parent_id,
            created_by=self.user_id,
        )
        self.session.add(domain)

        self.audit.log_event(
            user_id=self.user_id,
            action="create",
            entity_type="domain",
            entity_id=domain.id,
        )

        return domain

    def assign_to_domain(self, object_id: int, domain_id: int) -> None:
        """Assign an object to a domain."""
        # Update all ownership assignments for this object
        assignments = self.repo.get_by_object(object_id)
        for assignment in assignments:
            assignment.domain_id = domain_id

        self.audit.log_event(
            user_id=self.user_id,
            action="assign_domain",
            entity_type="object",
            entity_id=object_id,
            changes={"domain_id": domain_id},
        )
```

### 10.4 CLI Commands

```bash
# Classification
datacompass classify <object> --level confidential
datacompass classify <object> --level restricted --compliance gdpr hipaa
datacompass classify <object>.<column> --level confidential
datacompass classify list [--source <name>] [--level <level>]
datacompass classify rules list
datacompass classify rules apply [--source <name>]  # Run auto-classification
datacompass classify rules create --name "PII Detection" --config rules.yaml

# Ownership
datacompass owner assign <object> --email owner@company.com
datacompass owner remove <object> --email owner@company.com
datacompass steward assign <object> --email steward@company.com
datacompass owner list <object>
datacompass owner my-objects  # Objects owned by current user

# Domains
datacompass domain create "Customer Data" [--parent "Sales"]
datacompass domain list [--tree]
datacompass domain show "Customer Data"
datacompass domain assign <object> --domain "Customer Data"
datacompass domain objects "Customer Data"  # List objects in domain

# Audit (from Phase 9)
datacompass audit log [--entity-type object] [--user user@company.com] [--since 2024-01-01]
datacompass audit export --format json --output audit.json
```

### 10.5 API Endpoints

```
/api/v1/
├── classification/
│   ├── GET    /                           List all classifications
│   ├── GET    /objects/{id}               Get object classification
│   ├── PUT    /objects/{id}               Set object classification
│   ├── GET    /objects/{id}/columns       Get column classifications
│   ├── PUT    /objects/{id}/columns/{col} Set column classification
│   ├── GET    /rules                      List classification rules
│   ├── POST   /rules                      Create classification rule
│   ├── PATCH  /rules/{id}                 Update rule
│   ├── DELETE /rules/{id}                 Delete rule
│   └── POST   /rules/apply                Apply rules to objects
│
├── ownership/
│   ├── GET    /objects/{id}               Get object owners
│   ├── POST   /objects/{id}               Assign owner
│   ├── DELETE /objects/{id}/{email}       Remove owner
│   ├── GET    /my-objects                 Objects owned by current user
│   ├── GET    /domains                    List domains
│   ├── POST   /domains                    Create domain
│   ├── GET    /domains/{id}               Get domain details
│   ├── PATCH  /domains/{id}               Update domain
│   ├── DELETE /domains/{id}               Delete domain
│   ├── GET    /domains/{id}/objects       Objects in domain
│   └── POST   /domains/{id}/objects/{obj} Assign object to domain
│
└── audit/
    ├── GET    /events                     Query audit log
    └── GET    /events/export              Export audit log
```

### 10.6 Web UI Components

```
frontend/src/
├── components/
│   ├── ClassificationBadge.tsx      # Visual badge for classification level
│   ├── ComplianceTags.tsx           # Tags for compliance labels
│   ├── OwnershipPanel.tsx           # Panel showing owners/stewards
│   ├── DomainBreadcrumb.tsx         # Domain hierarchy breadcrumb
│   └── AuditLogTable.tsx            # Paginated audit log viewer
│
├── pages/
│   ├── ClassificationPage.tsx       # Classification management dashboard
│   ├── DomainsPage.tsx              # Domain hierarchy viewer
│   └── AuditLogPage.tsx             # Audit log explorer
│
└── hooks/
    ├── useClassification.ts         # TanStack Query hooks
    ├── useOwnership.ts
    ├── useDomains.ts
    └── useAudit.ts
```

### 10.7 Configuration Files

```yaml
# classification-rules.yaml
rules:
  - name: "PII - Email Addresses"
    match:
      column_name_pattern: "(?i)(email|e_mail|email_address|contact_email)"
    apply:
      level: confidential
      compliance: [gdpr]

  - name: "PII - SSN/National ID"
    match:
      column_name_pattern: "(?i)(ssn|social_security|national_id|tax_id)"
    apply:
      level: restricted
      compliance: [gdpr, hipaa]

  - name: "Financial Data"
    match:
      schema_pattern: "(?i)(finance|accounting|billing)"
    apply:
      level: confidential
      compliance: [sox, pci_dss]

  - name: "Health Records"
    match:
      tags: [phi, health, medical]
    apply:
      level: restricted
      compliance: [hipaa]

  - name: "PII - Phone Numbers"
    match:
      column_name_pattern: "(?i)(phone|mobile|cell|telephone)"
    apply:
      level: confidential
      compliance: [gdpr]
```

Apply with: `datacompass classify rules apply --config classification-rules.yaml`

### Phase 10 Milestone

✅ Objects can be classified with sensitivity levels and compliance labels
✅ Auto-classification rules process objects based on patterns
✅ Objects have owners and stewards assigned
✅ Objects are organized into business domains
✅ All changes are audited

**Test**:
```bash
# Classify an object
datacompass classify prod.customers.users --level confidential --compliance gdpr

# Assign owner
datacompass owner assign prod.customers.users --email data-team@company.com

# View audit trail
datacompass audit log --entity-type object --since 2024-01-01 | jq '.[] | .action'
```

---

## Phase 6 Completion: DQ Adapter Integration & Backfill

**Goal**: Execute real DQ metric queries against data sources and support historical backfill.

**Current State**: DQ system is fully functional with mock metric values. The infrastructure (configs, expectations, breaches, thresholds) is production-ready, but `DQService._execute_metrics()` returns simulated values.

### 6.1 Adapter Interface for DQ Queries

The `SourceAdapter` base class already defines the interface:

```python
# src/datacompass/core/adapters/base.py
class SourceAdapter(ABC):
    SUPPORTED_DQ_METRICS: ClassVar[list[str]] = []

    @abstractmethod
    async def execute_dq_query(self, query: DQQuery) -> list[dict]:
        """Execute a data quality query and return results.

        Args:
            query: DQQuery object containing metric type, target, date range

        Returns:
            List of dicts with keys: snapshot_date, metric_value
        """
        ...
```

#### DQQuery Model

```python
# src/datacompass/core/models/dq.py
from pydantic import BaseModel
from datetime import date

class DQQuery(BaseModel):
    """Query specification for DQ metric execution."""
    metric_type: str              # row_count, null_count, distinct_count, etc.
    schema_name: str              # Target schema
    object_name: str              # Target table/view
    column_name: str | None       # For column-level metrics
    date_column: str              # Column to filter by date
    date_format: str | None       # Date format pattern if needed
    start_date: date              # Inclusive start
    end_date: date                # Inclusive end
    grain: str                    # daily, weekly, monthly

    def get_date_filter_sql(self, dialect: str = "standard") -> str:
        """Generate date filter clause for the query."""
        if self.grain == "daily":
            return f"DATE({self.date_column}) BETWEEN '{self.start_date}' AND '{self.end_date}'"
        elif self.grain == "weekly":
            return f"DATE_TRUNC('week', {self.date_column}) BETWEEN '{self.start_date}' AND '{self.end_date}'"
        elif self.grain == "monthly":
            return f"DATE_TRUNC('month', {self.date_column}) BETWEEN '{self.start_date}' AND '{self.end_date}'"
```

### 6.2 PostgreSQL Adapter Implementation

```python
# src/datacompass/core/adapters/postgresql.py

class PostgreSQLAdapter(SourceAdapter):
    SUPPORTED_DQ_METRICS = [
        "row_count",
        "distinct_count",
        "null_count",
        "max_length",
        "min",
        "max",
        "mean",
        "sum",
        "median",
    ]

    async def execute_dq_query(self, query: DQQuery) -> list[dict]:
        """Execute DQ metric query against PostgreSQL."""
        sql = self._build_metric_query(query)

        async with self._get_connection() as conn:
            result = await conn.fetch(sql)

        return [
            {
                "snapshot_date": row["snapshot_date"],
                "metric_value": float(row["metric_value"]) if row["metric_value"] is not None else None,
            }
            for row in result
        ]

    def _build_metric_query(self, query: DQQuery) -> str:
        """Build SQL query for the specified metric."""
        fqn = f'"{query.schema_name}"."{query.object_name}"'
        date_col = f'"{query.date_column}"'

        # Date grouping expression
        if query.grain == "daily":
            date_expr = f"DATE({date_col})"
        elif query.grain == "weekly":
            date_expr = f"DATE_TRUNC('week', {date_col})::date"
        elif query.grain == "monthly":
            date_expr = f"DATE_TRUNC('month', {date_col})::date"
        else:
            date_expr = f"DATE({date_col})"

        # Metric expression
        metric_expr = self._get_metric_expression(query.metric_type, query.column_name)

        sql = f"""
            SELECT
                {date_expr} AS snapshot_date,
                {metric_expr} AS metric_value
            FROM {fqn}
            WHERE {date_col} >= '{query.start_date}'
              AND {date_col} < '{query.end_date}'::date + INTERVAL '1 day'
            GROUP BY {date_expr}
            ORDER BY snapshot_date
        """
        return sql

    def _get_metric_expression(self, metric_type: str, column_name: str | None) -> str:
        """Get SQL expression for metric type."""
        col = f'"{column_name}"' if column_name else None

        expressions = {
            "row_count": "COUNT(*)",
            "distinct_count": f"COUNT(DISTINCT {col})",
            "null_count": f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)",
            "max_length": f"MAX(LENGTH({col}::text))",
            "min": f"MIN({col})",
            "max": f"MAX({col})",
            "mean": f"AVG({col}::numeric)",
            "sum": f"SUM({col}::numeric)",
            "median": f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {col})",
        }

        if metric_type not in expressions:
            raise ValueError(f"Unsupported metric type: {metric_type}")

        expr = expressions[metric_type]
        if col is None and metric_type != "row_count":
            raise ValueError(f"Metric {metric_type} requires a column_name")

        return expr
```

### 6.3 Databricks Adapter Implementation

```python
# src/datacompass/core/adapters/databricks.py

class DatabricksAdapter(SourceAdapter):
    SUPPORTED_DQ_METRICS = [
        "row_count",
        "distinct_count",
        "null_count",
        "max_length",
        "min",
        "max",
        "mean",
        "sum",
        "median",
    ]

    async def execute_dq_query(self, query: DQQuery) -> list[dict]:
        """Execute DQ metric query against Databricks SQL."""
        sql = self._build_metric_query(query)

        async with self._get_cursor() as cursor:
            await cursor.execute(sql)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

        return [
            {
                "snapshot_date": row[columns.index("snapshot_date")],
                "metric_value": float(row[columns.index("metric_value")])
                    if row[columns.index("metric_value")] is not None else None,
            }
            for row in rows
        ]

    def _build_metric_query(self, query: DQQuery) -> str:
        """Build Spark SQL query for the specified metric."""
        fqn = f"`{self.catalog}`.`{query.schema_name}`.`{query.object_name}`"
        date_col = f"`{query.date_column}`"

        # Date grouping (Databricks/Spark SQL syntax)
        if query.grain == "daily":
            date_expr = f"DATE({date_col})"
        elif query.grain == "weekly":
            date_expr = f"DATE_TRUNC('week', {date_col})"
        elif query.grain == "monthly":
            date_expr = f"DATE_TRUNC('month', {date_col})"
        else:
            date_expr = f"DATE({date_col})"

        metric_expr = self._get_metric_expression(query.metric_type, query.column_name)

        sql = f"""
            SELECT
                {date_expr} AS snapshot_date,
                {metric_expr} AS metric_value
            FROM {fqn}
            WHERE {date_col} >= '{query.start_date}'
              AND {date_col} <= '{query.end_date}'
            GROUP BY {date_expr}
            ORDER BY snapshot_date
        """
        return sql

    def _get_metric_expression(self, metric_type: str, column_name: str | None) -> str:
        """Get Spark SQL expression for metric type."""
        col = f"`{column_name}`" if column_name else None

        expressions = {
            "row_count": "COUNT(*)",
            "distinct_count": f"COUNT(DISTINCT {col})",
            "null_count": f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)",
            "max_length": f"MAX(LENGTH(CAST({col} AS STRING)))",
            "min": f"MIN({col})",
            "max": f"MAX({col})",
            "mean": f"AVG(CAST({col} AS DOUBLE))",
            "sum": f"SUM(CAST({col} AS DOUBLE))",
            "median": f"PERCENTILE({col}, 0.5)",  # Spark SQL syntax
        }

        if metric_type not in expressions:
            raise ValueError(f"Unsupported metric type: {metric_type}")

        return expressions[metric_type]
```

### 6.4 DQService Integration

Update `DQService` to use real adapter queries instead of mock values:

```python
# src/datacompass/core/services/dq_service.py

class DQService:
    def __init__(self, session: Session, user_id: str = "system") -> None:
        self.session = session
        self.user_id = user_id
        self.repo = DQRepository(session)
        self.catalog_repo = CatalogRepository(session)
        self.source_repo = SourceRepository(session)

    async def run_expectations(
        self,
        config_id: int,
        target_date: date | None = None,
    ) -> list[DQResult]:
        """Run all enabled expectations for a DQ config."""
        config = self.repo.get_config(config_id)
        if not config:
            raise ValueError(f"DQ config {config_id} not found")

        obj = self.catalog_repo.get_by_id(config.object_id)
        source = self.source_repo.get_by_id(obj.source_id)

        # Get adapter for the source
        adapter = get_adapter(source.source_type, source.connection_info)

        target_date = target_date or date.today() - timedelta(days=1)
        results = []

        for expectation in config.expectations:
            if not expectation.is_enabled:
                continue

            try:
                # Build query
                query = DQQuery(
                    metric_type=expectation.metric_type,
                    schema_name=obj.schema_name,
                    object_name=obj.object_name,
                    column_name=expectation.column_name,
                    date_column=config.date_column,
                    date_format=config.date_format,
                    start_date=target_date,
                    end_date=target_date,
                    grain=config.grain,
                )

                # Execute query via adapter
                async with adapter:
                    query_results = await adapter.execute_dq_query(query)

                if query_results:
                    metric_value = query_results[0]["metric_value"]
                else:
                    metric_value = None

                # Store result
                result = self._store_result(expectation.id, target_date, metric_value)
                results.append(result)

                # Check for breaches
                self._check_breach(expectation, result)

            except Exception as e:
                logger.error(f"Failed to execute DQ query for expectation {expectation.id}: {e}")
                # Store error result
                result = self._store_result(
                    expectation.id,
                    target_date,
                    metric_value=None,
                    error=str(e),
                )
                results.append(result)

        return results

    def _store_result(
        self,
        expectation_id: int,
        snapshot_date: date,
        metric_value: float | None,
        error: str | None = None,
    ) -> DQResult:
        """Store or update a DQ result."""
        existing = self.repo.get_result(expectation_id, snapshot_date)

        if existing:
            existing.metric_value = metric_value
            existing.error = error
            existing.executed_at = datetime.utcnow()
            return existing

        result = DQResult(
            expectation_id=expectation_id,
            snapshot_date=snapshot_date,
            metric_value=metric_value,
            error=error,
        )
        self.session.add(result)
        return result
```

### 6.5 Backfill Command

```python
# In src/datacompass/cli/main.py

@dq_app.command("backfill")
def dq_backfill(
    object_ref: Annotated[str, typer.Argument(help="Object reference (source.schema.object)")],
    days: Annotated[int, typer.Option("--days", "-d", help="Number of days to backfill")] = 30,
    start_date: Annotated[str | None, typer.Option("--start", help="Start date (YYYY-MM-DD)")] = None,
    end_date: Annotated[str | None, typer.Option("--end", help="End date (YYYY-MM-DD)")] = None,
    parallel: Annotated[int, typer.Option("--parallel", "-p", help="Parallel execution")] = 1,
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.json,
) -> None:
    """Backfill DQ metrics for historical dates.

    Examples:
        # Backfill last 30 days
        datacompass dq backfill prod.analytics.orders --days 30

        # Backfill specific date range
        datacompass dq backfill prod.analytics.orders --start 2024-01-01 --end 2024-01-31

        # Parallel execution (careful with rate limits)
        datacompass dq backfill prod.analytics.orders --days 90 --parallel 4
    """
    try:
        with get_session() as session:
            service = DQService(session, user_id=get_current_user())
            catalog_service = CatalogService(session)

            # Resolve object
            obj = catalog_service.resolve_object_ref(object_ref)
            if not obj:
                raise ValueError(f"Object not found: {object_ref}")

            # Get DQ config
            config = service.get_config_by_object(obj.id)
            if not config:
                raise ValueError(f"No DQ config for object: {object_ref}")

            # Determine date range
            if start_date and end_date:
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
            else:
                end = date.today() - timedelta(days=1)
                start = end - timedelta(days=days - 1)

            # Generate dates to backfill
            dates_to_fill = []
            current = start
            while current <= end:
                dates_to_fill.append(current)
                if config.grain == "daily":
                    current += timedelta(days=1)
                elif config.grain == "weekly":
                    current += timedelta(weeks=1)
                elif config.grain == "monthly":
                    # Move to next month
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)

            console.print(f"Backfilling {len(dates_to_fill)} periods from {start} to {end}")

            results = {"success": 0, "failed": 0, "dates": []}

            # Execute backfill
            if parallel > 1:
                # Parallel execution with asyncio
                import asyncio
                from concurrent.futures import ThreadPoolExecutor

                async def run_date(d: date) -> dict:
                    try:
                        run_results = await service.run_expectations(config.id, target_date=d)
                        return {"date": d.isoformat(), "status": "success", "results": len(run_results)}
                    except Exception as e:
                        return {"date": d.isoformat(), "status": "failed", "error": str(e)}

                async def run_all():
                    tasks = [run_date(d) for d in dates_to_fill]
                    # Batch to avoid overwhelming the source
                    batch_size = parallel
                    all_results = []
                    for i in range(0, len(tasks), batch_size):
                        batch = tasks[i:i + batch_size]
                        batch_results = await asyncio.gather(*batch)
                        all_results.extend(batch_results)
                    return all_results

                date_results = asyncio.run(run_all())
            else:
                # Sequential execution
                date_results = []
                with Progress(console=console) as progress:
                    task = progress.add_task("Backfilling...", total=len(dates_to_fill))
                    for d in dates_to_fill:
                        try:
                            run_results = asyncio.run(
                                service.run_expectations(config.id, target_date=d)
                            )
                            date_results.append({
                                "date": d.isoformat(),
                                "status": "success",
                                "results": len(run_results),
                            })
                            results["success"] += 1
                        except Exception as e:
                            date_results.append({
                                "date": d.isoformat(),
                                "status": "failed",
                                "error": str(e),
                            })
                            results["failed"] += 1
                        progress.advance(task)

            session.commit()

            results["dates"] = date_results
            results["success"] = sum(1 for d in date_results if d["status"] == "success")
            results["failed"] = sum(1 for d in date_results if d["status"] == "failed")

            output_result(results, format)

    except Exception as e:
        handle_error(e)
```

### 6.6 Trend Charts in Web UI

Add trend visualization to the DQ Hub and object detail pages.

```tsx
// frontend/src/components/DQTrendChart.tsx
import { Line } from '@ant-design/charts';
import { useQuery } from '@tanstack/react-query';
import { getDQResults } from '../api/client';

interface DQTrendChartProps {
  expectationId: number;
  days?: number;
}

export function DQTrendChart({ expectationId, days = 30 }: DQTrendChartProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['dq-results', expectationId, days],
    queryFn: () => getDQResults(expectationId, days),
  });

  if (isLoading) return <Spin />;

  const chartData = data?.results.map(r => ({
    date: r.snapshot_date,
    value: r.metric_value,
    threshold_upper: r.threshold_upper,
    threshold_lower: r.threshold_lower,
    is_breach: r.is_breach,
  })) || [];

  const config = {
    data: chartData,
    xField: 'date',
    yField: 'value',
    point: {
      size: 4,
      shape: 'circle',
      style: (datum: any) => ({
        fill: datum.is_breach ? '#ff4d4f' : '#1890ff',
      }),
    },
    annotations: [
      // Upper threshold line
      {
        type: 'line',
        yField: 'threshold_upper',
        style: { stroke: '#ff7875', lineDash: [4, 4] },
      },
      // Lower threshold line
      {
        type: 'line',
        yField: 'threshold_lower',
        style: { stroke: '#ff7875', lineDash: [4, 4] },
      },
    ],
    tooltip: {
      fields: ['value', 'threshold_upper', 'threshold_lower', 'is_breach'],
    },
  };

  return <Line {...config} />;
}
```

```tsx
// frontend/src/components/DQExpectationCard.tsx
import { Card, Statistic, Row, Col } from 'antd';
import { DQTrendChart } from './DQTrendChart';

interface DQExpectationCardProps {
  expectation: DQExpectation;
  latestResult: DQResult | null;
}

export function DQExpectationCard({ expectation, latestResult }: DQExpectationCardProps) {
  return (
    <Card
      title={`${expectation.metric_type}${expectation.column_name ? ` (${expectation.column_name})` : ''}`}
      extra={<PriorityBadge priority={expectation.priority} />}
    >
      <Row gutter={16}>
        <Col span={8}>
          <Statistic
            title="Latest Value"
            value={latestResult?.metric_value ?? 'N/A'}
            valueStyle={{
              color: latestResult?.is_breach ? '#ff4d4f' : '#3f8600',
            }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="Threshold"
            value={`${latestResult?.threshold_lower ?? '?'} - ${latestResult?.threshold_upper ?? '?'}`}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="Last Run"
            value={latestResult?.executed_at ? dayjs(latestResult.executed_at).fromNow() : 'Never'}
          />
        </Col>
      </Row>

      <Divider />

      <DQTrendChart expectationId={expectation.id} days={30} />
    </Card>
  );
}
```

### 6.7 API Endpoints for Trend Data

```python
# src/datacompass/api/routes/dq.py

@router.get("/expectations/{expectation_id}/results")
async def get_expectation_results(
    expectation_id: int,
    days: int = Query(30, ge=1, le=365),
    service: DQServiceDep,
) -> dict:
    """Get historical results for an expectation."""
    results = service.get_results_for_expectation(
        expectation_id=expectation_id,
        days=days,
    )

    return {
        "expectation_id": expectation_id,
        "results": [
            {
                "snapshot_date": r.snapshot_date.isoformat(),
                "metric_value": r.metric_value,
                "threshold_upper": r.threshold_upper,
                "threshold_lower": r.threshold_lower,
                "is_breach": r.breach_id is not None,
                "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            }
            for r in results
        ],
    }

@router.get("/configs/{config_id}/summary")
async def get_config_summary(
    config_id: int,
    service: DQServiceDep,
) -> dict:
    """Get summary with trend data for a DQ config."""
    config = service.get_config(config_id)
    if not config:
        raise HTTPException(404, "Config not found")

    return {
        "config": config.to_response(),
        "expectations": [
            {
                "expectation": exp.to_response(),
                "latest_result": service.get_latest_result(exp.id),
                "breach_count_30d": service.count_breaches(exp.id, days=30),
                "trend": service.get_trend_summary(exp.id, days=7),  # up, down, stable
            }
            for exp in config.expectations
        ],
    }
```

### 6.8 Tasks Checklist

#### Adapter Implementation
- [ ] Add `DQQuery` model to `models/dq.py`
- [ ] Implement `execute_dq_query()` in `PostgreSQLAdapter`
- [ ] Implement `execute_dq_query()` in `DatabricksAdapter`
- [ ] Add adapter tests with mock database responses
- [ ] Handle connection errors and timeouts gracefully
- [ ] Add query timeout configuration

#### DQService Integration
- [ ] Update `DQService.run_expectations()` to use adapter queries
- [ ] Remove mock value generation code
- [ ] Add error handling for query failures
- [ ] Store query errors in `DQResult.error` field
- [ ] Add `DQResult.error` column if not exists (migration)

#### Backfill Command
- [ ] Implement `datacompass dq backfill` command
- [ ] Support `--days`, `--start`, `--end` options
- [ ] Support `--parallel` for concurrent execution
- [ ] Add progress bar for sequential execution
- [ ] Add rate limiting to avoid overwhelming sources
- [ ] Add tests for backfill command

#### Web UI Trends
- [ ] Install @ant-design/charts: `npm install @ant-design/charts`
- [ ] Create `DQTrendChart` component
- [ ] Create `DQExpectationCard` component with embedded chart
- [ ] Add trend charts to DQ Hub page
- [ ] Add trend charts to object detail DQ tab
- [ ] Add API endpoint `GET /api/v1/dq/expectations/{id}/results`
- [ ] Add API endpoint `GET /api/v1/dq/configs/{id}/summary`
- [ ] Add TanStack Query hooks for trend data

#### Testing
- [ ] Unit tests for adapter `_build_metric_query()` methods
- [ ] Integration tests for `execute_dq_query()` with test database
- [ ] CLI tests for backfill command
- [ ] API tests for trend endpoints
- [ ] Frontend component tests for charts

### Phase 6 Milestone

✅ DQ metrics execute real queries against PostgreSQL and Databricks
✅ Historical data can be backfilled with a single command
✅ Trend charts visualize metric history and threshold breaches
✅ Query errors are captured and reported

**Test**:
```bash
# Run DQ checks with real data
datacompass dq run prod.analytics.orders

# Backfill 30 days of history
datacompass dq backfill prod.analytics.orders --days 30

# View results
datacompass dq status prod.analytics.orders --format table
```

---

## Deferred Items

### External Auth Providers (Phase 9.4)

Deferred until SSO environment available:

- [ ] OIDC provider (Azure AD, Okta, Google)
- [ ] LDAP provider
- [ ] Auto-registration on first login
- [ ] Group-to-role mapping

See `docs/oidc-implementation-guide.md` for implementation details.

---

## Implementation Order

Recommended order to maximize value while minimizing dependencies:

```
1. Phase 6 Completion - DQ Adapter Integration
   └── Real metric execution (high value, independent)

2. Phase 9.1 - Audit Trail (foundation for governance)
   └── Enables tracking all subsequent changes

3. Phase 8 Completion - Scheduler + Notifications
   └── Operationalizes existing DQ and scan features

4. Phase 9.2 - Observability
   └── Production visibility

5. Phase 9.3 - Docker Deployment
   └── Production deployment ready

6. Phase 10.1-10.2 - Classification + Ownership
   └── Core governance features

7. Phase 10.3-10.4 - Domains + CLI/API/Web
   └── Complete governance UI

8. Phase 9.4 - External Auth (when needed)
   └── Enterprise SSO
```

---

## Summary

| Phase | Scope | Effort |
|-------|-------|--------|
| 6 Completion | DQ adapter queries, backfill, trend charts | Medium |
| 8 Completion | Scheduler daemon, notification handlers | Medium |
| 9.1 | Audit trail with change tracking | Medium |
| 9.2 | Prometheus metrics, structured logging | Small |
| 9.3 | Docker deployment configuration | Small |
| 10.1 | Classification system + auto-rules | Medium |
| 10.2 | Ownership + domain hierarchy | Medium |
| 10.3 | Governance CLI/API/Web | Medium |
| 9.4 | OIDC/LDAP providers | Large (deferred) |

Total remaining: ~7-9 weeks of focused development.
