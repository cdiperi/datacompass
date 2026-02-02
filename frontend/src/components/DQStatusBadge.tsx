/**
 * Badge components for DQ status and priority display.
 */

import { Tag } from 'antd'
import type { DQBreachStatus, DQPriority } from '../api/types'

interface StatusBadgeProps {
  status: DQBreachStatus
}

export function DQStatusBadge({ status }: StatusBadgeProps) {
  const config: Record<DQBreachStatus, { color: string; label: string }> = {
    open: { color: 'red', label: 'Open' },
    acknowledged: { color: 'orange', label: 'Acknowledged' },
    dismissed: { color: 'default', label: 'Dismissed' },
    resolved: { color: 'green', label: 'Resolved' },
  }

  const { color, label } = config[status] || { color: 'default', label: status }

  return <Tag color={color}>{label}</Tag>
}

interface PriorityBadgeProps {
  priority: DQPriority
}

export function DQPriorityBadge({ priority }: PriorityBadgeProps) {
  const config: Record<DQPriority, { color: string; label: string }> = {
    critical: { color: 'red', label: 'Critical' },
    high: { color: 'orange', label: 'High' },
    medium: { color: 'blue', label: 'Medium' },
    low: { color: 'default', label: 'Low' },
  }

  const { color, label } = config[priority] || { color: 'default', label: priority }

  return <Tag color={color}>{label}</Tag>
}

interface DirectionBadgeProps {
  direction: 'high' | 'low'
}

export function DQDirectionBadge({ direction }: DirectionBadgeProps) {
  if (direction === 'high') {
    return (
      <Tag color="red">
        <span style={{ fontWeight: 600 }}>&uarr;</span> High
      </Tag>
    )
  }
  return (
    <Tag color="blue">
      <span style={{ fontWeight: 600 }}>&darr;</span> Low
    </Tag>
  )
}
