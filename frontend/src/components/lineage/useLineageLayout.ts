/**
 * Hook for computing ELK layout of lineage graphs.
 */

import { useState, useEffect } from 'react'
import ELK from 'elkjs/lib/elk.bundled.js'
import type { Node, Edge } from '@xyflow/react'
import type { LineageGraph, LineageNode, ExternalNode } from '../../api/types'

const elk = new ELK()

const NODE_WIDTH = 220
const NODE_HEIGHT = 60
const ROOT_NODE_WIDTH = 240
const ROOT_NODE_HEIGHT = 70

export interface LineageNodeData extends Record<string, unknown> {
  label: string
  objectType: string
  sourceName: string
  schemaName: string
  objectName: string
  isRoot: boolean
  isExternal: boolean
  objectId?: number
}

export interface LineageEdgeData extends Record<string, unknown> {
  dependencyType: string
  confidence: string
}

type LineageFlowNode = Node<LineageNodeData>
type LineageFlowEdge = Edge<LineageEdgeData>

function getExternalNodeKey(ext: ExternalNode): string {
  return `ext-${ext.schema_name || ''}-${ext.object_name}`
}

export function useLineageLayout(lineage: LineageGraph | undefined): {
  nodes: LineageFlowNode[]
  edges: LineageFlowEdge[]
} {
  const [layoutResult, setLayoutResult] = useState<{
    nodes: LineageFlowNode[]
    edges: LineageFlowEdge[]
  }>({ nodes: [], edges: [] })

  useEffect(() => {
    if (!lineage) {
      setLayoutResult({ nodes: [], edges: [] })
      return
    }

    const computeLayout = async () => {
      const { root, nodes, external_nodes, edges } = lineage

      // Build ELK graph structure
      const elkNodes: Array<{
        id: string
        width: number
        height: number
      }> = []

      const elkEdges: Array<{
        id: string
        sources: string[]
        targets: string[]
      }> = []

      // Add root node
      elkNodes.push({
        id: root.id.toString(),
        width: ROOT_NODE_WIDTH,
        height: ROOT_NODE_HEIGHT,
      })

      // Add other nodes
      nodes.forEach((node) => {
        elkNodes.push({
          id: node.id.toString(),
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
        })
      })

      // Add external nodes
      external_nodes.forEach((ext) => {
        elkNodes.push({
          id: getExternalNodeKey(ext),
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
        })
      })

      // Add edges (flipped for data flow direction)
      edges.forEach((edge, idx) => {
        let toNodeId: string

        if (edge.to_id !== null) {
          toNodeId = edge.to_id.toString()
        } else if (edge.to_external) {
          const ext = edge.to_external as { schema_name?: string; object_name?: string }
          toNodeId = `ext-${ext.schema_name || ''}-${ext.object_name || ''}`
        } else {
          return
        }

        // Flip: data flows from to_id -> from_id
        elkEdges.push({
          id: `edge-${idx}`,
          sources: [toNodeId],
          targets: [edge.from_id.toString()],
        })
      })

      // Compute layout with ELK
      const elkGraph = {
        id: 'root',
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': 'RIGHT',
          'elk.spacing.nodeNode': '50',
          'elk.layered.spacing.nodeNodeBetweenLayers': '100',
          'elk.padding': '[top=20,left=20,bottom=20,right=20]',
        },
        children: elkNodes,
        edges: elkEdges,
      }

      try {
        const layoutedGraph = await elk.layout(elkGraph)

        // Convert to React Flow nodes
        const flowNodes: LineageFlowNode[] = []

        // Map for looking up node data
        const nodeDataMap = new Map<string, LineageNode>()
        nodeDataMap.set(root.id.toString(), root)
        nodes.forEach((n) => nodeDataMap.set(n.id.toString(), n))

        const externalDataMap = new Map<string, ExternalNode>()
        external_nodes.forEach((ext) => externalDataMap.set(getExternalNodeKey(ext), ext))

        layoutedGraph.children?.forEach((elkNode) => {
          const nodeData = nodeDataMap.get(elkNode.id)
          const externalData = externalDataMap.get(elkNode.id)
          const isRoot = elkNode.id === root.id.toString()

          if (nodeData) {
            flowNodes.push({
              id: elkNode.id,
              type: 'lineageNode',
              position: { x: elkNode.x || 0, y: elkNode.y || 0 },
              data: {
                label: `${nodeData.source_name}.${nodeData.schema_name}.${nodeData.object_name}`,
                objectType: nodeData.object_type,
                sourceName: nodeData.source_name,
                schemaName: nodeData.schema_name,
                objectName: nodeData.object_name,
                isRoot,
                isExternal: false,
                objectId: nodeData.id,
              },
            })
          } else if (externalData) {
            flowNodes.push({
              id: elkNode.id,
              type: 'lineageNode',
              position: { x: elkNode.x || 0, y: elkNode.y || 0 },
              data: {
                label: externalData.schema_name
                  ? `${externalData.schema_name}.${externalData.object_name}`
                  : externalData.object_name,
                objectType: externalData.object_type || 'UNKNOWN',
                sourceName: '',
                schemaName: externalData.schema_name || '',
                objectName: externalData.object_name,
                isRoot: false,
                isExternal: true,
              },
            })
          }
        })

        // Convert to React Flow edges (swap source/target for data flow direction)
        const flowEdges: LineageFlowEdge[] = edges.map((edge, idx) => {
          let toNodeId: string

          if (edge.to_id !== null) {
            toNodeId = edge.to_id.toString()
          } else if (edge.to_external) {
            const ext = edge.to_external as { schema_name?: string; object_name?: string }
            toNodeId = `ext-${ext.schema_name || ''}-${ext.object_name || ''}`
          } else {
            toNodeId = ''
          }

          // Flip direction: arrows show data flow, not dependency direction
          return {
            id: `edge-${idx}`,
            source: toNodeId,
            target: edge.from_id.toString(),
            type: 'lineageEdge',
            data: {
              dependencyType: edge.dependency_type,
              confidence: edge.confidence,
            },
          }
        })

        setLayoutResult({ nodes: flowNodes, edges: flowEdges })
      } catch (error) {
        console.error('ELK layout error:', error)
        setLayoutResult({ nodes: [], edges: [] })
      }
    }

    computeLayout()
  }, [lineage])

  return layoutResult
}
