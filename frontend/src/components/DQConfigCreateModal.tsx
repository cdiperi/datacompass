/**
 * Modal for creating a new DQ configuration.
 */

import { useMemo, useCallback } from 'react'
import { Form, Input, Modal, Select, message } from 'antd'
import type { DQGrain } from '../api/types'
import { useCreateDQConfig, useDQConfigs } from '../hooks/useDQ'
import { useObjects } from '../hooks/useObjects'

interface DQConfigCreateModalProps {
  open: boolean
  onClose: () => void
  onSuccess?: (configId: number) => void
}

interface FormValues {
  object_id: number
  date_column?: string
  grain: DQGrain
}

export function DQConfigCreateModal({
  open,
  onClose,
  onSuccess,
}: DQConfigCreateModalProps) {
  const [form] = Form.useForm<FormValues>()
  const selectedObjectId = Form.useWatch('object_id', form)

  const { data: objects, isLoading: objectsLoading } = useObjects({ limit: 500 })
  const { data: existingConfigs } = useDQConfigs()
  const createConfig = useCreateDQConfig()

  // Filter out objects that already have DQ configs
  const availableObjects = useMemo(() => {
    if (!objects || !existingConfigs) return []
    const configuredObjectIds = new Set(existingConfigs.map((c) => c.object_id))
    return objects.filter((obj) => !configuredObjectIds.has(obj.id))
  }, [objects, existingConfigs])

  // Check if an object is selected
  const hasSelectedObject = selectedObjectId !== undefined

  // Reset form when modal opens
  const handleAfterOpenChange = useCallback((visible: boolean) => {
    if (visible) {
      form.resetFields()
    }
  }, [form])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      const result = await createConfig.mutateAsync({
        object_id: values.object_id,
        date_column: values.date_column || null,
        grain: values.grain,
      })
      message.success('DQ configuration created')
      onClose()
      onSuccess?.(result.id)
    } catch {
      if (createConfig.error) {
        message.error('Failed to create configuration')
      }
    }
  }

  return (
    <Modal
      title="Create DQ Configuration"
      open={open}
      onOk={handleSubmit}
      onCancel={onClose}
      confirmLoading={createConfig.isPending}
      okText="Create"
      afterOpenChange={handleAfterOpenChange}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={{ grain: 'daily' }}>
        <Form.Item
          name="object_id"
          label="Object"
          rules={[{ required: true, message: 'Please select an object' }]}
        >
          <Select
            showSearch
            placeholder="Select an object"
            loading={objectsLoading}
            optionFilterProp="label"
            options={availableObjects.map((obj) => ({
              value: obj.id,
              label: `${obj.source_name}.${obj.schema_name}.${obj.object_name}`,
            }))}
          />
        </Form.Item>

        <Form.Item
          name="date_column"
          label="Date Column"
          tooltip="Column used for date partitioning (optional)"
        >
          <Input
            placeholder="e.g., created_at"
            disabled={!hasSelectedObject}
          />
        </Form.Item>

        <Form.Item
          name="grain"
          label="Grain"
          rules={[{ required: true }]}
        >
          <Select
            options={[
              { value: 'daily', label: 'Daily' },
              { value: 'hourly', label: 'Hourly' },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
