import { useParams, Link } from 'react-router-dom'
import { Typography, Spin, Alert, Breadcrumb, Tabs, Descriptions, Table, Tag, Empty, Space, Input, Button, message, Card, Statistic, Row, Col } from 'antd'
import { HomeOutlined, PartitionOutlined, InfoCircleOutlined, SafetyCertificateOutlined, EditOutlined, CheckOutlined, CloseOutlined, DatabaseOutlined, HddOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { useObject, useUpdateObject } from '../hooks/useObjects'
import { useDQConfigs, useDQBreaches } from '../hooks/useDQ'
import { LineageList } from '../components/LineageList'
import { TagEditor } from '../components/TagEditor'
import { DQStatusBadge } from '../components/DQStatusBadge'
import { paramsToFqn, getSourceUrl, getSchemaUrl } from '../utils/urls'
import type { CatalogObjectDetail, ColumnSummary, DQBreach, DQBreachStatus } from '../api/types'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

/**
 * Format bytes to human-readable size (KB, MB, GB, TB)
 */
function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes === 0) return '0 B'

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const value = bytes / Math.pow(k, i)

  // Show 2 decimal places for MB and above, 0 for KB and B
  const decimals = i >= 2 ? 2 : 0
  return `${value.toFixed(decimals)} ${units[i]}`
}

/**
 * Format large numbers with commas
 */
function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '-'
  return num.toLocaleString()
}

export function ObjectDetailPage() {
  const { source, schema, object } = useParams<{ source: string; schema: string; object: string }>()
  const fqn = paramsToFqn(source!, schema!, object!)
  const { data: objectData, isLoading, error } = useObject(fqn)

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message={
          <>
            <strong>Error loading object</strong>
            <div>{error.message}</div>
          </>
        }
      />
    )
  }

  if (!objectData) {
    return (
      <Alert
        type="warning"
        showIcon
        message="Object not found"
      />
    )
  }

  const tabItems = [
    {
      key: 'overview',
      label: (
        <span>
          <InfoCircleOutlined style={{ marginRight: 8 }} />
          Overview
        </span>
      ),
      children: <OverviewTab object={objectData} />,
    },
    {
      key: 'lineage',
      label: (
        <span>
          <PartitionOutlined style={{ marginRight: 8 }} />
          Lineage
        </span>
      ),
      children: <LineageList objectId={objectData.id} />,
    },
    {
      key: 'data-quality',
      label: (
        <span>
          <SafetyCertificateOutlined style={{ marginRight: 8 }} />
          Data Quality
        </span>
      ),
      children: <DataQualityTab objectId={objectData.id} objectName={objectData.object_name} />,
    },
  ]

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/"><HomeOutlined /></Link> },
          { title: <Link to="/catalog">Catalog</Link> },
          { title: <Link to={getSourceUrl(objectData.source_name)}>{objectData.source_name}</Link> },
          { title: <Link to={getSchemaUrl(objectData.source_name, objectData.schema_name)}>{objectData.schema_name}</Link> },
          { title: objectData.object_name },
        ]}
      />

      <Space align="center" style={{ marginBottom: 16 }}>
        <Title level={2} style={{ margin: 0 }}>
          {objectData.object_name}
        </Title>
        <Tag color={objectData.object_type === 'VIEW' ? 'purple' : 'blue'}>
          {objectData.object_type}
        </Tag>
      </Space>

      <Tabs defaultActiveKey="overview" items={tabItems} />
    </div>
  )
}

// =============================================================================
// Overview Tab - Non-technical focused
// =============================================================================

interface OverviewTabProps {
  object: CatalogObjectDetail
}

