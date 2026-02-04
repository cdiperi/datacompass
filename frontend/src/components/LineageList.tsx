/**
 * Component for displaying lineage (dependencies/dependents) as a list or graph.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Alert,
  Empty,
  Radio,
  Segmented,
  Spin,
  Table,
  Tag,
  Typography,
  InputNumber,
  Space,
} from 'antd'
import { TableOutlined, ApartmentOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useLineage } from '../hooks/useLineage'
import type { LineageNode, ExternalNode } from '../api/types'
import { getObjectUrl } from '../utils/urls'
import { LineageGraph } from './lineage/LineageGraph'

const { Text } = Typography

interface LineageListProps {
  objectId: number
}

type LineageItem = (LineageNode | ExternalNode) & { isExternal?: boolean }

type ViewMode = 'table' | 'graph'

export function LineageList({ objectId }: LineageListProps) {
  const [direction, setDirection] = useState<'upstream' | 'downstream' | 'both'>('both')
  const [depth, setDepth] = useState(3)
  const [viewMode, setViewMode] = useState<ViewMode>('graph')

  const { data: lineage, isLoading, error } = useLineage(objectId, {
    direction,
    depth,
  })

  const columns: ColumnsType<LineageItem> = [
    {
      title: 'Distance',
      dataIndex: 'distance',
      key: 'distance',
      width: 80,
      align: 'center',
      render: (distance: number) => (
        <Tag color={distance === 1 ? 'blue' : 'default'}>{distance}</Tag>
      ),
    },
    {
      title: 'Object',
      key: 'object',
      render: (_, record) => {
        if ('isExternal' in record && record.isExternal) {
          const ext = record as ExternalNode
          return (
            <Text type="secondary">
              {ext.schema_name ? `${ext.schema_name}.` : ''}
              {ext.object_name} (external)
            </Text>
          )
        }
        const node = record as LineageNode
        return (
          <Link to={getObjectUrl(node)}>
            {node.source_name}.{node.schema_name}.{node.object_name}
          </Link>
        )
      },
    },
    {
      title: 'Type',
      key: 'type',
      width: 100,
      render: (_, record) => {
        if ('isExternal' in record && record.isExternal) {
          const ext = record as ExternalNode
          return <Text type="secondary">{ext.object_type || '?'}</Text>
        }
        const node = record as LineageNode
        return <Tag>{node.object_type}</Tag>
      },
    },
  ]

  // Combine internal and external nodes for display
  const items: LineageItem[] = [
    ...(lineage?.nodes || []),
    ...(lineage?.external_nodes || []).map((ext) => ({
      ...ext,
      isExternal: true as const,
    })),
  ].sort((a, b) => a.distance - b.distance)

  const hasData = items.length > 0

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Radio.Group
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
          optionType="button"
          buttonStyle="solid"
          options={[
            { label: 'All', value: 'both' },
            { label: 'Upstream', value: 'upstream' },
            { label: 'Downstream', value: 'downstream' },
          ]}
        />
        <Space>
          <Text type="secondary">Depth:</Text>
          <InputNumber
            min={1}
            max={10}
            value={depth}
            onChange={(value) => setDepth(value || 3)}
            size="small"
            style={{ width: 60 }}
          />
        </Space>
        <Segmented
          value={viewMode}
          onChange={(value) => setViewMode(value as ViewMode)}
          options={[
            { label: 'Graph', value: 'graph', icon: <ApartmentOutlined /> },
            { label: 'Table', value: 'table', icon: <TableOutlined /> },
          ]}
        />
      </Space>

      {error && (
        <Alert
          type="error"
          showIcon
          message="Error loading lineage"
          description={error.message}
          style={{ marginBottom: 16 }}
        />
      )}

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      ) : !hasData ? (
        <Empty
          description={
            direction === 'both'
              ? 'No lineage found'
              : direction === 'upstream'
                ? 'No upstream dependencies found'
                : 'No downstream dependents found'
          }
        />
      ) : viewMode === 'graph' ? (
        <>
          <LineageGraph lineage={lineage} />
          {lineage?.truncated && (
            <Alert
              type="info"
              showIcon
              message={`Graph truncated at depth ${depth}. Increase depth to see more.`}
              style={{ marginTop: 16 }}
            />
          )}
        </>
      ) : (
        <>
          <Table
            dataSource={items}
            columns={columns}
            rowKey={(record) =>
              'id' in record
                ? `node-${record.id}`
                : `ext-${record.schema_name}-${record.object_name}`
            }
            pagination={false}
            size="small"
          />
          {lineage?.truncated && (
            <Alert
              type="info"
              showIcon
              message={`Graph truncated at depth ${depth}. Increase depth to see more.`}
              style={{ marginTop: 16 }}
            />
          )}
        </>
      )}
    </div>
  )
}
