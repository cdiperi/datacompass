/**
 * Modal for creating or editing a DQ expectation.
 */

import { useCallback } from 'react'
import { Form, Input, InputNumber, Modal, Select, message } from 'antd'
import type {
  DQExpectation,
  DQExpectationType,
  DQPriority,
  DQThresholdType,
  ThresholdConfig,
} from '../api/types'
import { useCreateDQExpectation, useUpdateDQExpectation } from '../hooks/useDQ'

interface ExpectationModalProps {
  open: boolean
  onClose: () => void
  configId: number
  expectation?: DQExpectation | null
}

interface FormValues {
  expectation_type: DQExpectationType
  column_name?: string
  priority: DQPriority
  threshold_type: DQThresholdType
  threshold_min?: number
  threshold_max?: number
  threshold_multiplier?: number
  threshold_lookback_days?: number
}

const EXPECTATION_TYPES: { value: DQExpectationType; label: string; requiresColumn: boolean }[] = [
  { value: 'row_count', label: 'Row Count', requiresColumn: false },
  { value: 'null_count', label: 'Null Count', requiresColumn: true },
  { value: 'distinct_count', label: 'Distinct Count', requiresColumn: true },
  { value: 'min', label: 'Min', requiresColumn: true },
  { value: 'max', label: 'Max', requiresColumn: true },
  { value: 'mean', label: 'Mean', requiresColumn: true },
  { value: 'sum', label: 'Sum', requiresColumn: true },
]

const THRESHOLD_TYPES: { value: DQThresholdType; label: string; description: string }[] = [
  { value: 'absolute', label: 'Absolute', description: 'Fixed min/max bounds' },
  { value: 'simple_average', label: 'Simple Average', description: 'Based on historical average' },
  { value: 'dow_adjusted', label: 'Day of Week Adjusted', description: 'Adjusted for day of week patterns' },
]

const PRIORITIES: { value: DQPriority; label: string }[] = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const DEFAULT_FORM_VALUES: FormValues = {
  expectation_type: 'row_count',
  priority: 'medium',
  threshold_type: 'simple_average',
  threshold_multiplier: 2.0,
  threshold_lookback_days: 30,
}

