/**
 * Modal for viewing and editing DQ configuration details.
 */

import { useState, useCallback } from 'react'
import {
  Button,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import type { DQExpectation, DQGrain } from '../api/types'
import {
  useDQConfig,
  useDeleteDQExpectation,
  useUpdateDQConfig,
  useUpdateDQExpectation,
} from '../hooks/useDQ'
import { DQPriorityBadge } from './DQStatusBadge'
import { ExpectationModal } from './ExpectationModal'

const { Text } = Typography

interface DQConfigDetailModalProps {
  open: boolean
  onClose: () => void
  configId: number | null
}

interface SettingsFormValues {
  date_column?: string
  grain: DQGrain
  is_enabled: boolean
}

export function DQConfigDetailModal({
  open,
  onClose,
  configId,
}: DQConfigDetailModalProps) {
  const [form] = Form.useForm<SettingsFormValues>()
  const [settingsChanged, setSettingsChanged] = useState(false)
  const [expectationModalOpen, setExpectationModalOpen] = useState(false)
  const [editingExpectation, setEditingExpectation] = useState<DQExpectation | null>(null)
  const [deleteModalVisible, setDeleteModalVisible] = useState(false)
  const [expectationToDelete, setExpectationToDelete] = useState<DQExpectation | null>(null)

  const { data: config, isLoading } = useDQConfig(configId ?? 0)
  const updateConfig = useUpdateDQConfig()
  const updateExpectation = useUpdateDQExpectation()
  const deleteExpectation = useDeleteDQExpectation()

  // Initialize form when modal opens or config changes
  const handleAfterOpenChange = useCallback((visible: boolean) => {
    if (visible && config) {
      form.setFieldsValue({
        date_column: config.date_column ?? undefined,
        grain: config.grain as DQGrain,
        is_enabled: config.is_enabled,
      })
      setSettingsChanged(false)
    }
  }, [form, config])

  const handleSaveSettings = async () => {
    if (!configId) return

    try {
      const values = await form.validateFields()
      await updateConfig.mutateAsync({
        configId,
        data: {
          date_column: values.date_column || null,
          grain: values.grain,
          is_enabled: values.is_enabled,
        },
      })
      message.success('Settings saved')
      setSettingsChanged(false)
    } catch {
      message.error('Failed to save settings')
    }
  }

  const handleToggleExpectationEnabled = async (expectation: DQExpectation, checked: boolean) => {
    try {
      await updateExpectation.mutateAsync({
        expectationId: expectation.id,
        data: { is_enabled: checked },
      })
      message.success(`Expectation ${checked ? 'enabled' : 'disabled'}`)
    } catch {
      message.error('Failed to update expectation')
    }
  }

  const handleAddExpectation = () => {
    setEditingExpectation(null)
    setExpectationModalOpen(true)
  }

  const handleEditExpectation = (expectation: DQExpectation) => {
    setEditingExpectation(expectation)
    setExpectationModalOpen(true)
  }

  const handleDeleteClick = (expectation: DQExpectation) => {
    setExpectationToDelete(expectation)
    setDeleteModalVisible(true)
  }

  const handleDeleteConfirm = async () => {
    if (!expectationToDelete || !configId) return

    try {
      await deleteExpectation.mutateAsync({
        expectationId: expectationToDelete.id,
        configId,
      })
      message.success('Expectation deleted')
      setDeleteModalVisible(false)
    } catch {
      message.error('Failed to delete expectation')
    }
  }

  const formatThresholdConfig = (tc: DQExpectation['threshold_config']) => {
    if (tc.type === 'absolute') {
      const parts = []
      if (tc.min !== null && tc.min !== undefined) parts.push(`min: ${tc.min}`)
      if (tc.max !== null && tc.max !== undefined) parts.push(`max: ${tc.max}`)
      return parts.length > 0 ? parts.join(', ') : 'No bounds set'
    }
    const strategy = tc.type === 'simple_average' ? 'Simple Avg' : 'DoW Adjusted'
    const mult = tc.multiplier ?? 2.0
    const days = tc.lookback_days ?? (tc.type === 'dow_adjusted' ? 90 : 30)
    return `${strategy} (${mult}x std, ${days}d)`
  }

  const expectationColumns: ColumnsType<DQExpectation> = [
    {
      title: 'Type',
      dataIndex: 'expectation_type',
      key: 'type',
      width: 120,
    },
    {
      title: 'Column',
      dataIndex: 'column_name',
      key: 'column',
      width: 120,
      render: (col) => col || <Text type="secondary">-</Text>,
    },
    {
      title: 'Threshold',
      key: 'threshold',
      render: (_, record) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {formatThresholdConfig(record.threshold_config)}
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
      title: 'Enabled',
      dataIndex: 'is_enabled',
      key: 'enabled',
      width: 80,
      align: 'center',
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          size="small"
          loading={updateExpectation.isPending}
          onChange={(checked) => handleToggleExpectationEnabled(record, checked)}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditExpectation(record)}
          />
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteClick(record)}
          />
        </Space>
      ),
    },
  ]

  const renderSettings = () => (
    <Form
      form={form}
      layout="vertical"
      onValuesChange={() => setSettingsChanged(true)}
    >
      {config && (
        <Descriptions size="small" style={{ marginBottom: 16 }}>
          <Descriptions.Item label="Object">
            <Text code>
              {config.source_name}.{config.schema_name}.{config.object_name}
            </Text>
          </Descriptions.Item>
        </Descriptions>
      )}

      <Form.Item name="date_column" label="Date Column">
        <Input placeholder="e.g., created_at (optional)" />
      </Form.Item>

      <Form.Item name="grain" label="Grain" rules={[{ required: true }]}>
        <Select
          options={[
            { value: 'daily', label: 'Daily' },
            { value: 'hourly', label: 'Hourly' },
          ]}
        />
      </Form.Item>

      <Form.Item name="is_enabled" label="Enabled" valuePropName="checked">
        <Switch />
      </Form.Item>

      <Button
        type="primary"
        onClick={handleSaveSettings}
        disabled={!settingsChanged}
        loading={updateConfig.isPending}
      >
        Save Settings
      </Button>
    </Form>
  )

  const renderExpectations = () => (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleAddExpectation}
        >
          Add Expectation
        </Button>
      </div>

      <Table
        columns={expectationColumns}
        dataSource={config?.expectations ?? []}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        size="small"
      />
    </div>
  )

  return (
    <>
      <Modal
        title="DQ Configuration"
        open={open}
        onCancel={onClose}
        footer={null}
        width={700}
        afterOpenChange={handleAfterOpenChange}
        destroyOnClose
      >
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: 24 }}>Loading...</div>
        ) : config ? (
          <Tabs
            defaultActiveKey="settings"
            items={[
              {
                key: 'settings',
                label: 'Settings',
                children: renderSettings(),
              },
              {
                key: 'expectations',
                label: `Expectations (${config.expectations.length})`,
                children: renderExpectations(),
              },
            ]}
          />
        ) : (
          <Text type="danger">Configuration not found</Text>
        )}
      </Modal>

      {configId && (
        <ExpectationModal
          open={expectationModalOpen}
          onClose={() => {
            setExpectationModalOpen(false)
            setEditingExpectation(null)
          }}
          configId={configId}
          expectation={editingExpectation}
        />
      )}

      <Modal
        title="Delete Expectation"
        open={deleteModalVisible}
        onOk={handleDeleteConfirm}
        onCancel={() => setDeleteModalVisible(false)}
        confirmLoading={deleteExpectation.isPending}
        okButtonProps={{ danger: true }}
        okText="Delete"
      >
        {expectationToDelete && (
          <p>
            Are you sure you want to delete the{' '}
            <Text strong>{expectationToDelete.expectation_type}</Text>
            {expectationToDelete.column_name && (
              <> expectation on column <Text strong>{expectationToDelete.column_name}</Text></>
            )}
            ? This will also delete all associated results and breaches.
          </p>
        )}
      </Modal>
    </>
  )
}
