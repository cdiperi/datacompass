import { useParams, Link } from 'react-router-dom'
import { Typography, Spin, Alert, Breadcrumb, Tabs, Descriptions, Table, Tag, Empty, Space, Input, Button, message } from 'antd'
import { HomeOutlined, PartitionOutlined, TableOutlined, InfoCircleOutlined, SafetyCertificateOutlined, EditOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
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
          <InfoCircleOutlined />
          Overview
        </span>
      ),
      children: <OverviewTab object={objectData} />,
    },
    {
      key: 'columns',
      label: (
        <span>
          <TableOutlined />
          Columns ({objectData.columns.length})
        </span>
      ),
      children: <ColumnsTab columns={objectData.columns} />,
    },
    {
      key: 'lineage',
      label: (
        <span>
          <PartitionOutlined />
          Lineage
        </span>
      ),
      children: <LineageList objectId={objectData.id} />,
    },
    {
      key: 'data-quality',
      label: (
        <span>
          <SafetyCertificateOutlined />
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

      <Title level={2}>
        {objectData.object_name}
      </Title>

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

  return (
    <div>
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

      {/* Metadata in a clean layout */}
      <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
        <Descriptions.Item label="Type">
          <Tag color={object.object_type === 'VIEW' ? 'purple' : 'blue'}>
            {object.object_type}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Source">{object.source_name}</Descriptions.Item>
        <Descriptions.Item label="Schema">{object.schema_name}</Descriptions.Item>
        <Descriptions.Item label="Columns">{object.columns.length}</Descriptions.Item>
        <Descriptions.Item label="Created">
          {new Date(object.created_at).toLocaleDateString()}
        </Descriptions.Item>
        <Descriptions.Item label="Last Updated">
          {new Date(object.updated_at).toLocaleDateString()}
        </Descriptions.Item>
      </Descriptions>
    </div>
  )
}

// =============================================================================
// Columns Tab
// =============================================================================

interface ColumnsTabProps {
  columns: ColumnSummary[]
}

function ColumnsTab({ columns }: ColumnsTabProps) {
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
    <Table
      dataSource={columns}
      columns={columnTableColumns}
      rowKey="column_name"
      pagination={columns.length > 20 ? { pageSize: 20 } : false}
      size="small"
    />
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
