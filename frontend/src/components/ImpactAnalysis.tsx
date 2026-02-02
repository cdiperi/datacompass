/**
 * Impact analysis visualization component.
 */

import { Collapse, Table, Tag, Typography, Space, Statistic, Row, Col, Card } from 'antd'
import { WarningOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { CampaignImpactSummary, ImpactedObject } from '../api/types'

const { Text } = Typography

interface ImpactAnalysisProps {
  impact: CampaignImpactSummary
}

export function ImpactAnalysis({ impact }: ImpactAnalysisProps) {
  const impactedColumns: ColumnsType<ImpactedObject> = [
    {
      title: 'Distance',
      dataIndex: 'distance',
      key: 'distance',
      width: 80,
      align: 'center',
      render: (distance: number) => (
        <Tag color={distance === 1 ? 'orange' : distance === 2 ? 'blue' : 'default'}>
          {distance}
        </Tag>
      ),
    },
    {
      title: 'Object',
      dataIndex: 'full_name',
      key: 'full_name',
    },
    {
      title: 'Type',
      dataIndex: 'object_type',
      key: 'object_type',
      width: 100,
    },
  ]

  const items = impact.impacts.map((depImpact) => ({
    key: String(depImpact.deprecated_object_id),
    label: (
      <Space>
        <Text strong>{depImpact.deprecated_object_name}</Text>
        {depImpact.downstream_count > 0 ? (
          <Tag color="warning" icon={<WarningOutlined />}>
            {depImpact.downstream_count} downstream
          </Tag>
        ) : (
          <Tag color="success">No dependencies</Tag>
        )}
      </Space>
    ),
    children:
      depImpact.impacted_objects.length > 0 ? (
        <Table
          dataSource={depImpact.impacted_objects}
          columns={impactedColumns}
          rowKey="id"
          size="small"
          pagination={false}
        />
      ) : (
        <Text type="secondary">No downstream objects depend on this.</Text>
      ),
  }))

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="Deprecated Objects"
              value={impact.total_deprecated}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Impacted Objects"
              value={impact.total_impacted}
              valueStyle={
                impact.total_impacted > 0 ? { color: '#faad14' } : undefined
              }
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Impact Ratio"
              value={
                impact.total_deprecated > 0
                  ? (impact.total_impacted / impact.total_deprecated).toFixed(1)
                  : 0
              }
              suffix="x"
            />
          </Card>
        </Col>
      </Row>

      {items.length > 0 ? (
        <Collapse items={items} defaultActiveKey={[items[0]?.key]} />
      ) : (
        <Text type="secondary">No deprecated objects in this campaign.</Text>
      )}
    </div>
  )
}
