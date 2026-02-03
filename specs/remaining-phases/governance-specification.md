# Data Compass - Phase 10 Governance Technical Specification

## Overview

This specification details the governance features for Data Compass:
- **Classification**: Sensitivity levels and compliance labels for objects/columns
- **Ownership**: Data owners, stewards, and business domain hierarchy
- **Audit**: Complete change tracking with before/after snapshots

---

## 1. Data Models

### 1.1 Classification

```python
class ClassificationLevel(str, Enum):
    """Data sensitivity levels, from least to most sensitive."""
    PUBLIC = "public"           # No restrictions
    INTERNAL = "internal"       # Internal use only
    CONFIDENTIAL = "confidential"  # Business-sensitive
    RESTRICTED = "restricted"   # Highly sensitive (PII, PHI, etc.)

class ComplianceLabel(str, Enum):
    """Regulatory compliance frameworks."""
    GDPR = "gdpr"       # EU General Data Protection Regulation
    HIPAA = "hipaa"     # US Health Insurance Portability
    PCI_DSS = "pci_dss" # Payment Card Industry
    SOX = "sox"         # Sarbanes-Oxley
    CCPA = "ccpa"       # California Consumer Privacy Act
    FERPA = "ferpa"     # Family Educational Rights and Privacy Act
```

#### Classification Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `object_id` | int (FK) | Reference to catalog_objects |
| `column_id` | int (FK, nullable) | Reference to columns (null = object-level) |
| `level` | ClassificationLevel | Sensitivity level |
| `compliance_labels` | JSON array | List of compliance labels |
| `classified_by` | string | User who classified |
| `classified_at` | datetime | When classified |
| `source` | string | How classified: manual, rule, inherited |

**Constraints**:
- Unique constraint on (object_id, column_id) - only one classification per target
- Column-level classification inherits object_id from parent

#### Classification Rule Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `name` | string | Rule name |
| `description` | string | Rule description |
| `is_enabled` | bool | Whether rule is active |
| `priority` | int | Lower = higher priority (default 100) |
| `match_conditions` | JSON | Matching criteria |
| `apply_level` | ClassificationLevel | Level to apply |
| `apply_compliance` | JSON array | Compliance labels to apply |
| `created_at` | datetime | Creation timestamp |
| `created_by` | string | Creator user |

**Match Conditions Schema**:
```json
{
  "column_name_pattern": "regex pattern",
  "object_name_pattern": "regex pattern",
  "schema_pattern": "regex pattern",
  "source_pattern": "regex pattern",
  "tags": ["tag1", "tag2"],
  "object_types": ["TABLE", "VIEW"]
}
```

### 1.2 Ownership

```python
class OwnerRole(str, Enum):
    """Ownership role types."""
    OWNER = "owner"       # Business owner, accountable for data
    STEWARD = "steward"   # Technical steward, manages quality
    DELEGATE = "delegate" # Delegated authority from owner
```

#### Domain Model (Business Hierarchy)

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `name` | string | Domain name (unique) |
| `description` | string | Domain description |
| `parent_id` | int (FK, nullable) | Parent domain for hierarchy |
| `created_at` | datetime | Creation timestamp |
| `created_by` | string | Creator user |

**Example Hierarchy**:
```
Sales
├── Customer Data
│   ├── CRM
│   └── Marketing
└── Orders
    ├── Transactions
    └── Fulfillment
```

#### Object Owner Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `object_id` | int (FK) | Reference to catalog_objects |
| `domain_id` | int (FK, nullable) | Reference to domains |
| `user_id` | string | User email/identifier |
| `role` | OwnerRole | owner, steward, or delegate |
| `assigned_by` | string | Who made the assignment |
| `assigned_at` | datetime | When assigned |

**Constraints**:
- Unique constraint on (object_id, user_id, role) - prevent duplicate assignments
- An object can have multiple owners/stewards

### 1.3 Audit Events

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `timestamp` | datetime | Event timestamp |
| `user_id` | string | User who performed action |
| `action` | string | Action type (see below) |
| `entity_type` | string | Type of entity affected |
| `entity_id` | int | ID of entity affected |
| `changes` | JSON | Before/after field changes |
| `context` | JSON | Request context (IP, user agent, etc.) |

