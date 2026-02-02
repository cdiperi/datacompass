/**
 * Custom React Flow node component for lineage visualization.
 */

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Typography } from 'antd'
import type { LineageNodeData } from './useLineageLayout'

const { Text } = Typography

// Colors by object type
const TYPE_COLORS: Record<string, string> = {
  TABLE: '#1677ff',
  VIEW: '#722ed1',
  MATERIALIZED_VIEW: '#13c2c2',
  EXTERNAL: '#8c8c8c',
  UNKNOWN: '#8c8c8c',
}

// Get border color based on object type
function getBorderColor(objectType: string, isExternal: boolean): string {
  if (isExternal) return '#8c8c8c'
  return TYPE_COLORS[objectType] || TYPE_COLORS.UNKNOWN
}

export const LineageNode = memo(function LineageNode({
  data,
}: NodeProps & { data: LineageNodeData }) {
  const { label, objectType, isRoot, isExternal } = data
  const borderColor = getBorderColor(objectType, isExternal)

  return (
    <>
      <Handle type="target" position={Position.Left} />
      <div
        style={{
          padding: '8px 12px',
          background: isRoot ? '#f0f5ff' : '#fff',
          border: `2px ${isExternal ? 'dashed' : 'solid'} ${borderColor}`,
          borderRadius: 8,
          boxShadow: isRoot ? '0 2px 8px rgba(22, 119, 255, 0.25)' : '0 1px 4px rgba(0, 0, 0, 0.1)',
          minWidth: isRoot ? 220 : 200,
          maxWidth: 280,
          cursor: isExternal ? 'default' : 'pointer',
        }}
      >
        <div style={{ marginBottom: 4 }}>
          <Text
            strong={isRoot}
            style={{
              fontSize: 12,
              color: borderColor,
              textTransform: 'uppercase',
            }}
          >
            {objectType}
            {isExternal && ' (external)'}
          </Text>
        </div>
        <Text
          ellipsis={{ tooltip: label }}
          style={{
            fontSize: isRoot ? 13 : 12,
            fontWeight: isRoot ? 600 : 400,
            display: 'block',
            maxWidth: 256,
          }}
        >
          {label}
        </Text>
      </div>
      <Handle type="source" position={Position.Right} />
    </>
  )
})
