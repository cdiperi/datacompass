/**
 * Scheduler Hub page showing scheduled jobs and notification configuration.
 */

import { Card, Col, Row, Statistic, Typography, Alert, Skeleton, Tabs, Tag } from 'antd'
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  BellOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { useSchedulerHubSummary } from '../hooks/useSchedules'
import { useNotificationRules } from '../hooks/useNotifications'
import { ScheduleTable } from '../components/ScheduleTable'
import { ChannelTable } from '../components/ChannelTable'

const { Title, Text } = Typography

export function SchedulerHubPage() {
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useSchedulerHubSummary()

  if (summaryError) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          message="Error loading scheduler summary"
          description={summaryError.message}
          showIcon
        />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Scheduler Hub</Title>
      <Text type="secondary">
        Manage automated jobs, schedules, and notification configuration.
      </Text>

      {/* Summary Cards */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {summaryLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Schedules"
                value={summary?.enabled_schedules ?? 0}
                suffix={`/ ${summary?.total_schedules ?? 0}`}
                prefix={<ClockCircleOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {summaryLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Notification Channels"
                value={summary?.enabled_channels ?? 0}
                suffix={`/ ${summary?.total_channels ?? 0}`}
                prefix={<BellOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {summaryLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Notification Rules"
                value={summary?.enabled_rules ?? 0}
                suffix={`/ ${summary?.total_rules ?? 0}`}
                prefix={<CheckCircleOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {summaryLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Job Types"
                value={Object.keys(summary?.schedules_by_type ?? {}).length}
                valueStyle={{ color: '#8c8c8c' }}
                prefix={<PlayCircleOutlined />}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* Job Type Breakdown */}
      {summary && Object.keys(summary.schedules_by_type ?? {}).length > 0 && (
        <Card style={{ marginTop: 24 }} title="Schedules by Job Type">
          <Row gutter={16}>
            {['scan', 'dq_run', 'deprecation_check'].map((jobType) => {
              const count = summary.schedules_by_type[jobType] ?? 0
              const colors: Record<string, string> = {
                scan: '#1677ff',
                dq_run: '#722ed1',
                deprecation_check: '#fa8c16',
              }
              const labels: Record<string, string> = {
                scan: 'Scans',
                dq_run: 'DQ Runs',
                deprecation_check: 'Deprecation Checks',
              }
              return (
                <Col key={jobType} span={8}>
                  <Statistic
                    title={labels[jobType]}
                    value={count}
                    valueStyle={{ color: count > 0 ? colors[jobType] : '#8c8c8c' }}
                  />
                </Col>
              )
            })}
          </Row>
        </Card>
      )}

      {/* Recent Runs */}
      {summary && summary.recent_runs.length > 0 && (
        <Card style={{ marginTop: 24 }} title="Recent Runs">
          <Row gutter={[8, 8]}>
            {summary.recent_runs.slice(0, 5).map((run) => (
              <Col key={run.id} span={24}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '8px 12px',
                    backgroundColor: '#fafafa',
                    borderRadius: 6,
                  }}
                >
                  <span>
                    <Text strong>Run #{run.id}</Text>
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      Schedule #{run.schedule_id}
                    </Text>
                  </span>
                  <span>
                    <Tag
                      color={
                        run.status === 'success'
                          ? 'green'
                          : run.status === 'failed'
                          ? 'red'
                          : 'blue'
                      }
                    >
                      {run.status}
                    </Tag>
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      {new Date(run.started_at).toLocaleString()}
                    </Text>
                  </span>
                </div>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* Tabs for Schedules and Notifications */}
      <Card style={{ marginTop: 24 }}>
        <Tabs
          defaultActiveKey="schedules"
          items={[
            {
              key: 'schedules',
              label: (
                <span>
                  <ClockCircleOutlined /> Schedules{' '}
                  {summary?.total_schedules ? (
                    <span style={{ color: '#8c8c8c' }}>({summary.total_schedules})</span>
                  ) : null}
                </span>
              ),
              children: <ScheduleTable showFilters />,
            },
            {
              key: 'channels',
              label: (
                <span>
                  <BellOutlined /> Channels{' '}
                  {summary?.total_channels ? (
                    <span style={{ color: '#8c8c8c' }}>({summary.total_channels})</span>
                  ) : null}
                </span>
              ),
              children: <ChannelTable showFilters={false} />,
            },
            {
              key: 'rules',
              label: (
                <span>
                  Rules{' '}
                  {summary?.total_rules ? (
                    <span style={{ color: '#8c8c8c' }}>({summary.total_rules})</span>
                  ) : null}
                </span>
              ),
              children: <NotificationRulesTable />,
            },
          ]}
        />
      </Card>
    </div>
  )
}

/**
 * Simple notification rules table component.
 */
function NotificationRulesTable() {
  const { data: rules, isLoading, error } = useNotificationRules({})

  if (error) {
    return <Text type="danger">Error loading rules: {error.message}</Text>
  }

  if (isLoading) {
    return <Skeleton active />
  }

  if (!rules || rules.length === 0) {
    return (
      <Alert
        type="info"
        message="No notification rules configured"
        description="Use the CLI to create notification rules: datacompass notify rule create"
      />
    )
  }

  const eventTypeColors: Record<string, string> = {
    dq_breach: 'red',
    scan_failed: 'orange',
    scan_completed: 'green',
    deprecation_deadline: 'purple',
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
          <th style={{ textAlign: 'left', padding: 8 }}>Name</th>
          <th style={{ textAlign: 'left', padding: 8 }}>Event Type</th>
          <th style={{ textAlign: 'left', padding: 8 }}>Channel</th>
          <th style={{ textAlign: 'center', padding: 8 }}>Enabled</th>
        </tr>
      </thead>
      <tbody>
        {rules.map((rule) => (
          <tr key={rule.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
            <td style={{ padding: 8 }}>
              <Text strong>{rule.name}</Text>
            </td>
            <td style={{ padding: 8 }}>
              <Tag color={eventTypeColors[rule.event_type] || 'default'}>
                {rule.event_type.replace(/_/g, ' ')}
              </Tag>
            </td>
            <td style={{ padding: 8 }}>
              <Text>{rule.channel_name}</Text>
            </td>
            <td style={{ textAlign: 'center', padding: 8 }}>
              {rule.is_enabled ? (
                <CheckCircleOutlined style={{ color: '#52c41a' }} />
              ) : (
                <span style={{ color: '#8c8c8c' }}>-</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