**Action Types**:
- `create` - Entity created
- `update` - Entity modified
- `delete` - Entity deleted
- `classify` - Classification assigned
- `assign_owner` - Owner assigned
- `remove_owner` - Owner removed
- `assign_domain` - Domain assigned
- `login` - User logged in
- `logout` - User logged out
- `view` - Entity viewed (optional, high volume)

**Entity Types**:
- `object` - Catalog object
- `column` - Column
- `classification` - Classification record
- `domain` - Business domain
- `owner` - Ownership assignment
- `dq_config` - DQ configuration
- `dq_breach` - DQ breach
- `campaign` - Deprecation campaign
- `user` - User account
- `apikey` - API key

---

## 2. Service Interfaces

### 2.1 ClassificationService

```python
class ClassificationService:
    def __init__(self, session: Session, user_id: str) -> None: ...

    # Object classification
    def classify_object(
        self,
        object_id: int,
        level: ClassificationLevel,
        compliance_labels: list[str] | None = None,
        source: str = "manual",
    ) -> Classification: ...

    def classify_column(
        self,
        object_id: int,
        column_id: int,
        level: ClassificationLevel,
        compliance_labels: list[str] | None = None,
    ) -> Classification: ...

    def remove_classification(self, object_id: int, column_id: int | None = None) -> bool: ...

    def get_classification(self, object_id: int, column_id: int | None = None) -> Classification | None: ...

    def get_effective_classification(self, object_id: int) -> Classification | None:
        """Get classification, deriving from columns if no object-level exists."""
        ...

    def list_classifications(
        self,
        source_id: int | None = None,
        level: ClassificationLevel | None = None,
        compliance_label: str | None = None,
    ) -> list[Classification]: ...

    # Rules
    def create_rule(
        self,
        name: str,
        match_conditions: dict,
        apply_level: ClassificationLevel,
        apply_compliance: list[str] | None = None,
        description: str | None = None,
        priority: int = 100,
    ) -> ClassificationRule: ...

    def update_rule(self, rule_id: int, **updates) -> ClassificationRule: ...
    def delete_rule(self, rule_id: int) -> bool: ...
    def list_rules(self, enabled_only: bool = False) -> list[ClassificationRule]: ...

    def apply_rules(
        self,
        source_id: int | None = None,
        dry_run: bool = False,
    ) -> dict:
        """Apply classification rules. Returns {classified: N, skipped: N, errors: N}."""
        ...
```

### 2.2 OwnershipService

```python
class OwnershipService:
    def __init__(self, session: Session, user_id: str) -> None: ...

    # Ownership
    def assign_owner(
        self,
        object_id: int,
        owner_email: str,
        role: OwnerRole,
        domain_id: int | None = None,
    ) -> ObjectOwner: ...

    def remove_owner(self, object_id: int, owner_email: str, role: OwnerRole) -> bool: ...

    def get_owners(self, object_id: int) -> list[ObjectOwner]: ...

    def get_owned_objects(
        self,
        user_email: str,
        role: OwnerRole | None = None,
    ) -> list[CatalogObject]: ...

    # Domains
    def create_domain(
        self,
        name: str,
        description: str | None = None,
        parent_id: int | None = None,
    ) -> Domain: ...

    def update_domain(self, domain_id: int, **updates) -> Domain: ...
    def delete_domain(self, domain_id: int) -> bool: ...

    def get_domain(self, domain_id: int) -> Domain | None: ...
    def get_domain_by_name(self, name: str) -> Domain | None: ...

    def list_domains(self, parent_id: int | None = None) -> list[Domain]: ...

    def get_domain_tree(self) -> list[dict]:
        """Get full domain hierarchy as nested structure."""
        ...

    def assign_to_domain(self, object_id: int, domain_id: int) -> None: ...

    def get_domain_objects(self, domain_id: int, include_children: bool = True) -> list[CatalogObject]: ...
```

### 2.3 AuditService

