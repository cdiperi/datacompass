/**
 * Table component for displaying DQ breaches with filtering and actions.
 */

import { useState } from 'react'
import { Button, Modal, Input, Select, Space, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import type { DQBreach, DQBreachStatus, DQPriority } from '../api/types'
import { useDQBreaches, useUpdateBreachStatus } from '../hooks/useDQ'
import { DQDirectionBadge, DQPriorityBadge, DQStatusBadge } from './DQStatusBadge'

const { Text } = Typography

interface BreachTableProps {
  initialStatus?: DQBreachStatus
  initialPriority?: DQPriority
  limit?: number
  showFilters?: boolean
}

export function BreachTable({
  initialStatus,
  initialPriority,
  limit = 50,
  showFilters = true,
}: BreachTableProps) {
  const [statusFilter, setStatusFilter] = useState<DQBreachStatus | undefined>(initialStatus)
  const [priorityFilter, setPriorityFilter] = useState<DQPriority | undefined>(initialPriority)

  const { data: breaches, isLoading, error } = useDQBreaches({
    status: statusFilter,
    priority: priorityFilter,
    limit,
  })

  const updateStatus = useUpdateBreachStatus()

  // Modal state for status update
  const [updateModalVisible, setUpdateModalVisible] = useState(false)
  const [selectedBreach, setSelectedBreach] = useState<DQBreach | null>(null)
  const [newStatus, setNewStatus] = useState<'acknowledged' | 'dismissed' | 'resolved'>('acknowledged')
  const [notes, setNotes] = useState('')

  const handleUpdateClick = (breach: DQBreach) => {
    setSelectedBreach(breach)
    setNewStatus('acknowledged')
    setNotes('')
    setUpdateModalVisible(true)
  }

  const handleUpdateConfirm = async () => {
    if (!selectedBreach) return

    try {
      await updateStatus.mutateAsync({
        breachId: selectedBreach.id,
        data: { status: newStatus, notes: notes || undefined },
      })
      message.success('Breach status updated')
      setUpdateModalVisible(false)
    } catch {
      message.error('Failed to update breach status')
    }
  }

  const columns: ColumnsType<DQBreach> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'Object',
      key: 'object',
      render: (_, record) => (
        <Link to={`/objects/${record.object_id}`}>
          <Text code>{record.schema_name}.{record.object_name}</Text>
        </Link>
      ),
    },
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
      title: 'Date',
      dataIndex: 'snapshot_date',
      key: 'date',
      width: 110,
    },
    {
      title: 'Direction',
      dataIndex: 'breach_direction',
      key: 'direction',
      width: 90,
      render: (direction) => <DQDirectionBadge direction={direction} />,
    },
    {
      title: 'Deviation',
      key: 'deviation',
      width: 100,
      render: (_, record) => (
        <Text type={record.deviation_percent > 50 ? 'danger' : 'warning'}>
          {record.deviation_percent.toFixed(1)}%
        </Text>
      ),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (priority) => <DQPriorityBadge priority={priority} />,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status) => <DQStatusBadge status={status} />,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) =>
        record.status === 'open' || record.status === 'acknowledged' ? (
          <Button size="small" onClick={() => handleUpdateClick(record)}>
            Update
          </Button>
        ) : null,
    },
  ]

  if (error) {
    return <Text type="danger">Error loading breaches: {error.message}</Text>
  }

  return (
    <div>
      {showFilters && (
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="Status"
            allowClear
            style={{ width: 150 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'open', label: 'Open' },
              { value: 'acknowledged', label: 'Acknowledged' },
              { value: 'dismissed', label: 'Dismissed' },
              { value: 'resolved', label: 'Resolved' },
            ]}
          />
          <Select
            placeholder="Priority"
            allowClear
            style={{ width: 150 }}
            value={priorityFilter}
            onChange={setPriorityFilter}
            options={[
              { value: 'critical', label: 'Critical' },
              { value: 'high', label: 'High' },
              { value: 'medium', label: 'Medium' },
              { value: 'low', label: 'Low' },
            ]}
          />
        </Space>
      )}

      <Table
        columns={columns}
        dataSource={breaches}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        size="small"
      />

      <Modal
        title="Update Breach Status"
        open={updateModalVisible}
        onOk={handleUpdateConfirm}
        onCancel={() => setUpdateModalVisible(false)}
        confirmLoading={updateStatus.isPending}
      >
        {selectedBreach && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>
              Updating breach #{selectedBreach.id} for{' '}
              <Text strong>
                {selectedBreach.schema_name}.{selectedBreach.object_name}
              </Text>
            </Text>

            <div>
              <Text type="secondary">New Status:</Text>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                value={newStatus}
                onChange={setNewStatus}
                options={[
                  { value: 'acknowledged', label: 'Acknowledged' },
                  { value: 'dismissed', label: 'Dismissed' },
                  { value: 'resolved', label: 'Resolved' },
                ]}
              />
            </div>

            <div>
              <Text type="secondary">Notes (optional):</Text>
              <Input.TextArea
                style={{ marginTop: 4 }}
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add notes about this status change..."
              />
            </div>
          </Space>
        )}
      </Modal>
    </div>
  )
}