export function ExpectationModal({
  open,
  onClose,
  configId,
  expectation,
}: ExpectationModalProps) {
  const [form] = Form.useForm<FormValues>()
  const thresholdType = Form.useWatch('threshold_type', form)
  const expectationType = Form.useWatch('expectation_type', form)

  const createExpectation = useCreateDQExpectation()
  const updateExpectation = useUpdateDQExpectation()

  const isEdit = !!expectation

  // Check if selected expectation type requires a column
  const requiresColumn = EXPECTATION_TYPES.find(
    (t) => t.value === expectationType
  )?.requiresColumn ?? false

  // Initialize form when modal opens
  const handleAfterOpenChange = useCallback((visible: boolean) => {
    if (visible) {
      if (expectation) {
        const tc = expectation.threshold_config
        form.setFieldsValue({
          expectation_type: expectation.expectation_type as DQExpectationType,
          column_name: expectation.column_name ?? undefined,
          priority: expectation.priority,
          threshold_type: tc.type,
          threshold_min: tc.min ?? undefined,
          threshold_max: tc.max ?? undefined,
          threshold_multiplier: tc.multiplier ?? undefined,
          threshold_lookback_days: tc.lookback_days ?? undefined,
        })
      } else {
        form.resetFields()
      }
    }
  }, [expectation, form])

  const buildThresholdConfig = (values: FormValues): ThresholdConfig => {
    const config: ThresholdConfig = {
      type: values.threshold_type,
    }

    if (values.threshold_type === 'absolute') {
      if (values.threshold_min !== undefined) config.min = values.threshold_min
      if (values.threshold_max !== undefined) config.max = values.threshold_max
    } else {
      if (values.threshold_multiplier !== undefined) {
        config.multiplier = values.threshold_multiplier
      }
      if (values.threshold_lookback_days !== undefined) {
        config.lookback_days = values.threshold_lookback_days
      }
      // Allow absolute bounds as fallback
      if (values.threshold_min !== undefined) config.min = values.threshold_min
      if (values.threshold_max !== undefined) config.max = values.threshold_max
    }

    return config
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      const thresholdConfig = buildThresholdConfig(values)

      if (isEdit && expectation) {
        await updateExpectation.mutateAsync({
          expectationId: expectation.id,
          data: {
            expectation_type: values.expectation_type,
            column_name: requiresColumn ? values.column_name : null,
            priority: values.priority,
            threshold_config: thresholdConfig,
          },
        })
        message.success('Expectation updated')
      } else {
        await createExpectation.mutateAsync({
          config_id: configId,
          expectation_type: values.expectation_type,
          column_name: requiresColumn ? values.column_name : null,
          priority: values.priority,
          threshold_config: thresholdConfig,
        })
        message.success('Expectation created')
      }
      onClose()
    } catch {
      const error = createExpectation.error || updateExpectation.error
      if (error) {
        message.error('Failed to save expectation')
      }
    }
  }

  const isPending = createExpectation.isPending || updateExpectation.isPending

  return (
    <Modal
      title={isEdit ? 'Edit Expectation' : 'Add Expectation'}
      open={open}
      onOk={handleSubmit}
      onCancel={onClose}
      confirmLoading={isPending}
      okText={isEdit ? 'Update' : 'Add'}
      width={500}
      afterOpenChange={handleAfterOpenChange}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={DEFAULT_FORM_VALUES}>
        <Form.Item
          name="expectation_type"
          label="Metric Type"
          rules={[{ required: true }]}
        >
          <Select
            options={EXPECTATION_TYPES.map((t) => ({
              value: t.value,
              label: t.label,
            }))}
          />
        </Form.Item>

        {requiresColumn && (
          <Form.Item
            name="column_name"
            label="Column"
            rules={[{ required: true, message: 'Column is required for this metric type' }]}
          >
            <Input placeholder="e.g., email" />
          </Form.Item>
        )}

        <Form.Item name="priority" label="Priority" rules={[{ required: true }]}>
          <Select options={PRIORITIES} />
        </Form.Item>

        <Form.Item
          name="threshold_type"
          label="Threshold Strategy"
          rules={[{ required: true }]}
        >
          <Select
            options={THRESHOLD_TYPES.map((t) => ({
              value: t.value,
              label: `${t.label} - ${t.description}`,
            }))}
          />
        </Form.Item>

        {thresholdType === 'absolute' && (
          <>
            <Form.Item name="threshold_min" label="Minimum Value">
              <InputNumber style={{ width: '100%' }} placeholder="Leave empty for no minimum" />
            </Form.Item>
            <Form.Item name="threshold_max" label="Maximum Value">
              <InputNumber style={{ width: '100%' }} placeholder="Leave empty for no maximum" />
            </Form.Item>
          </>
        )}

        {(thresholdType === 'simple_average' || thresholdType === 'dow_adjusted') && (
          <>
            <Form.Item
              name="threshold_multiplier"
              label="Standard Deviation Multiplier"
              tooltip="Values outside mean +/- (multiplier * std dev) are breaches"
            >
              <InputNumber
                style={{ width: '100%' }}
                min={0.1}
                max={10}
                step={0.5}
                placeholder="Default: 2.0"
              />
            </Form.Item>
            <Form.Item
              name="threshold_lookback_days"
              label="Lookback Days"
              tooltip="Number of days of historical data to use"
            >
              <InputNumber
                style={{ width: '100%' }}
                min={7}
                max={365}
                placeholder={thresholdType === 'dow_adjusted' ? 'Default: 90' : 'Default: 30'}
              />
            </Form.Item>
            <Form.Item
              name="threshold_min"
              label="Absolute Minimum (optional)"
              tooltip="Fall back if no historical data"
            >
              <InputNumber style={{ width: '100%' }} placeholder="Optional floor" />
            </Form.Item>
            <Form.Item
              name="threshold_max"
              label="Absolute Maximum (optional)"
              tooltip="Fall back if no historical data"
            >
              <InputNumber style={{ width: '100%' }} placeholder="Optional ceiling" />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  )
}