```python
class AuditService:
    def __init__(self, session: Session) -> None: ...

    def log_event(
        self,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: int,
        changes: dict | None = None,
        context: dict | None = None,
    ) -> AuditEvent: ...

    def log_change(
        self,
        user_id: str,
        entity_type: str,
        entity_id: int,
        old_value: dict,
        new_value: dict,
        context: dict | None = None,
    ) -> AuditEvent | None:
        """Log change event with computed diff. Returns None if no changes."""
        ...

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
    ) -> list[AuditEvent]: ...

    def count_events(self, **filters) -> int: ...

    def export_events(
        self,
        since: datetime,
        until: datetime | None = None,
        format: str = "json",
    ) -> str | bytes: ...
```

---

## 3. CLI Commands

### 3.1 Classification Commands

```bash
# Classify objects
datacompass classify <object> --level <level> [--compliance <label>...]
datacompass classify <object>.<column> --level <level> [--compliance <label>...]

# Examples:
datacompass classify prod.customers.users --level confidential --compliance gdpr
datacompass classify prod.customers.users.email --level confidential --compliance gdpr

# Remove classification
datacompass classify <object> --remove

# List classifications
datacompass classify list [--source <name>] [--level <level>] [--compliance <label>]
datacompass classify list --source prod --level restricted

# Rules management
datacompass classify rules list [--enabled]
datacompass classify rules show <rule-id>
datacompass classify rules create --name "Name" --config <yaml>
datacompass classify rules update <rule-id> --disable
datacompass classify rules delete <rule-id>

# Apply rules
datacompass classify rules apply [--source <name>] [--dry-run]
```

### 3.2 Ownership Commands

```bash
# Owner management
datacompass owner assign <object> --email <user@company.com>
datacompass owner remove <object> --email <user@company.com>
datacompass owner list <object>

# Steward management
datacompass steward assign <object> --email <user@company.com>
datacompass steward remove <object> --email <user@company.com>

# My objects
datacompass owner my-objects [--role owner|steward]

# Domain management
datacompass domain create "Domain Name" [--parent "Parent Domain"] [--description "..."]
datacompass domain list [--tree]
datacompass domain show "Domain Name"
datacompass domain update "Domain Name" [--name "New Name"] [--description "..."]
datacompass domain delete "Domain Name"

# Assign objects to domains
datacompass domain assign <object> --domain "Domain Name"
datacompass domain objects "Domain Name" [--include-children]
```

### 3.3 Audit Commands

```bash
# Query audit log
datacompass audit log [--entity-type <type>] [--entity-id <id>] [--user <email>] \
                      [--action <action>] [--since <date>] [--until <date>] \
                      [--limit <n>]

# Examples:
datacompass audit log --entity-type object --since 2024-01-01
datacompass audit log --user admin@company.com --action update
datacompass audit log --entity-type classification

# Export audit log
datacompass audit export --format json --since 2024-01-01 --output audit.json
datacompass audit export --format csv --since 2024-01-01 --output audit.csv

# View specific entity history
datacompass audit history object 123
datacompass audit history classification 45
```

---

## 4. API Endpoints

### 4.1 Classification API

```yaml
/api/v1/classification:
  GET:
    summary: List all classifications
    parameters:
      - source_id: int (optional)
      - level: string (optional)
      - compliance_label: string (optional)
      - page: int
      - limit: int
    response: PaginatedResponse[ClassificationResponse]

  POST /objects/{object_id}:
    summary: Set object classification
    body:
      level: ClassificationLevel (required)
      compliance_labels: list[string] (optional)
    response: ClassificationResponse

  GET /objects/{object_id}:
    summary: Get object classification
    response: ClassificationResponse | null

  DELETE /objects/{object_id}:
    summary: Remove object classification
    response: {success: true}

  POST /objects/{object_id}/columns/{column_id}:
    summary: Set column classification
    body:
      level: ClassificationLevel (required)
      compliance_labels: list[string] (optional)
    response: ClassificationResponse

  GET /objects/{object_id}/columns:
    summary: Get all column classifications for an object
    response: list[ClassificationResponse]

/api/v1/classification/rules:
  GET:
    summary: List classification rules
    parameters:
      - enabled: bool (optional)
    response: list[ClassificationRuleResponse]

  POST:
    summary: Create classification rule
    body:
      name: string (required)
      description: string (optional)
      match_conditions: object (required)
      apply_level: ClassificationLevel (required)
      apply_compliance: list[string] (optional)
      priority: int (optional, default 100)
    response: ClassificationRuleResponse

  PATCH /{rule_id}:
    summary: Update classification rule
    body: (partial ClassificationRule)
    response: ClassificationRuleResponse

  DELETE /{rule_id}:
    summary: Delete classification rule
    response: {success: true}

  POST /apply:
    summary: Apply classification rules to objects
    body:
      source_id: int (optional)
      dry_run: bool (optional, default false)
    response: {classified: int, skipped: int, errors: int}
```

