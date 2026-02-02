/**
 * TypeScript types matching backend Pydantic schemas.
 * These types correspond to the API response models in datacompass.core.models.schemas
 */

// =============================================================================
// Data Source Types
// =============================================================================

export interface DataSource {
  id: number
  name: string
  display_name: string | null
  source_type: string
  is_active: boolean
  last_scan_at: string | null
  last_scan_status: string | null
  created_at: string
  updated_at: string
}

export interface DataSourceDetail extends DataSource {
  object_count: number
  table_count: number
  view_count: number
}

// =============================================================================
// Column Types
// =============================================================================

export interface ForeignKeyConstraint {
  constraint_name: string
  references_schema: string
  references_table: string
  references_column: string
}

export interface ColumnSummary {
  column_name: string
  data_type: string | null
  nullable: boolean | null
  description: string | null
  foreign_key: ForeignKeyConstraint | null
}

// =============================================================================
// Catalog Object Types
// =============================================================================

export interface CatalogObjectSummary {
  id: number
  source_name: string
  schema_name: string
  object_name: string
  object_type: string
  description: string | null
  column_count: number
}

export interface CatalogObjectDetail {
  id: number
  source_id: number
  source_name: string
  schema_name: string
  object_name: string
  object_type: string
  source_metadata: Record<string, unknown> | null
  user_metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
  deleted_at: string | null
  columns: ColumnSummary[]
}

// =============================================================================
// Search Types
// =============================================================================

export interface SearchResult {
  id: number
  source_name: string
  schema_name: string
  object_name: string
  object_type: string
  description: string | null
  tags: string[]
  rank: number
  highlights: Record<string, string>
}

// =============================================================================
// Request Types
// =============================================================================

export interface ObjectUpdateRequest {
  description?: string | null
  tags_to_add?: string[]
  tags_to_remove?: string[]
}

// =============================================================================
// Filter Types (for query params)
// =============================================================================

export interface ObjectFilters {
  source?: string
  object_type?: string
  schema?: string
  limit?: number
  offset?: number
}

export interface SearchFilters {
  q: string
  source?: string
  object_type?: string
  limit?: number
}

// =============================================================================
// Lineage Types
// =============================================================================

export interface LineageNode {
  id: number
  source_name: string
  schema_name: string
  object_name: string
  object_type: string
  distance: number
}

export interface ExternalNode {
  schema_name: string | null
  object_name: string
  object_type: string | null
  distance: number
}

export interface LineageEdge {
  from_id: number
  to_id: number | null
  to_external: Record<string, unknown> | null
  dependency_type: string
  confidence: string
}

export interface LineageGraph {
  root: LineageNode
  nodes: LineageNode[]
  external_nodes: ExternalNode[]
  edges: LineageEdge[]
  direction: string
  depth: number
  truncated: boolean
}

export interface LineageSummary {
  upstream_count: number
  downstream_count: number
  external_count: number
}

export interface LineageFilters {
  direction?: 'upstream' | 'downstream'
  depth?: number
}

// =============================================================================
// Data Quality Types
// =============================================================================

export type DQPriority = 'critical' | 'high' | 'medium' | 'low'
export type DQBreachStatus = 'open' | 'acknowledged' | 'dismissed' | 'resolved'
export type DQBreachDirection = 'high' | 'low'
export type DQThresholdType = 'absolute' | 'simple_average' | 'dow_adjusted'

export interface ThresholdConfig {
  type: DQThresholdType
  min?: number | null
  max?: number | null
  multiplier?: number | null
  lookback_days?: number | null
}

