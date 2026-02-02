/**
 * API client with fetch wrapper for backend communication.
 * All functions handle JSON serialization and error responses.
 */

import type {
  BreachStatusUpdate,
  CampaignCreate,
  CampaignDetailResponse,
  CampaignFilters,
  CampaignImpactSummary,
  CampaignListItem,
  CampaignUpdate,
  CatalogObjectDetail,
  CatalogObjectSummary,
  ChannelCreate,
  ChannelFilters,
  ChannelUpdate,
  DataSource,
  DeprecationCreate,
  DeprecationFilters,
  DeprecationHubSummary,
  DeprecationResponse,
  DQBreach,
  DQBreachFilters,
  DQConfigDetail,
  DQConfigFilters,
  DQConfigListItem,
  DQHubSummary,
  DQRunResult,
  LineageFilters,
  LineageGraph,
  LineageSummary,
  NotificationChannel,
  NotificationLogEntry,
  NotificationLogFilters,
  NotificationRule,
  ObjectFilters,
  ObjectUpdateRequest,
  RuleCreate,
  RuleFilters,
  RuleUpdate,
  Schedule,
  ScheduleCreate,
  ScheduleFilters,
  ScheduleRun,
  ScheduleUpdate,
  SchedulerHubSummary,
  SearchFilters,
  SearchResult,
} from './types'

const API_BASE = '/api/v1'

class ApiError extends Error {
  status: number
  statusText: string
  body?: unknown

  constructor(status: number, statusText: string, body?: unknown) {
    super(`API Error: ${status} ${statusText}`)
    this.name = 'ApiError'
    this.status = status
    this.statusText = statusText
    this.body = body
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    let body: unknown
    try {
      body = await response.json()
    } catch {
      // Response may not be JSON
    }
    throw new ApiError(response.status, response.statusText, body)
  }

  return response.json()
}

function buildQueryString(params: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value))
    }
  }
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

// =============================================================================
// Sources API
// =============================================================================

export async function getSources(activeOnly = false): Promise<DataSource[]> {
  const query = activeOnly ? '?active_only=true' : ''
  return fetchJson<DataSource[]>(`${API_BASE}/sources${query}`)
}

export async function getSource(name: string): Promise<DataSource> {
  return fetchJson<DataSource>(`${API_BASE}/sources/${encodeURIComponent(name)}`)
}

// =============================================================================
// Objects API
// =============================================================================

