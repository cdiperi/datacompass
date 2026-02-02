/**
 * Table component for displaying DQ configurations with actions.
 */

import { useState } from 'react'
import { Button, Modal, Space, Switch, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  DeleteOutlined,
  EditOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import type { DQConfigListItem } from '../api/types'
import {
  useDQConfigs,
  useDeleteDQConfig,
  useRunDQConfig,
  useUpdateDQConfig,
} from '../hooks/useDQ'
import { getObjectUrl } from '../utils/urls'

const { Text } = Typography

interface DQConfigTableProps {
  onViewConfig?: (configId: number) => void
}

export function DQConfigTable({ onViewConfig }: DQConfigTableProps) {
  const { data: configs, isLoading, error } = useDQConfigs()
  const updateConfig = useUpdateDQConfig()
  const deleteConfig = useDeleteDQConfig()
  const runConfig = useRunDQConfig()

  const [deleteModalVisible, setDeleteModalVisible] = useState(false)
  const [configToDelete, setConfigToDelete] = useState<DQConfigListItem | null>(null)

  const handleToggleEnabled = async (config: DQConfigListItem, checked: boolean) => {
    try {
      await updateConfig.mutateAsync({
        configId: config.id,
        data: { is_enabled: checked },
      })
      message.success(`Config ${checked ? 'enabled' : 'disabled'}`)
    } catch {
      message.error('Failed to update config')
    }
  }

  const handleRunConfig = async (configId: number) => {
    try {
      const result = await runConfig.mutateAsync({ configId })
      if (result.breached > 0) {
        message.warning(`DQ check completed: ${result.breached} breach(es) detected`)
      } else {
        message.success(`DQ check completed: all ${result.passed} checks passed`)
      }
    } catch {
      message.error('Failed to run DQ checks')
    }
  }

  const handleDeleteClick = (config: DQConfigListItem) => {
    setConfigToDelete(config)
    setDeleteModalVisible(true)
  }

  const handleDeleteConfirm = async () => {
    if (!configToDelete) return

    try {
      await deleteConfig.mutateAsync(configToDelete.id)
      message.success('Config deleted')
      setDeleteModalVisible(false)
    } catch {
      message.error('Failed to delete config')
    }
  }

  const columns: ColumnsType<DQConfigListItem> = [
    {
      title: 'Object',
      key: 'object',
      render: (_, record) => (
        <Link to={getObjectUrl(record)}>
          <Text code>
            {record.schema_name}.{record.object_name}
          </Text>
        </Link>
      ),
    },
    {
      title: 'Source',
      dataIndex: 'source_name',
      key: 'source',
      width: 120,
    },
    {
      title: 'Grain',
      dataIndex: 'grain',
      key: 'grain',
      width: 80,
    },
    {
      title: 'Expectations',
      dataIndex: 'expectation_count',
      key: 'expectations',
      width: 100,
      align: 'center',
    },
    {
      title: 'Breaches',
      dataIndex: 'open_breach_count',
      key: 'breaches',
      width: 90,
      align: 'center',
      render: (count) => (
        <Text type={count > 0 ? 'danger' : undefined}>{count}</Text>
      ),
    },
    {
      title: 'Enabled',
      dataIndex: 'is_enabled',
      key: 'enabled',
      width: 80,
      align: 'center',
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          size="small"
          loading={updateConfig.isPending}
          onChange={(checked) => handleToggleEnabled(record, checked)}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => onViewConfig?.(record.id)}
            title="View/Edit"
          />
          <Button
            type="text"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => handleRunConfig(record.id)}
            loading={runConfig.isPending}
            disabled={!record.is_enabled || record.expectation_count === 0}
            title="Run Checks"
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
    return <Text type="danger">Error loading configs: {error.message}</Text>
  }

  return (
    <div>
      <Table
        columns={columns}
        dataSource={configs}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        size="small"
      />

      <Modal
        title="Delete DQ Configuration"
        open={deleteModalVisible}
        onOk={handleDeleteConfirm}
        onCancel={() => setDeleteModalVisible(false)}
        confirmLoading={deleteConfig.isPending}
        okButtonProps={{ danger: true }}
        okText="Delete"
      >
        {configToDelete && (
          <p>
            Are you sure you want to delete the DQ configuration for{' '}
            <Text strong>
              {configToDelete.schema_name}.{configToDelete.object_name}
            </Text>
            ? This will also delete all expectations, results, and breaches.
          </p>
        )}
      </Modal>
    </div>
  )
}
