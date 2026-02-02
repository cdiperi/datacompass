import { Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import type { CatalogObjectSummary } from '../api/types'

const { Text } = Typography

interface ObjectTableProps {
  objects: CatalogObjectSummary[]
  loading?: boolean
  pagination?: {
    current: number
    pageSize: number
    total: number
    onChange: (page: number, pageSize: number) => void
  }
}

const objectTypeColors: Record<string, string> = {
  TABLE: 'blue',
  VIEW: 'green',
  MATERIALIZED_VIEW: 'purple',
  FUNCTION: 'orange',
}

export function ObjectTable({ objects, loading, pagination }: ObjectTableProps) {
  const navigate = useNavigate()

  const columns: ColumnsType<CatalogObjectSummary> = [
    {
      title: 'Name',
      dataIndex: 'object_name',
      key: 'object_name',
      render: (name: string) => (
        <Text strong style={{ cursor: 'pointer' }}>
          {name}
        </Text>
      ),
    },
    {
      title: 'Schema',
      dataIndex: 'schema_name',
      key: 'schema_name',
    },
    {
      title: 'Source',
      dataIndex: 'source_name',
      key: 'source_name',
    },
    {
      title: 'Type',
      dataIndex: 'object_type',
      key: 'object_type',
      render: (type: string) => (
        <Tag color={objectTypeColors[type] || 'default'}>{type}</Tag>
      ),
    },
    {
      title: 'Columns',
      dataIndex: 'column_count',
      key: 'column_count',
      align: 'right',
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (desc: string | null) => (
        <Text type={desc ? undefined : 'secondary'}>
          {desc || 'No description'}
        </Text>
      ),
    },
  ]

  return (
    <Table
      dataSource={objects}
      columns={columns}
      rowKey="id"
      loading={loading}
      pagination={pagination ? {
        current: pagination.current,
        pageSize: pagination.pageSize,
        total: pagination.total,
        onChange: pagination.onChange,
        showSizeChanger: true,
        showTotal: (total) => `${total} objects`,
      } : false}
      onRow={(record) => ({
        onClick: () => navigate(`/objects/${record.id}`),
        style: { cursor: 'pointer' },
      })}
    />
  )
}