function OverviewTab({ object }: OverviewTabProps) {
  const [isEditingDescription, setIsEditingDescription] = useState(false)
  const [descriptionValue, setDescriptionValue] = useState(
    object.user_metadata?.description as string || ''
  )
  const updateObject = useUpdateObject()

  const description = (object.user_metadata?.description as string) || null
  const tags = (object.user_metadata?.tags as string[]) || []

  const handleSaveDescription = async () => {
    try {
      await updateObject.mutateAsync({
        id: object.id,
        data: { description: descriptionValue },
      })
      setIsEditingDescription(false)
      message.success('Description updated')
    } catch {
      message.error('Failed to update description')
    }
  }

  const handleCancelEdit = () => {
    setDescriptionValue(description || '')
    setIsEditingDescription(false)
  }

  const handleAddTag = async (tag: string) => {
    try {
      await updateObject.mutateAsync({
        id: object.id,
        data: { tags_to_add: [tag] },
      })
      message.success(`Tag "${tag}" added`)
    } catch {
      message.error('Failed to add tag')
    }
  }

  const handleRemoveTag = async (tag: string) => {
    try {
      await updateObject.mutateAsync({
        id: object.id,
        data: { tags_to_remove: [tag] },
      })
      message.success(`Tag "${tag}" removed`)
    } catch {
      message.error('Failed to remove tag')
    }
  }

  // Extract statistics from source_metadata
  const rowCount = object.source_metadata?.row_count as number | null | undefined
  const sizeBytes = object.source_metadata?.size_bytes as number | null | undefined
  const hasStats = rowCount !== null && rowCount !== undefined || sizeBytes !== null && sizeBytes !== undefined

  return (
    <div>
      {/* Statistics section - show row count and size if available */}
      {hasStats && (
        <Card size="small" style={{ marginBottom: 24 }}>
          <Row gutter={48}>
            <Col>
              <Statistic
                title="Row Count"
                value={formatNumber(rowCount)}
                prefix={<DatabaseOutlined />}
              />
            </Col>
            <Col>
              <Statistic
                title="Size"
                value={formatBytes(sizeBytes)}
                prefix={<HddOutlined />}
              />
            </Col>
          </Row>
        </Card>
      )}

      {/* Description section - prominent for non-technical users */}
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 8 }}>Description</Title>
        {isEditingDescription ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <TextArea
              value={descriptionValue}
              onChange={(e) => setDescriptionValue(e.target.value)}
              rows={3}
              placeholder="Enter description..."
            />
            <Space>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                onClick={handleSaveDescription}
                loading={updateObject.isPending}
              >
                Save
              </Button>
              <Button
                icon={<CloseOutlined />}
                onClick={handleCancelEdit}
              >
                Cancel
              </Button>
            </Space>
          </Space>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Paragraph style={{ margin: 0, maxWidth: 800 }}>
              {description || <Text type="secondary">No description available</Text>}
            </Paragraph>
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => setIsEditingDescription(true)}
            />
          </div>
        )}
      </div>

      {/* Tags */}
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 8 }}>Tags</Title>
        <TagEditor
          tags={tags}
          onAddTag={handleAddTag}
          onRemoveTag={handleRemoveTag}
          disabled={updateObject.isPending}
        />
      </div>

      {/* Columns */}
      <div>
        <ColumnsTable columns={object.columns} />
      </div>
    </div>
  )
}

// =============================================================================
// Columns Table
// =============================================================================

interface ColumnsTableProps {
  columns: ColumnSummary[]
}

function ColumnsTable({ columns }: ColumnsTableProps) {
  const [searchTerm, setSearchTerm] = useState('')

  const filteredColumns = columns.filter((col) =>
    col.column_name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const columnTableColumns: ColumnsType<ColumnSummary> = [
    {
      title: 'Column Name',
      dataIndex: 'column_name',
      key: 'column_name',
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: 'Data Type',
      dataIndex: 'data_type',
      key: 'data_type',
      render: (type: string | null) => (
        <Text code style={{ fontSize: 12 }}>
          {type || '-'}
        </Text>
      ),
    },
    {
      title: 'Nullable',
      dataIndex: 'nullable',
      key: 'nullable',
      width: 100,
      render: (nullable: boolean | null) => {
        if (nullable === null) return <Text type="secondary">-</Text>
        return nullable ? (
          <Tag color="default">Yes</Tag>
        ) : (
          <Tag color="blue">No</Tag>
        )
      },
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string | null) => (
        <Text type={desc ? undefined : 'secondary'}>
          {desc || 'No description'}
        </Text>
      ),
    },
  ]

  if (columns.length === 0) {
    return <Empty description="No columns found" />
  }

  return (
    <div>
      <Space align="center" style={{ marginBottom: 8 }}>
        <Title level={5} style={{ margin: 0 }}>Columns ({columns.length})</Title>
        <Input
          placeholder="Search..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          allowClear
          size="small"
          style={{ width: 160 }}
        />
      </Space>
      <Table
        dataSource={filteredColumns}
        columns={columnTableColumns}
        rowKey="column_name"
        pagination={filteredColumns.length > 20 ? { pageSize: 20 } : false}
        size="small"
      />
    </div>
  )
}

