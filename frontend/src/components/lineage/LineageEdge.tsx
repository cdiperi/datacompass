/**
 * Custom React Flow edge component for lineage visualization.
 */

import { memo } from 'react'
import { BaseEdge, getStraightPath, type EdgeProps } from '@xyflow/react'
import type { LineageEdgeData } from './useLineageLayout'

// Get edge style based on confidence
function getEdgeStyle(confidence: string, dependencyType: string): React.CSSProperties {
  const isDashed = dependencyType === 'INDIRECT'

  switch (confidence) {
    case 'HIGH':
      return {
        strokeWidth: 2,
        stroke: '#1677ff',
        strokeDasharray: isDashed ? '5,5' : undefined,
      }
    case 'MEDIUM':
      return {
        strokeWidth: 1.5,
        stroke: '#1677ff',
        strokeOpacity: 0.7,
        strokeDasharray: isDashed ? '5,5' : undefined,
      }
    case 'LOW':
    default:
      return {
        strokeWidth: 1,
        stroke: '#8c8c8c',
        strokeOpacity: 0.6,
        strokeDasharray: '4,4',
      }
  }
}

export const LineageEdge = memo(function LineageEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
}: EdgeProps & { data?: LineageEdgeData }) {
  const [edgePath] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  })

  const style = getEdgeStyle(data?.confidence || 'HIGH', data?.dependencyType || 'DIRECT')

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={style}
      markerEnd="url(#lineage-arrow)"
    />
  )
})
