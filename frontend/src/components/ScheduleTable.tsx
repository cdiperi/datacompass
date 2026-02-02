/**
 * Table component for displaying scheduled jobs with filtering and actions.
 */

import { useState } from 'react'
import {
  Button,
  Modal,
  Input,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  PlayCircleOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import type { JobType, Schedule } from '../api/types'
import {
  useSchedules,
  useUpdateSchedule,
  useDeleteSchedule,
  useRunScheduleNow,
} from '../hooks/useSchedules'

const { Text } = Typography

interface ScheduleTableProps {
  initialJobType?: JobType
  limit?: number
  showFilters?: boolean
}

const jobTypeColors: Record<JobType, string> = {
  scan: 'blue',
  dq_run: 'purple',
  deprecation_check: 'orange',
}

const jobTypeLabels: Record<JobType, string> = {
  scan: 'Scan',
  dq_run: 'DQ Run',
  deprecation_check: 'Deprecation Check',
}

export function ScheduleTable({
  initialJobType,
  limit = 50,
  showFilters = true,
}: ScheduleTableProps) {
  const [jobTypeFilter, setJobTypeFilter] = useState<JobType | undefined>(initialJobType)
  const [enabledFilter, setEnabledFilter] = useState<boolean | undefined>(undefined)

  const { data: schedules, isLoading, error } = useSchedules({
    job_type: jobTypeFilter,
    is_enabled: enabledFilter,
    limit,
  })

  const updateSchedule = useUpdateSchedule()
  const deleteSchedule = useDeleteSchedule()
  const runNow = useRunScheduleNow()

  // Delete modal state
  const [deleteModalVisible, setDeleteModalVisible] = useState(false)
  const [selectedSchedule, setSelectedSchedule] = useState<Schedule | null>(null)

  const handleToggleEnabled = async (schedule: Schedule) => {
    try {
      await updateSchedule.mutateAsync({
        scheduleId: schedule.id,
        data: { is_enabled: !schedule.is_enabled },
      })
      message.success(`Schedule ${schedule.is_enabled ? 'disabled' : 'enabled'}`)
    } catch {
      message.error('Failed to update schedule')
    }
  }

  const handleRunNow = async (scheduleId: number) => {
    try {
      await runNow.mutateAsync(scheduleId)
      message.success('Schedule triggered successfully')
    } catch {
      message.error('Failed to run schedule')
    }
  }

  const handleDeleteClick = (schedule: Schedule) => {
    setSelectedSchedule(schedule)
    setDeleteModalVisible(true)
  }

  const handleDeleteConfirm = async () => {
    if (!selectedSchedule) return

    try {
      await deleteSchedule.mutateAsync(selectedSchedule.id)
      message.success('Schedule deleted')
      setDeleteModalVisible(false)
    } catch {
      message.error('Failed to delete schedule')
    }
  }

  const columns: ColumnsType<Schedule> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <span>
          <Text strong>{name}</Text>
          {record.description && (
            <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
              {record.description}
            </Text>
          )}
        </span>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'job_type',
      key: 'job_type',
      width: 140,
      render: (jobType: JobType) => (
        <Tag color={jobTypeColors[jobType]}>{jobTypeLabels[jobType]}</Tag>
      ),
    },
    {
      title: 'Target',
      key: 'target',
      width: 150,
      render: (_, record) =>
        record.target_name ? (
          <Text code>{record.target_name}</Text>
        ) : (
          <Text type="secondary">All</Text>
        ),
    },
    {
      title: 'Cron',
      dataIndex: 'cron_expression',
      key: 'cron',
      width: 120,
      render: (cron) => <Text code>{cron}</Text>,
    },
    {
      title: 'Next Run',
      dataIndex: 'next_run_at',
      key: 'next_run',
      width: 160,
      render: (nextRun) =>
        nextRun ? new Date(nextRun).toLocaleString() : <Text type="secondary">-</Text>,
    },
    {
      title: 'Last Run',
      key: 'last_run',
      width: 140,
      render: (_, record) => {
        if (!record.last_run_at) return <Text type="secondary">Never</Text>
        const statusIcon =
          record.last_run_status === 'success' ? (
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
          ) : record.last_run_status === 'failed' ? (
            <CloseCircleOutlined style={{ color: '#f5222d' }} />
          ) : record.last_run_status === 'running' ? (
            <SyncOutlined spin style={{ color: '#1677ff' }} />
          ) : null

        return (
          <Space>
            {statusIcon}
            <Text>{new Date(record.last_run_at).toLocaleDateString()}</Text>
          </Space>
        )
      },
    },
    {
      title: 'Enabled',
      dataIndex: 'is_enabled',
      key: 'enabled',
      width: 90,
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggleEnabled(record)}
          loading={updateSchedule.isPending}
          size="small"
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => handleRunNow(record.id)}
            loading={runNow.isPending}
            title="Run Now"
          />
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteClick(record)}
            title="Delete"
          />
        </Space>
      ),
    },
  ]

  if (error) {
    return <Text type="danger">Error loading schedules: {error.message}</Text>
  }

  return (
    <div>
      {showFilters && (
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="Job Type"
            allowClear
            style={{ width: 180 }}
            value={jobTypeFilter}
            onChange={setJobTypeFilter}
            options={[
              { value: 'scan', label: 'Scan' },
              { value: 'dq_run', label: 'DQ Run' },
              { value: 'deprecation_check', label: 'Deprecation Check' },
            ]}
          />
          <Select
            placeholder="Status"
            allowClear
            style={{ width: 120 }}
            value={enabledFilter}
            onChange={setEnabledFilter}
            options={[
              { value: true, label: 'Enabled' },
              { value: false, label: 'Disabled' },
            ]}
          />
        </Space>
      )}

      <Table
        columns={columns}
        dataSource={schedules}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        size="small"
      />

      <Modal
        title="Delete Schedule"
        open={deleteModalVisible}
        onOk={handleDeleteConfirm}
        onCancel={() => setDeleteModalVisible(false)}
        confirmLoading={deleteSchedule.isPending}
        okText="Delete"
        okButtonProps={{ danger: true }}
      >
        {selectedSchedule && (
          <Text>
            Are you sure you want to delete schedule{' '}
            <Text strong>"{selectedSchedule.name}"</Text>? This action cannot be undone.
          </Text>
        )}
      </Modal>
    </div>
  )
}
