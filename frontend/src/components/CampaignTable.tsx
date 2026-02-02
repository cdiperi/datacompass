/**
 * Campaign list table component.
 */

import { Table, Tag, Button, Popconfirm, Space, Tooltip } from 'antd'
import { DeleteOutlined, EyeOutlined, PlayCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { CampaignListItem, CampaignStatus } from '../api/types'

interface CampaignTableProps {
  campaigns: CampaignListItem[]
  loading?: boolean
  onView?: (campaign: CampaignListItem) => void
  onActivate?: (campaign: CampaignListItem) => void
  onDelete?: (campaign: CampaignListItem) => void
}

const statusColors: Record<CampaignStatus, string> = {
  draft: 'default',
  active: 'processing',
  completed: 'success',
}

export function CampaignTable({
  campaigns,
  loading = false,
  onView,
  onActivate,
  onDelete,
}: CampaignTableProps) {
  const columns: ColumnsType<CampaignListItem> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => (
        <Button type="link" onClick={() => onView?.(record)} style={{ padding: 0 }}>
          {name}
        </Button>
      ),
    },
    {
      title: 'Source',
      dataIndex: 'source_name',
      key: 'source_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: CampaignStatus) => (
        <Tag color={statusColors[status]}>{status}</Tag>
      ),
    },
    {
      title: 'Target Date',
      dataIndex: 'target_date',
      key: 'target_date',
      width: 120,
    },
    {
      title: 'Objects',
      dataIndex: 'object_count',
      key: 'object_count',
      width: 80,
      align: 'right',
    },
    {
      title: 'Days Left',
      dataIndex: 'days_remaining',
      key: 'days_remaining',
      width: 90,
      align: 'right',
      render: (days: number | null, record) => {
        if (record.status === 'completed' || days === null) {
          return <span style={{ color: '#999' }}>-</span>
        }
        if (days < 0) {
          return <Tag color="error">Overdue</Tag>
        }
        if (days <= 7) {
          return <Tag color="warning">{days}</Tag>
        }
        return days
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="View Details">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => onView?.(record)}
            />
          </Tooltip>
          {record.status === 'draft' && (
            <Tooltip title="Activate">
              <Button
                type="text"
                size="small"
                icon={<PlayCircleOutlined />}
                onClick={() => onActivate?.(record)}
              />
            </Tooltip>
          )}
          <Popconfirm
            title="Delete campaign?"
            description="This will remove all deprecations in this campaign."
            onConfirm={() => onDelete?.(record)}
            okText="Delete"
            cancelText="Cancel"
          >
            <Tooltip title="Delete">
              <Button type="text" size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Table
      dataSource={campaigns}
      columns={columns}
      loading={loading}
      rowKey="id"
      size="middle"
      pagination={{ pageSize: 10 }}
    />
  )
}
