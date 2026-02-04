import { Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import type { CatalogObjectSummary } from '../api/types'
import { getObjectUrl } from '../utils/urls'

const { Text } = Typography

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

  // Show 1 decimal place for KB and above, 0 for B
  const decimals = i >= 1 ? 1 : 0
  return `${value.toFixed(decimals)} ${units[i]}`
}

/**
 * Format large numbers with units (K, M, B) for readability
 * Numbers <= 99,999 are shown with commas
 * Numbers > 99,999 are shown with units
 */
function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '-'
  if (num <= 99999) return num.toLocaleString()

  const units = ['', 'K', 'M', 'B', 'T']
  const k = 1000
  const i = Math.floor(Math.log(num) / Math.log(k))
  const value = num / Math.pow(k, i)

  // Show 1 decimal place if needed, otherwise whole number
  const formatted = value % 1 === 0 ? value.toString() : value.toFixed(1)
  return `${formatted}${units[i]}`
}

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
      title: 'Rows',
      dataIndex: 'row_count',
      key: 'row_count',
      width: 1,
      onCell: () => ({ style: { whiteSpace: 'nowrap', paddingRight: 32, textAlign: 'right' } }),
      render: (count: number | null) => (
        <Text type={count !== null ? undefined : 'secondary'}>
          {formatNumber(count)}
        </Text>
      ),
    },
    {
      title: 'Size',
      dataIndex: 'size_bytes',
      key: 'size_bytes',
      width: 1,
      onCell: () => ({ style: { whiteSpace: 'nowrap', paddingRight: 32, textAlign: 'right' } }),
      render: (bytes: number | null) => (
        <Text type={bytes !== null ? undefined : 'secondary'}>
          {formatBytes(bytes)}
        </Text>
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