### 4.2 Ownership API

```yaml
/api/v1/ownership:
  GET /objects/{object_id}:
    summary: Get object owners
    response: list[ObjectOwnerResponse]

  POST /objects/{object_id}:
    summary: Assign owner to object
    body:
      user_id: string (required) # email
      role: OwnerRole (required)
      domain_id: int (optional)
    response: ObjectOwnerResponse

  DELETE /objects/{object_id}/{email}:
    summary: Remove owner from object
    parameters:
      - role: OwnerRole (required)
    response: {success: true}

  GET /my-objects:
    summary: Get objects owned by current user
    parameters:
      - role: OwnerRole (optional)
    response: list[ObjectSummaryResponse]

/api/v1/domains:
  GET:
    summary: List domains
    parameters:
      - parent_id: int (optional, filter by parent)
      - tree: bool (optional, return nested structure)
    response: list[DomainResponse] | DomainTree

  POST:
    summary: Create domain
    body:
      name: string (required)
      description: string (optional)
      parent_id: int (optional)
    response: DomainResponse

  GET /{domain_id}:
    summary: Get domain details
    response: DomainResponse

  PATCH /{domain_id}:
    summary: Update domain
    body: (partial Domain)
    response: DomainResponse

  DELETE /{domain_id}:
    summary: Delete domain
    response: {success: true}

  GET /{domain_id}/objects:
    summary: Get objects in domain
    parameters:
      - include_children: bool (optional, default true)
    response: list[ObjectSummaryResponse]

  POST /{domain_id}/objects/{object_id}:
    summary: Assign object to domain
    response: {success: true}
```

### 4.3 Audit API

```yaml
/api/v1/audit:
  GET /events:
    summary: Query audit events
    parameters:
      - entity_type: string (optional)
      - entity_id: int (optional)
      - user_id: string (optional)
      - action: string (optional)
      - since: datetime (optional)
      - until: datetime (optional)
      - page: int
      - limit: int
    response: PaginatedResponse[AuditEventResponse]

  GET /events/export:
    summary: Export audit events
    parameters:
      - since: datetime (required)
      - until: datetime (optional)
      - format: string (json | csv)
    response: file download

  GET /entities/{entity_type}/{entity_id}/history:
    summary: Get audit history for specific entity
    response: list[AuditEventResponse]
```

---

## 5. Pydantic Schemas

```python
# Request/Response schemas
class ClassificationRequest(BaseModel):
    level: ClassificationLevel
    compliance_labels: list[str] = []

class ClassificationResponse(BaseModel):
    id: int
    object_id: int
    column_id: int | None
    object_name: str  # Denormalized for convenience
    column_name: str | None
    level: ClassificationLevel
    compliance_labels: list[str]
    classified_by: str
    classified_at: datetime
    source: str

class ClassificationRuleRequest(BaseModel):
    name: str
    description: str | None = None
    match_conditions: dict
    apply_level: ClassificationLevel
    apply_compliance: list[str] = []
    priority: int = 100
    is_enabled: bool = True

class ClassificationRuleResponse(ClassificationRuleRequest):
    id: int
    created_at: datetime
    created_by: str

class DomainRequest(BaseModel):
    name: str
    description: str | None = None
    parent_id: int | None = None

class DomainResponse(DomainRequest):
    id: int
    created_at: datetime
    created_by: str
    children: list["DomainResponse"] = []  # For tree view

class ObjectOwnerRequest(BaseModel):
    user_id: str  # Email
    role: OwnerRole
    domain_id: int | None = None

class ObjectOwnerResponse(ObjectOwnerRequest):
    id: int
    object_id: int
    object_name: str  # Denormalized
    assigned_by: str
    assigned_at: datetime
    domain_name: str | None  # Denormalized

class AuditEventResponse(BaseModel):
    id: int
    timestamp: datetime
    user_id: str
    action: str
    entity_type: str
    entity_id: int
    changes: dict | None
    context: dict | None
```