export interface DQExpectation {
  id: number
  config_id: number
  expectation_type: string
  column_name: string | null
  threshold_config: ThresholdConfig
  priority: DQPriority
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface DQConfigListItem {
  id: number
  object_id: number
  object_name: string
  schema_name: string
  source_name: string
  date_column: string | null
  grain: string
  is_enabled: boolean
  expectation_count: number
  open_breach_count: number
}

export interface DQConfigDetail {
  id: number
  object_id: number
  object_name: string
  schema_name: string
  source_name: string
  date_column: string | null
  grain: string
  is_enabled: boolean
  expectations: DQExpectation[]
  created_at: string
  updated_at: string
}

export interface DQBreach {
  id: number
  expectation_id: number
  result_id: number
  snapshot_date: string
  metric_value: number
  breach_direction: DQBreachDirection
  threshold_value: number
  deviation_value: number
  deviation_percent: number
  status: DQBreachStatus
  detected_at: string
  created_at: string
  updated_at: string
  // Detail fields
  object_id: number
  object_name: string
  schema_name: string
  source_name: string
  expectation_type: string
  column_name: string | null
  priority: DQPriority
  threshold_snapshot: ThresholdConfig
  lifecycle_events: Array<{
    status: string
    by: string
    at: string
    notes?: string
  }>
}

export interface DQHubSummary {
  total_configs: number
  enabled_configs: number
  total_expectations: number
  enabled_expectations: number
  open_breaches: number
  breaches_by_priority: Record<string, number>
  breaches_by_status: Record<string, number>
  recent_breaches: DQBreach[]
}

export interface DQRunResultItem {
  expectation_id: number
  expectation_type: string
  column_name: string | null
  metric_value: number
  computed_threshold_low: number | null
  computed_threshold_high: number | null
  status: 'pass' | 'breach'
  breach_id: number | null
}

export interface DQRunResult {
  config_id: number
  object_name: string
  schema_name: string
  source_name: string
  snapshot_date: string
  total_checks: number
  passed: number
  breached: number
  results: DQRunResultItem[]
}

export interface DQBreachFilters {
  status?: DQBreachStatus
  priority?: DQPriority
  source_id?: number
  limit?: number
  offset?: number
}

export type DQGrain = 'daily' | 'hourly'
export type DQExpectationType = 'row_count' | 'null_count' | 'distinct_count' | 'min' | 'max' | 'mean' | 'sum'

export interface DQConfigCreate {
  object_id: number
  date_column?: string | null
  grain?: DQGrain
}

export interface DQConfigUpdate {
  date_column?: string | null
  grain?: DQGrain
  is_enabled?: boolean
}

export interface DQExpectationCreate {
  config_id: number
  expectation_type: DQExpectationType
  column_name?: string | null
  threshold_config: ThresholdConfig
  priority?: DQPriority
}

export interface DQExpectationUpdate {
  expectation_type?: DQExpectationType
  column_name?: string | null
  threshold_config?: ThresholdConfig
  priority?: DQPriority
  is_enabled?: boolean
}

export interface DQConfigFilters {
  source_id?: number
  enabled_only?: boolean
  limit?: number
  offset?: number
}

export interface BreachStatusUpdate {
  status: 'acknowledged' | 'dismissed' | 'resolved'
  notes?: string
}

// =============================================================================
// Deprecation Types
// =============================================================================

export type CampaignStatus = 'draft' | 'active' | 'completed'

export interface DeprecationResponse {
  id: number
  campaign_id: number
  object_id: number
  object_name: string
  schema_name: string
  object_type: string
  replacement_id: number | null
  replacement_name: string | null
  migration_notes: string | null
  created_at: string
  updated_at: string
}

export interface CampaignListItem {
  id: number
  source_id: number
  source_name: string
  name: string
  status: CampaignStatus
  target_date: string
  object_count: number
  days_remaining: number | null
}

export interface CampaignDetailResponse {
  id: number
  source_id: number
  source_name: string
  name: string
  description: string | null
  status: CampaignStatus
  target_date: string
  deprecations: DeprecationResponse[]
  days_remaining: number | null
  created_at: string
  updated_at: string
}

export interface ImpactedObject {
  id: number
  source_name: string
  schema_name: string
  object_name: string
  object_type: string
  distance: number
  full_name: string
}

export interface DeprecationImpact {
  deprecated_object_id: number
  deprecated_object_name: string
  downstream_count: number
  impacted_objects: ImpactedObject[]
}

export interface CampaignImpactSummary {
  campaign_id: number
  campaign_name: string
  total_deprecated: number
  total_impacted: number
  impacts: DeprecationImpact[]
}

export interface DeprecationHubSummary {
  total_campaigns: number
  active_campaigns: number
  draft_campaigns: number
  completed_campaigns: number
  total_deprecated_objects: number
  upcoming_deadlines: CampaignListItem[]
}

export interface CampaignCreate {
  source_id: number
  name: string
  description?: string
  target_date: string
}

export interface CampaignUpdate {
  name?: string
  description?: string
  status?: CampaignStatus
  target_date?: string
}

export interface DeprecationCreate {
  object_id: number
  replacement_id?: number
  migration_notes?: string
}

export interface CampaignFilters {
  source_id?: number
  status?: CampaignStatus
  limit?: number
  offset?: number
}

export interface DeprecationFilters {
  campaign_id?: number
  limit?: number
  offset?: number
}

// =============================================================================
// Scheduling Types
// =============================================================================

export type JobType = 'scan' | 'dq_run' | 'deprecation_check'
export type RunStatus = 'running' | 'success' | 'failed'

export interface Schedule {
  id: number
  name: string
  description: string | null
  job_type: JobType
  target_id: number | null
  target_name: string | null
  cron_expression: string
  timezone: string
  is_enabled: boolean
  next_run_at: string | null
  last_run_at: string | null
  last_run_status: RunStatus | null
  created_at: string
  updated_at: string
}

export interface ScheduleRun {
  id: number
  schedule_id: number
  started_at: string
  completed_at: string | null
  status: RunStatus
  result_summary: Record<string, unknown> | null
  error_message: string | null
  created_at: string
}

export interface SchedulerHubSummary {
  total_schedules: number
  enabled_schedules: number
  total_channels: number
  enabled_channels: number
  total_rules: number
  enabled_rules: number
  recent_runs: ScheduleRun[]
  recent_notifications: NotificationLogEntry[]
  schedules_by_type: Record<string, number>
  notifications_by_status: Record<string, number>
}

export interface ScheduleCreate {
  name: string
  description?: string
  job_type: JobType
  target_id?: number
  cron_expression: string
  timezone?: string
}

export interface ScheduleUpdate {
  name?: string
  description?: string
  cron_expression?: string
  timezone?: string
  is_enabled?: boolean
}

export interface ScheduleFilters {
  job_type?: JobType
  is_enabled?: boolean
  limit?: number
  offset?: number
}

// =============================================================================
// Notification Types
// =============================================================================

export type ChannelType = 'email' | 'slack' | 'webhook'
export type EventType = 'dq_breach' | 'scan_failed' | 'scan_completed' | 'deprecation_deadline'
export type NotificationStatus = 'sent' | 'failed' | 'rate_limited'

export interface NotificationChannel {
  id: number
  name: string
  channel_type: ChannelType
  config: Record<string, unknown>
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface NotificationRule {
  id: number
  name: string
  event_type: EventType
  conditions: Record<string, unknown> | null
  channel_id: number
  channel_name: string
  template_override: string | null
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface NotificationLogEntry {
  id: number
  rule_id: number | null
  channel_id: number | null
  event_type: EventType
  event_payload: Record<string, unknown>
  status: NotificationStatus
  error_message: string | null
  sent_at: string
}

export interface ChannelCreate {
  name: string
  channel_type: ChannelType
  config: Record<string, unknown>
}

export interface ChannelUpdate {
  name?: string
  config?: Record<string, unknown>
  is_enabled?: boolean
}

export interface RuleCreate {
  name: string
  event_type: EventType
  conditions?: Record<string, unknown>
  channel_id: number
  template_override?: string
}

export interface RuleUpdate {
  name?: string
  conditions?: Record<string, unknown>
  channel_id?: number
  template_override?: string
  is_enabled?: boolean
}

export interface ChannelFilters {
  channel_type?: ChannelType
  is_enabled?: boolean
  limit?: number
  offset?: number
}

export interface RuleFilters {
  event_type?: EventType
  channel_id?: number
  is_enabled?: boolean
  limit?: number
  offset?: number
}

export interface NotificationLogFilters {
  event_type?: EventType
  status?: NotificationStatus
  limit?: number
  offset?: number
}
