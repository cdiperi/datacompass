/**
 * Data Quality Hub page showing summary and breaches.
 */

import { Card, Col, Row, Statistic, Typography, Alert, Skeleton, Tabs } from 'antd'
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  SettingOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { useDQHubSummary } from '../hooks/useDQ'
import { BreachTable } from '../components/BreachTable'

const { Title, Text } = Typography

export function DQHubPage() {
  const { data: summary, isLoading, error } = useDQHubSummary()

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          message="Error loading DQ summary"
          description={error.message}
          showIcon
        />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Data Quality Hub</Title>
      <Text type="secondary">
        Monitor data quality checks, view breaches, and track resolution.
      </Text>

      {/* Summary Cards */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {isLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Configurations"
                value={summary?.enabled_configs ?? 0}
                suffix={`/ ${summary?.total_configs ?? 0}`}
                prefix={<SettingOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {isLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Expectations"
                value={summary?.enabled_expectations ?? 0}
                suffix={`/ ${summary?.total_expectations ?? 0}`}
                prefix={<CheckCircleOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {isLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Open Breaches"
                value={summary?.open_breaches ?? 0}
                valueStyle={{
                  color: (summary?.open_breaches ?? 0) > 0 ? '#cf1322' : '#3f8600',
                }}
                prefix={
                  (summary?.open_breaches ?? 0) > 0 ? (
                    <ExclamationCircleOutlined />
                  ) : (
                    <CheckCircleOutlined />
                  )
                }
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            {isLoading ? (
              <Skeleton.Button active block />
            ) : (
              <Statistic
                title="Critical Breaches"
                value={summary?.breaches_by_priority?.critical ?? 0}
                valueStyle={{
                  color:
                    (summary?.breaches_by_priority?.critical ?? 0) > 0
                      ? '#cf1322'
                      : '#3f8600',
                }}
                prefix={<WarningOutlined />}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* Priority Breakdown */}
      {summary && Object.keys(summary.breaches_by_priority).length > 0 && (
        <Card style={{ marginTop: 24 }} title="Open Breaches by Priority">
          <Row gutter={16}>
            {['critical', 'high', 'medium', 'low'].map((priority) => {
              const count = summary.breaches_by_priority[priority] ?? 0
              const colors: Record<string, string> = {
                critical: '#cf1322',
                high: '#fa8c16',
                medium: '#1677ff',
                low: '#8c8c8c',
              }
              return (
                <Col key={priority} span={6}>
                  <Statistic
                    title={priority.charAt(0).toUpperCase() + priority.slice(1)}
                    value={count}
                    valueStyle={{ color: count > 0 ? colors[priority] : '#8c8c8c' }}
                  />
                </Col>
              )
            })}
          </Row>
        </Card>
      )}

      {/* Breaches Table */}
      <Card style={{ marginTop: 24 }}>
        <Tabs
          defaultActiveKey="open"
          items={[
            {
              key: 'open',
              label: (
                <span>
                  Open{' '}
                  {summary?.open_breaches ? (
                    <span style={{ color: '#cf1322' }}>({summary.open_breaches})</span>
                  ) : null}
                </span>
              ),
              children: <BreachTable initialStatus="open" showFilters={false} />,
            },
            {
              key: 'acknowledged',
              label: 'Acknowledged',
              children: <BreachTable initialStatus="acknowledged" showFilters={false} />,
            },
            {
              key: 'all',
              label: 'All Breaches',
              children: <BreachTable showFilters />,
            },
          ]}
        />
      </Card>
    </div>
  )
}