---

## 6. Configuration

### 6.1 Classification Rules YAML

```yaml
# classification-rules.yaml
rules:
  # PII Detection - Email
  - name: "PII - Email Addresses"
    description: "Classify columns containing email addresses"
    match:
      column_name_pattern: "(?i)(email|e_mail|email_address|contact_email)"
    apply:
      level: confidential
      compliance: [gdpr]
    priority: 10

  # PII Detection - SSN
  - name: "PII - SSN/National ID"
    description: "Classify columns containing social security or national ID numbers"
    match:
      column_name_pattern: "(?i)(ssn|social_security|national_id|tax_id|nin)"
    apply:
      level: restricted
      compliance: [gdpr, hipaa]
    priority: 5

  # Financial Data by Schema
  - name: "Financial Data"
    description: "Classify objects in financial schemas"
    match:
      schema_pattern: "(?i)(finance|accounting|billing|payments)"
    apply:
      level: confidential
      compliance: [sox, pci_dss]
    priority: 50

  # Health Data by Tag
  - name: "Health Records"
    description: "Classify objects tagged as health-related"
    match:
      tags: [phi, health, medical, patient]
    apply:
      level: restricted
      compliance: [hipaa]
    priority: 20

  # Credit Card Data
  - name: "Payment Card Data"
    description: "Classify columns containing credit card information"
    match:
      column_name_pattern: "(?i)(card_number|credit_card|cvv|card_exp)"
    apply:
      level: restricted
      compliance: [pci_dss]
    priority: 5
```

### 6.2 Domain Configuration YAML

```yaml
# domains.yaml
domains:
  - name: "Sales"
    description: "Sales and revenue data"
    children:
      - name: "Customer Data"
        description: "Customer information and CRM data"
        children:
          - name: "CRM"
          - name: "Marketing"
      - name: "Orders"
        description: "Order and transaction data"
        children:
          - name: "Transactions"
          - name: "Fulfillment"

  - name: "Finance"
    description: "Financial and accounting data"
    children:
      - name: "Accounting"
      - name: "Billing"
      - name: "Revenue"

  - name: "HR"
    description: "Human resources data"
    children:
      - name: "Employees"
      - name: "Payroll"
      - name: "Benefits"
```

Apply with: `datacompass domain apply domains.yaml`

---

## 7. Web UI Components

### 7.1 Classification Badge

```tsx
// components/ClassificationBadge.tsx
interface ClassificationBadgeProps {
  level: ClassificationLevel;
  compliance?: string[];
  showCompliance?: boolean;
}

const levelColors = {
  public: 'green',
  internal: 'blue',
  confidential: 'orange',
  restricted: 'red',
};

export function ClassificationBadge({ level, compliance, showCompliance }: ClassificationBadgeProps) {
  return (
    <Space>
      <Tag color={levelColors[level]}>{level.toUpperCase()}</Tag>
      {showCompliance && compliance?.map(label => (
        <Tag key={label}>{label.toUpperCase()}</Tag>
      ))}
    </Space>
  );
}
```

### 7.2 Ownership Panel

```tsx
// components/OwnershipPanel.tsx
interface OwnershipPanelProps {
  objectId: number;
  owners: ObjectOwner[];
  onAssign: (email: string, role: OwnerRole) => void;
  onRemove: (email: string, role: OwnerRole) => void;
}

export function OwnershipPanel({ objectId, owners, onAssign, onRemove }: OwnershipPanelProps) {
  const ownersList = owners.filter(o => o.role === 'owner');
  const stewardsList = owners.filter(o => o.role === 'steward');

  return (
    <Card title="Ownership">
      <Descriptions column={1}>
        <Descriptions.Item label="Owners">
          {ownersList.map(o => (
            <Tag key={o.user_id} closable onClose={() => onRemove(o.user_id, 'owner')}>
              {o.user_id}
            </Tag>
          ))}
          <AddOwnerButton role="owner" onAdd={(email) => onAssign(email, 'owner')} />
        </Descriptions.Item>
        <Descriptions.Item label="Stewards">
          {stewardsList.map(o => (
            <Tag key={o.user_id} closable onClose={() => onRemove(o.user_id, 'steward')}>
              {o.user_id}
            </Tag>
          ))}
          <AddOwnerButton role="steward" onAdd={(email) => onAssign(email, 'steward')} />
        </Descriptions.Item>
        <Descriptions.Item label="Domain">
          {owners[0]?.domain_name || 'Unassigned'}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
```