export async function getObjects(filters: ObjectFilters = {}): Promise<CatalogObjectSummary[]> {
  const query = buildQueryString({
    source: filters.source,
    object_type: filters.object_type,
    schema: filters.schema,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<CatalogObjectSummary[]>(`${API_BASE}/objects${query}`)
}

export async function getObject(id: string | number): Promise<CatalogObjectDetail> {
  return fetchJson<CatalogObjectDetail>(`${API_BASE}/objects/${encodeURIComponent(String(id))}`)
}

export async function updateObject(
  id: string | number,
  data: ObjectUpdateRequest
): Promise<CatalogObjectDetail> {
  return fetchJson<CatalogObjectDetail>(
    `${API_BASE}/objects/${encodeURIComponent(String(id))}`,
    {
      method: 'PATCH',
      body: JSON.stringify(data),
    }
  )
}

// =============================================================================
// Search API
// =============================================================================

export async function search(filters: SearchFilters): Promise<SearchResult[]> {
  const query = buildQueryString({
    q: filters.q,
    source: filters.source,
    object_type: filters.object_type,
    limit: filters.limit,
  })
  return fetchJson<SearchResult[]>(`${API_BASE}/search${query}`)
}

// =============================================================================
// Lineage API
// =============================================================================

export async function getLineage(
  id: string | number,
  filters: LineageFilters = {}
): Promise<LineageGraph> {
  const query = buildQueryString({
    direction: filters.direction,
    depth: filters.depth,
  })
  return fetchJson<LineageGraph>(
    `${API_BASE}/objects/${encodeURIComponent(String(id))}/lineage${query}`
  )
}

export async function getLineageSummary(id: string | number): Promise<LineageSummary> {
  return fetchJson<LineageSummary>(
    `${API_BASE}/objects/${encodeURIComponent(String(id))}/lineage/summary`
  )
}

// =============================================================================
// Data Quality API
// =============================================================================

export async function getDQConfigs(filters: DQConfigFilters = {}): Promise<DQConfigListItem[]> {
  const query = buildQueryString({
    source_id: filters.source_id,
    enabled_only: filters.enabled_only ? 'true' : undefined,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<DQConfigListItem[]>(`${API_BASE}/dq/configs${query}`)
}

export async function getDQConfig(configId: number): Promise<DQConfigDetail> {
  return fetchJson<DQConfigDetail>(`${API_BASE}/dq/configs/${configId}`)
}

export async function deleteDQConfig(configId: number): Promise<void> {
  await fetch(`${API_BASE}/dq/configs/${configId}`, { method: 'DELETE' })
}

export async function runDQConfig(
  configId: number,
  snapshotDate?: string
): Promise<DQRunResult> {
  const query = snapshotDate ? `?snapshot_date=${snapshotDate}` : ''
  return fetchJson<DQRunResult>(`${API_BASE}/dq/configs/${configId}/run${query}`, {
    method: 'POST',
  })
}

export async function getDQBreaches(filters: DQBreachFilters = {}): Promise<DQBreach[]> {
  const query = buildQueryString({
    status: filters.status,
    priority: filters.priority,
    source_id: filters.source_id,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<DQBreach[]>(`${API_BASE}/dq/breaches${query}`)
}

export async function getDQBreach(breachId: number): Promise<DQBreach> {
  return fetchJson<DQBreach>(`${API_BASE}/dq/breaches/${breachId}`)
}

export async function updateDQBreachStatus(
  breachId: number,
  data: BreachStatusUpdate
): Promise<DQBreach> {
  return fetchJson<DQBreach>(`${API_BASE}/dq/breaches/${breachId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function getDQHubSummary(): Promise<DQHubSummary> {
  return fetchJson<DQHubSummary>(`${API_BASE}/dq/hub/summary`)
}

// =============================================================================
// Deprecation API
// =============================================================================

export async function getCampaigns(filters: CampaignFilters = {}): Promise<CampaignListItem[]> {
  const query = buildQueryString({
    source_id: filters.source_id,
    status: filters.status,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<CampaignListItem[]>(`${API_BASE}/deprecations/campaigns${query}`)
}

export async function getCampaign(campaignId: number): Promise<CampaignDetailResponse> {
  return fetchJson<CampaignDetailResponse>(`${API_BASE}/deprecations/campaigns/${campaignId}`)
}

export async function createCampaign(data: CampaignCreate): Promise<CampaignDetailResponse> {
  return fetchJson<CampaignDetailResponse>(`${API_BASE}/deprecations/campaigns`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateCampaign(
  campaignId: number,
  data: CampaignUpdate
): Promise<CampaignDetailResponse> {
  return fetchJson<CampaignDetailResponse>(
    `${API_BASE}/deprecations/campaigns/${campaignId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(data),
    }
  )
}

export async function deleteCampaign(campaignId: number): Promise<void> {
  await fetch(`${API_BASE}/deprecations/campaigns/${campaignId}`, { method: 'DELETE' })
}

export async function addObjectToCampaign(
  campaignId: number,
  data: DeprecationCreate
): Promise<DeprecationResponse> {
  return fetchJson<DeprecationResponse>(
    `${API_BASE}/deprecations/campaigns/${campaignId}/objects`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  )
}

export async function removeObjectFromCampaign(deprecationId: number): Promise<void> {
  await fetch(`${API_BASE}/deprecations/objects/${deprecationId}`, { method: 'DELETE' })
}

export async function getDeprecations(
  filters: DeprecationFilters = {}
): Promise<DeprecationResponse[]> {
  const query = buildQueryString({
    campaign_id: filters.campaign_id,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<DeprecationResponse[]>(`${API_BASE}/deprecations/objects${query}`)
}

export async function getCampaignImpact(
  campaignId: number,
  depth = 3
): Promise<CampaignImpactSummary> {
  const query = buildQueryString({ depth })
  return fetchJson<CampaignImpactSummary>(
    `${API_BASE}/deprecations/campaigns/${campaignId}/impact${query}`
  )
}

export async function getDeprecationHubSummary(): Promise<DeprecationHubSummary> {
  return fetchJson<DeprecationHubSummary>(`${API_BASE}/deprecations/hub/summary`)
}

// =============================================================================
// Schedules API
// =============================================================================

export async function getSchedules(filters: ScheduleFilters = {}): Promise<Schedule[]> {
  const query = buildQueryString({
    job_type: filters.job_type,
    is_enabled: filters.is_enabled !== undefined ? String(filters.is_enabled) : undefined,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<Schedule[]>(`${API_BASE}/schedules${query}`)
}

export async function getSchedule(scheduleId: number): Promise<Schedule> {
  return fetchJson<Schedule>(`${API_BASE}/schedules/${scheduleId}`)
}

export async function createSchedule(data: ScheduleCreate): Promise<Schedule> {
  return fetchJson<Schedule>(`${API_BASE}/schedules`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateSchedule(
  scheduleId: number,
  data: ScheduleUpdate
): Promise<Schedule> {
  return fetchJson<Schedule>(`${API_BASE}/schedules/${scheduleId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteSchedule(scheduleId: number): Promise<void> {
  await fetch(`${API_BASE}/schedules/${scheduleId}`, { method: 'DELETE' })
}

export async function runScheduleNow(scheduleId: number): Promise<ScheduleRun> {
  return fetchJson<ScheduleRun>(`${API_BASE}/schedules/${scheduleId}/run`, {
    method: 'POST',
  })
}

export async function getScheduleRuns(
  scheduleId: number,
  limit = 20
): Promise<ScheduleRun[]> {
  const query = buildQueryString({ limit })
  return fetchJson<ScheduleRun[]>(`${API_BASE}/schedules/${scheduleId}/runs${query}`)
}

export async function getSchedulerHubSummary(): Promise<SchedulerHubSummary> {
  return fetchJson<SchedulerHubSummary>(`${API_BASE}/schedules/hub/summary`)
}

// =============================================================================
// Notification Channels API
// =============================================================================

export async function getNotificationChannels(
  filters: ChannelFilters = {}
): Promise<NotificationChannel[]> {
  const query = buildQueryString({
    channel_type: filters.channel_type,
    is_enabled: filters.is_enabled !== undefined ? String(filters.is_enabled) : undefined,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<NotificationChannel[]>(`${API_BASE}/notifications/channels${query}`)
}

export async function getNotificationChannel(channelId: number): Promise<NotificationChannel> {
  return fetchJson<NotificationChannel>(`${API_BASE}/notifications/channels/${channelId}`)
}

export async function createNotificationChannel(
  data: ChannelCreate
): Promise<NotificationChannel> {
  return fetchJson<NotificationChannel>(`${API_BASE}/notifications/channels`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateNotificationChannel(
  channelId: number,
  data: ChannelUpdate
): Promise<NotificationChannel> {
  return fetchJson<NotificationChannel>(`${API_BASE}/notifications/channels/${channelId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteNotificationChannel(channelId: number): Promise<void> {
  await fetch(`${API_BASE}/notifications/channels/${channelId}`, { method: 'DELETE' })
}

export async function testNotificationChannel(
  channelId: number
): Promise<{ success: boolean; message: string }> {
  return fetchJson<{ success: boolean; message: string }>(
    `${API_BASE}/notifications/channels/${channelId}/test`,
    { method: 'POST' }
  )
}

// =============================================================================
// Notification Rules API
// =============================================================================

export async function getNotificationRules(filters: RuleFilters = {}): Promise<NotificationRule[]> {
  const query = buildQueryString({
    event_type: filters.event_type,
    channel_id: filters.channel_id,
    is_enabled: filters.is_enabled !== undefined ? String(filters.is_enabled) : undefined,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<NotificationRule[]>(`${API_BASE}/notifications/rules${query}`)
}

export async function getNotificationRule(ruleId: number): Promise<NotificationRule> {
  return fetchJson<NotificationRule>(`${API_BASE}/notifications/rules/${ruleId}`)
}

export async function createNotificationRule(data: RuleCreate): Promise<NotificationRule> {
  return fetchJson<NotificationRule>(`${API_BASE}/notifications/rules`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateNotificationRule(
  ruleId: number,
  data: RuleUpdate
): Promise<NotificationRule> {
  return fetchJson<NotificationRule>(`${API_BASE}/notifications/rules/${ruleId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteNotificationRule(ruleId: number): Promise<void> {
  await fetch(`${API_BASE}/notifications/rules/${ruleId}`, { method: 'DELETE' })
}

// =============================================================================
// Notification Log API
// =============================================================================

export async function getNotificationLog(
  filters: NotificationLogFilters = {}
): Promise<NotificationLogEntry[]> {
  const query = buildQueryString({
    event_type: filters.event_type,
    status: filters.status,
    limit: filters.limit,
    offset: filters.offset,
  })
  return fetchJson<NotificationLogEntry[]>(`${API_BASE}/notifications/log${query}`)
}

export { ApiError }
