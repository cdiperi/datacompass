import { Descriptions, Table, Typography, Input, Button, Space, message } from 'antd'
import { EditOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { TagEditor } from './TagEditor'
import { useUpdateObject } from '../hooks/useObjects'
import type { CatalogObjectDetail, ColumnSummary } from '../api/types'

const { Text, Paragraph } = Typography
const { TextArea } = Input

interface ObjectDetailProps {
  object: CatalogObjectDetail
}

export function ObjectDetail({ object }: ObjectDetailProps) {
  const [isEditingDescription, setIsEditingDescription] = useState(false)
  const [descriptionValue, setDescriptionValue] = useState(
    object.user_metadata?.description as string || ''
  )
  const updateObject = useUpdateObject()

  const description = (object.user_metadata?.description as string) || null
  const tags = (object.user_metadata?.tags as string[]) || []

  const handleSaveDescription = async () => {
    try {
      await updateObject.mutateAsync({
        id: object.id,
        data: { description: descriptionValue },
      })
      setIsEditingDescription(false)
      message.success('Description updated')
    } catch {
      message.error('Failed to update description')
    }
  }

  const handleCancelEdit = () => {
    setDescriptionValue(description || '')
    setIsEditingDescription(false)
  }

  const handleAddTag = async (tag: string) => {
    try {
      await updateObject.mutateAsync({
        id: object.id,
        data: { tags_to_add: [tag] },
      })
      message.success(`Tag "${tag}" added`)
    } catch {
      message.error('Failed to add tag')
    }
  }

  const handleRemoveTag = async (tag: string) => {
    try {
      await updateObject.mutateAsync({
        id: object.id,
        data: { tags_to_remove: [tag] },
      })
      message.success(`Tag "${tag}" removed`)
    } catch {
      message.error('Failed to remove tag')
    }
  }

  const columnTableColumns: ColumnsType<ColumnSummary> = [
    {
      title: 'Column Name',
      dataIndex: 'column_name',
      key: 'column_name',
    },
    {
      title: 'Data Type',
      dataIndex: 'data_type',
      key: 'data_type',
      render: (type: string | null) => type || '-',
    },
    {
      title: 'Nullable',
      dataIndex: 'nullable',
      key: 'nullable',
      render: (nullable: boolean | null) => {
        if (nullable === null) return '-'
        return nullable ? 'Yes' : 'No'
      },
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string | null) => (
        <Text type={desc ? undefined : 'secondary'}>
          {desc || 'No description'}
        </Text>
      ),
    },
  ]

  return (
    <div>
      <Descriptions bordered column={2} style={{ marginBottom: 24 }}>
        <Descriptions.Item label="Source">{object.source_name}</Descriptions.Item>
        <Descriptions.Item label="Type">{object.object_type}</Descriptions.Item>
        <Descriptions.Item label="Schema">{object.schema_name}</Descriptions.Item>
        <Descriptions.Item label="Name">{object.object_name}</Descriptions.Item>
        <Descriptions.Item label="Created">
          {new Date(object.created_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="Updated">
          {new Date(object.updated_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="Description" span={2}>
          {isEditingDescription ? (
            <Space direction="vertical" style={{ width: '100%' }}>
              <TextArea
                value={descriptionValue}
                onChange={(e) => setDescriptionValue(e.target.value)}
                rows={3}
                placeholder="Enter description..."
              />
              <Space>
                <Button
                  type="primary"
                  icon={<CheckOutlined />}
                  onClick={handleSaveDescription}
                  loading={updateObject.isPending}
                >
                  Save
                </Button>
                <Button
                  icon={<CloseOutlined />}
                  onClick={handleCancelEdit}
                >
                  Cancel
                </Button>
              </Space>
            </Space>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Paragraph style={{ margin: 0 }}>
                {description || <Text type="secondary">No description</Text>}
              </Paragraph>
              <Button
                type="text"
                icon={<EditOutlined />}
                onClick={() => setIsEditingDescription(true)}
              />
            </div>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Tags" span={2}>
          <TagEditor
            tags={tags}
            onAddTag={handleAddTag}
            onRemoveTag={handleRemoveTag}
            disabled={updateObject.isPending}
          />
        </Descriptions.Item>
      </Descriptions>

      <Typography.Title level={4}>Columns ({object.columns.length})</Typography.Title>
      <Table
        dataSource={object.columns}
        columns={columnTableColumns}
        rowKey="column_name"
        pagination={false}
        size="small"
      />
    </div>
  )
}