### 7.3 Audit Log Table

```tsx
// components/AuditLogTable.tsx
interface AuditLogTableProps {
  events: AuditEvent[];
  loading: boolean;
  pagination: PaginationProps;
}

export function AuditLogTable({ events, loading, pagination }: AuditLogTableProps) {
  const columns = [
    {
      title: 'Time',
      dataIndex: 'timestamp',
      render: (ts: string) => dayjs(ts).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: 'User',
      dataIndex: 'user_id',
    },
    {
      title: 'Action',
      dataIndex: 'action',
      render: (action: string) => <Tag>{action}</Tag>,
    },
    {
      title: 'Entity',
      render: (_, record) => `${record.entity_type}:${record.entity_id}`,
    },
    {
      title: 'Changes',
      dataIndex: 'changes',
      render: (changes: object) => changes ? <ChangesPopover changes={changes} /> : '-',
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={events}
      loading={loading}
      pagination={pagination}
      rowKey="id"
    />
  );
}
```

---

## 8. Migration Script

```python
# src/datacompass/core/migrations/versions/009_governance.py
"""Add governance tables.

Revision ID: 009
Revises: 008
Create Date: 2024-XX-XX
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Domains table
    op.create_table(
        'domains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['domains.id']),
        sa.UniqueConstraint('name'),
    )

    # Classifications table
    op.create_table(
        'classifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('object_id', sa.Integer(), nullable=False),
        sa.Column('column_id', sa.Integer(), nullable=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('compliance_labels', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('classified_by', sa.String(255), nullable=False),
        sa.Column('classified_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('source', sa.String(20), nullable=False, server_default='manual'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['object_id'], ['catalog_objects.id']),
        sa.ForeignKeyConstraint(['column_id'], ['columns.id']),
        sa.UniqueConstraint('object_id', 'column_id', name='uq_classification_target'),
    )
    op.create_index('ix_classifications_level', 'classifications', ['level'])

    # Classification rules table
    op.create_table(
        'classification_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('match_conditions', sa.JSON(), nullable=False),
        sa.Column('apply_level', sa.String(20), nullable=False),
        sa.Column('apply_compliance', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Object owners table
    op.create_table(
        'object_owners',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('object_id', sa.Integer(), nullable=False),
        sa.Column('domain_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('assigned_by', sa.String(255), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['object_id'], ['catalog_objects.id']),
        sa.ForeignKeyConstraint(['domain_id'], ['domains.id']),
        sa.UniqueConstraint('object_id', 'user_id', 'role', name='uq_owner_assignment'),
    )
    op.create_index('ix_object_owners_user', 'object_owners', ['user_id'])

    # Audit events table
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_user', 'audit_events', ['user_id'])
    op.create_index('ix_audit_entity', 'audit_events', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_timestamp', 'audit_events', ['timestamp'])

def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('object_owners')
    op.drop_table('classification_rules')
    op.drop_table('classifications')
    op.drop_table('domains')
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# tests/core/services/test_classification_service.py
class TestClassificationService:
    def test_classify_object(self, session, sample_object):
        service = ClassificationService(session, user_id="test@example.com")
        classification = service.classify_object(
            object_id=sample_object.id,
            level=ClassificationLevel.CONFIDENTIAL,
            compliance_labels=["gdpr"],
        )
        assert classification.level == ClassificationLevel.CONFIDENTIAL
        assert "gdpr" in classification.compliance_labels

    def test_classify_object_updates_existing(self, session, classified_object):
        service = ClassificationService(session, user_id="test@example.com")
        classification = service.classify_object(
            object_id=classified_object.id,
            level=ClassificationLevel.RESTRICTED,
        )
        assert classification.level == ClassificationLevel.RESTRICTED

    def test_apply_rules_matches_pattern(self, session, sample_object_with_email_column):
        service = ClassificationService(session, user_id="test@example.com")
        service.create_rule(
            name="Email PII",
            match_conditions={"column_name_pattern": "(?i)email"},
            apply_level=ClassificationLevel.CONFIDENTIAL,
        )
        results = service.apply_rules()
        assert results["classified"] >= 1

    def test_effective_classification_inherits_from_columns(self, session, object_with_classified_columns):
        service = ClassificationService(session, user_id="test@example.com")
        effective = service.get_effective_classification(object_with_classified_columns.id)
        # Should return highest column classification
        assert effective.level == ClassificationLevel.RESTRICTED
```

