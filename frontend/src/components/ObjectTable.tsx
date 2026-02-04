import { Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import type { CatalogObjectSummary } from '../api/types'
import { getObjectUrl } from '../utils/urls'

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
      width: 1,
      onCell: () => ({ style: { whiteSpace: 'nowrap', paddingRight: 32 } }),
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: 'Schema',
      dataIndex: 'schema_name',
      key: 'schema_name',
      width: 1,
      onCell: () => ({ style: { whiteSpace: 'nowrap', paddingRight: 32 } }),
    },
    {
      title: 'Source',
      dataIndex: 'source_name',
      key: 'source_name',
      width: 1,
      onCell: () => ({ style: { whiteSpace: 'nowrap', paddingRight: 32 } }),
    },
    {
      title: 'Type',
      dataIndex: 'object_type',
      key: 'object_type',
      width: 1,
      onCell: () => ({ style: { whiteSpace: 'nowrap', paddingRight: 32 } }),
      render: (type: string) => (
        <Tag color={objectTypeColors[type] || 'default'}>{type}</Tag>
      ),
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
      tableLayout="auto"
      pagination={pagination ? {
        current: pagination.current,
        pageSize: pagination.pageSize,
        total: pagination.total,
        onChange: pagination.onChange,
        showSizeChanger: true,
        showTotal: (total) => `${total} objects`,
      } : false}
      onRow={(record) => ({
        onClick: () => navigate(getObjectUrl(record)),
        style: { cursor: 'pointer' },
      })}
    />
  )
}