// =============================================================================
// Data Quality Tab
// =============================================================================

interface DataQualityTabProps {
  objectId: number
  objectName: string
}

function DataQualityTab({ objectId, objectName }: DataQualityTabProps) {
  // Fetch all DQ configs and filter for this object
  const { data: allConfigs, isLoading: configsLoading } = useDQConfigs()
  const config = allConfigs?.find((c) => c.object_id === objectId)

  // Fetch breaches for this object (we filter by object_id)
  const { data: allBreaches, isLoading: breachesLoading } = useDQBreaches({ status: 'open' })
  const breaches = allBreaches?.filter((b) => b.object_id === objectId) || []

  if (configsLoading || breachesLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <Spin />
      </div>
    )
  }

  if (!config) {
    return (
      <Empty
        description={
          <span>
            No data quality configuration for <strong>{objectName}</strong>
          </span>
        }
      >
        <Text type="secondary">
          Configure data quality checks via CLI: <Text code>datacompass dq init {objectName}</Text>
        </Text>
      </Empty>
    )
  }

  const breachColumns: ColumnsType<DQBreach> = [
    {
      title: 'Check',
      key: 'check',
      render: (_, record) => (
        <span>
          {record.expectation_type}
          {record.column_name && <Text type="secondary"> ({record.column_name})</Text>}
        </span>
      ),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (priority: string) => {
        const colors: Record<string, string> = {
          critical: 'red',
          high: 'orange',
          medium: 'gold',
          low: 'default',
        }
        return <Tag color={colors[priority] || 'default'}>{priority}</Tag>
      },
    },
    {
      title: 'Snapshot Date',
      dataIndex: 'snapshot_date',
      key: 'snapshot_date',
      width: 120,
    },
    {
      title: 'Deviation',
      key: 'deviation',
      width: 100,
      render: (_, record) => (
        <Text type={record.deviation_percent > 10 ? 'danger' : 'warning'}>
          {record.deviation_percent.toFixed(1)}%
        </Text>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: DQBreachStatus) => <DQStatusBadge status={status} />,
    },
  ]

  return (
    <div>
      {/* Summary */}
      <Descriptions bordered column={3} size="small" style={{ marginBottom: 24 }}>
        <Descriptions.Item label="Status">
          <Tag color={config.is_enabled ? 'green' : 'default'}>
            {config.is_enabled ? 'Enabled' : 'Disabled'}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Expectations">{config.expectation_count}</Descriptions.Item>
        <Descriptions.Item label="Open Breaches">
          <Text type={breaches.length > 0 ? 'danger' : undefined}>
            {breaches.length}
          </Text>
        </Descriptions.Item>
        {config.date_column && (
          <Descriptions.Item label="Date Column">{config.date_column}</Descriptions.Item>
        )}
        <Descriptions.Item label="Grain">{config.grain}</Descriptions.Item>
      </Descriptions>

      {/* Breaches */}
      <Title level={5}>Open Breaches</Title>
      {breaches.length === 0 ? (
        <Empty description="No open breaches" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Table
          dataSource={breaches}
          columns={breachColumns}
          rowKey="id"
          pagination={false}
          size="small"
        />
      )}
    </div>
  )
}