### 9.2 Integration Tests

```python
# tests/api/test_classification_api.py
class TestClassificationAPI:
    def test_set_classification(self, client, sample_object):
        response = client.post(
            f"/api/v1/classification/objects/{sample_object.id}",
            json={"level": "confidential", "compliance_labels": ["gdpr"]},
        )
        assert response.status_code == 200
        assert response.json()["level"] == "confidential"

    def test_apply_rules(self, client, classification_rule):
        response = client.post("/api/v1/classification/rules/apply")
        assert response.status_code == 200
        assert "classified" in response.json()

# tests/cli/test_classification_commands.py
class TestClassificationCLI:
    def test_classify_object(self, cli_runner, sample_object):
        result = cli_runner.invoke(
            app,
            ["classify", sample_object.fqn, "--level", "confidential"],
        )
        assert result.exit_code == 0

    def test_list_classifications(self, cli_runner, classified_objects):
        result = cli_runner.invoke(app, ["classify", "list"])
        assert result.exit_code == 0
        assert "confidential" in result.output.lower()
```

---

## 10. Implementation Checklist

### Phase 10.1: Core Models & Migration
- [ ] Create migration 009 with all governance tables
- [ ] Create `ClassificationLevel`, `ComplianceLabel`, `OwnerRole` enums
- [ ] Create `Classification` SQLAlchemy model
- [ ] Create `ClassificationRule` SQLAlchemy model
- [ ] Create `Domain` SQLAlchemy model
- [ ] Create `ObjectOwner` SQLAlchemy model
- [ ] Create `AuditEvent` SQLAlchemy model (if not already from Phase 9)
- [ ] Add relationships to `CatalogObject` model

### Phase 10.2: Repositories
- [ ] Create `ClassificationRepository` with CRUD methods
- [ ] Create `OwnershipRepository` with CRUD methods
- [ ] Create `AuditRepository` with query methods
- [ ] Add tests for all repository methods

### Phase 10.3: Services
- [ ] Create `ClassificationService` with all methods
- [ ] Create `OwnershipService` with all methods
- [ ] Create/update `AuditService` (may exist from Phase 9)
- [ ] Add audit logging to all governance changes
- [ ] Add tests for all service methods

### Phase 10.4: CLI Commands
- [ ] Add `classify` command group
- [ ] Add `owner` and `steward` commands
- [ ] Add `domain` command group
- [ ] Add `audit` commands (if not already from Phase 9)
- [ ] Add tests for all CLI commands

### Phase 10.5: API Endpoints
- [ ] Add `/api/v1/classification` routes
- [ ] Add `/api/v1/ownership` routes
- [ ] Add `/api/v1/domains` routes
- [ ] Add `/api/v1/audit` routes (if not already)
- [ ] Add OpenAPI documentation
- [ ] Add tests for all API endpoints

### Phase 10.6: Web UI
- [ ] Create `ClassificationBadge` component
- [ ] Create `OwnershipPanel` component
- [ ] Create `DomainTree` component
- [ ] Create `AuditLogTable` component
- [ ] Add classification to object detail page
- [ ] Add ownership to object detail page
- [ ] Create classification management page
- [ ] Create domain management page
- [ ] Create audit log page
- [ ] Add TanStack Query hooks
- [ ] Add component tests
