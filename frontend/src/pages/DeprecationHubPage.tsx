/**
 * Deprecation Hub page - dashboard for campaign management.
 */

import { useState } from 'react'
import {
  Card,
  Col,
  Row,
  Statistic,
  Typography,
  Alert,
  Spin,
  Tabs,
  Modal,
  Descriptions,
  Table,
  Tag,
  Button,
  Space,
  message,
} from 'antd'
import {
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FileSearchOutlined,
} from '@ant-design/icons'
import type { TabsProps } from 'antd'

import { CampaignTable } from '../components/CampaignTable'
import { ImpactAnalysis } from '../components/ImpactAnalysis'
import {
  useCampaigns,
  useCampaign,
  useCampaignImpact,
  useDeprecationHubSummary,
  useUpdateCampaign,
  useDeleteCampaign,
} from '../hooks/useDeprecation'
import type { CampaignListItem } from '../api/types'

const { Title } = Typography

export function DeprecationHubPage() {
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState('all')

  const { data: summary, isLoading: summaryLoading } = useDeprecationHubSummary()
  const { data: campaigns, isLoading: campaignsLoading } = useCampaigns({
    status: activeTab === 'all' ? undefined : (activeTab as 'draft' | 'active' | 'completed'),
  })
  const { data: selectedCampaign, isLoading: campaignLoading } = useCampaign(
    selectedCampaignId ?? 0
  )
  const { data: impact, isLoading: impactLoading } = useCampaignImpact(
    selectedCampaignId ?? 0
  )

  const updateCampaign = useUpdateCampaign()
  const deleteCampaign = useDeleteCampaign()

  const handleView = (campaign: CampaignListItem) => {
    setSelectedCampaignId(campaign.id)
  }

  const handleActivate = (campaign: CampaignListItem) => {
    updateCampaign.mutate(
      { campaignId: campaign.id, data: { status: 'active' } },
      {
        onSuccess: () => {
          message.success(`Campaign "${campaign.name}" activated`)
        },
        onError: (error) => {
          message.error(`Failed to activate: ${error.message}`)
        },
      }
    )
  }

  const handleDelete = (campaign: CampaignListItem) => {
    deleteCampaign.mutate(campaign.id, {
      onSuccess: () => {
        message.success(`Campaign "${campaign.name}" deleted`)
        if (selectedCampaignId === campaign.id) {
          setSelectedCampaignId(null)
        }
      },
      onError: (error) => {
        message.error(`Failed to delete: ${error.message}`)
      },
    })
  }

  const handleCloseModal = () => {
    setSelectedCampaignId(null)
  }

  const tabItems: TabsProps['items'] = [
    { key: 'all', label: 'All Campaigns' },
    { key: 'draft', label: 'Draft' },
    { key: 'active', label: 'Active' },
    { key: 'completed', label: 'Completed' },
  ]

  if (summaryLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div>
      <Title level={2}>Deprecation Hub</Title>

      {/* Summary Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Campaigns"
              value={summary?.total_campaigns ?? 0}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Active Campaigns"
              value={summary?.active_campaigns ?? 0}
              valueStyle={{ color: '#1890ff' }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Draft Campaigns"
              value={summary?.draft_campaigns ?? 0}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Deprecated Objects"
              value={summary?.total_deprecated_objects ?? 0}
              valueStyle={
                (summary?.total_deprecated_objects ?? 0) > 0
                  ? { color: '#faad14' }
                  : undefined
              }
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Upcoming Deadlines Alert */}
      {summary?.upcoming_deadlines && summary.upcoming_deadlines.length > 0 && (
        <Alert
          message="Upcoming Deadlines"
          description={
            <Space direction="vertical" style={{ width: '100%' }}>
              {summary.upcoming_deadlines.slice(0, 3).map((c) => (
                <span key={c.id}>
                  <Tag
                    color={
                      c.days_remaining !== null && c.days_remaining <= 7
                        ? 'error'
                        : 'warning'
                    }
                  >
                    {c.days_remaining} days
                  </Tag>
                  <Button type="link" onClick={() => handleView(c)}>
                    {c.name}
                  </Button>
                  <span style={{ color: '#999' }}>({c.object_count} objects)</span>
                </span>
              ))}
            </Space>
          }
          type="warning"
          showIcon
          style={{ marginBottom: 24 }}
        />
      )}

      {/* Campaign Tabs and Table */}
      <Card>
        <Tabs items={tabItems} activeKey={activeTab} onChange={setActiveTab} />
        <CampaignTable
          campaigns={campaigns ?? []}
          loading={campaignsLoading}
          onView={handleView}
          onActivate={handleActivate}
          onDelete={handleDelete}
        />
      </Card>

      {/* Campaign Detail Modal */}
      <Modal
        title={selectedCampaign?.name ?? 'Campaign Details'}
        open={selectedCampaignId !== null}
        onCancel={handleCloseModal}
        footer={null}
        width={800}
      >
        {campaignLoading ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Spin />
          </div>
        ) : selectedCampaign ? (
          <Tabs
            items={[
              {
                key: 'details',
                label: 'Details',
                children: (
                  <>
                    <Descriptions bordered column={2} size="small">
                      <Descriptions.Item label="Source">
                        {selectedCampaign.source_name}
                      </Descriptions.Item>
                      <Descriptions.Item label="Status">
                        <Tag
                          color={
                            selectedCampaign.status === 'active'
                              ? 'processing'
                              : selectedCampaign.status === 'completed'
                              ? 'success'
                              : 'default'
                          }
                        >
                          {selectedCampaign.status}
                        </Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Target Date">
                        {selectedCampaign.target_date}
                      </Descriptions.Item>
                      <Descriptions.Item label="Days Remaining">
                        {selectedCampaign.days_remaining !== null
                          ? selectedCampaign.days_remaining
                          : '-'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Description" span={2}>
                        {selectedCampaign.description || '-'}
                      </Descriptions.Item>
                    </Descriptions>

                    <Title level={5} style={{ marginTop: 16 }}>
                      Deprecated Objects ({selectedCampaign.deprecations.length})
                    </Title>
                    <Table
                      dataSource={selectedCampaign.deprecations}
                      columns={[
                        {
                          title: 'Object',
                          key: 'object',
                          render: (_, record) =>
                            `${record.schema_name}.${record.object_name}`,
                        },
                        {
                          title: 'Type',
                          dataIndex: 'object_type',
                          key: 'object_type',
                          width: 100,
                        },
                        {
                          title: 'Replacement',
                          dataIndex: 'replacement_name',
                          key: 'replacement_name',
                          render: (val) => val || '-',
                        },
                        {
                          title: 'Notes',
                          dataIndex: 'migration_notes',
                          key: 'migration_notes',
                          ellipsis: true,
                          render: (val) => val || '-',
                        },
                      ]}
                      rowKey="id"
                      size="small"
                      pagination={false}
                    />
                  </>
                ),
              },
              {
                key: 'impact',
                label: (
                  <span>
                    <FileSearchOutlined /> Impact Analysis
                  </span>
                ),
                children: impactLoading ? (
                  <div style={{ textAlign: 'center', padding: 20 }}>
                    <Spin />
                  </div>
                ) : impact ? (
                  <ImpactAnalysis impact={impact} />
                ) : null,
              },
            ]}
          />
        ) : null}
      </Modal>
    </div>
  )
}
