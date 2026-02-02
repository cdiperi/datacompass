/**
 * Main React Flow container for lineage graph visualization.
 */

import { useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { LineageNode } from './LineageNode'
import { LineageEdge } from './LineageEdge'
import { useLineageLayout, type LineageNodeData } from './useLineageLayout'
import { getObjectUrl } from '../../utils/urls'
import type { LineageGraph as LineageGraphType } from '../../api/types'

const nodeTypes = {
  lineageNode: LineageNode,
}

const edgeTypes = {
  lineageEdge: LineageEdge,
}

interface LineageGraphInnerProps {
  lineage: LineageGraphType | undefined
}

function LineageGraphInner({ lineage }: LineageGraphInnerProps) {
  const navigate = useNavigate()
  const { fitView } = useReactFlow()
  const { nodes: layoutNodes, edges: layoutEdges } = useLineageLayout(lineage)

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges)

  // Update nodes/edges when layout changes
  useEffect(() => {
    setNodes(layoutNodes)
    setEdges(layoutEdges)
    // Fit view after layout update
    setTimeout(() => fitView({ padding: 0.2 }), 50)
  }, [layoutNodes, layoutEdges, setNodes, setEdges, fitView])

  // Navigate to object detail on node click
  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const data = node.data as LineageNodeData
      if (data.isExternal) return

      navigate(
        getObjectUrl({
          source_name: data.sourceName,
          schema_name: data.schemaName,
          object_name: data.objectName,
        })
      )
    },
    [navigate]
  )

  if (!lineage || (nodes.length === 0 && edges.length === 0)) {
    return null
  }

  return (
    <div style={{ width: '100%', height: 500 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
        maxZoom={2}
      >
        <Background />
        <Controls />
        {/* Custom arrow marker for edges */}
        <svg>
          <defs>
            <marker
              id="lineage-arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#1677ff" />
            </marker>
          </defs>
        </svg>
      </ReactFlow>
    </div>
  )
}

interface LineageGraphProps {
  lineage: LineageGraphType | undefined
}

export function LineageGraph({ lineage }: LineageGraphProps) {
  return (
    <ReactFlowProvider>
      <LineageGraphInner lineage={lineage} />
    </ReactFlowProvider>
  )
}
