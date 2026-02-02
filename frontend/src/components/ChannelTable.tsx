/**
 * Table component for displaying notification channels with filtering and actions.
 */

import { useState } from 'react'
import { Button, Modal, Space, Switch, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  DeleteOutlined,
  SendOutlined,
  MailOutlined,
  SlackOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import type { ChannelType, NotificationChannel } from '../api/types'
import {
  useNotificationChannels,
  useUpdateNotificationChannel,
  useDeleteNotificationChannel,
  useTestNotificationChannel,
} from '../hooks/useNotifications'

const { Text } = Typography

interface ChannelTableProps {
  initialChannelType?: ChannelType
  limit?: number
  showFilters?: boolean
}

const channelTypeIcons: Record<ChannelType, React.ReactNode> = {
  email: <MailOutlined />,
  slack: <SlackOutlined />,
  webhook: <ApiOutlined />,
}

const channelTypeColors: Record<ChannelType, string> = {
  email: 'blue',
  slack: 'purple',
  webhook: 'green',
}

export function ChannelTable({
  initialChannelType,
  limit = 50,
  showFilters: _showFilters = true,
}: ChannelTableProps) {
  void _showFilters // TODO: implement filters UI
  const { data: channels, isLoading, error } = useNotificationChannels({
    channel_type: initialChannelType,
    limit,
  })

  const updateChannel = useUpdateNotificationChannel()
  const deleteChannel = useDeleteNotificationChannel()
  const testChannel = useTestNotificationChannel()

  // Delete modal state
  const [deleteModalVisible, setDeleteModalVisible] = useState(false)
  const [selectedChannel, setSelectedChannel] = useState<NotificationChannel | null>(null)

  const handleToggleEnabled = async (channel: NotificationChannel) => {
    try {
      await updateChannel.mutateAsync({
        channelId: channel.id,
        data: { is_enabled: !channel.is_enabled },
      })
      message.success(`Channel ${channel.is_enabled ? 'disabled' : 'enabled'}`)
    } catch {
      message.error('Failed to update channel')
    }
  }

  const handleTest = async (channelId: number) => {
    try {
      const result = await testChannel.mutateAsync(channelId)
      if (result.success) {
        message.success(result.message || 'Test notification sent')
      } else {
        message.error(result.message || 'Test failed')
      }
    } catch {
      message.error('Failed to test channel')
    }
  }

  const handleDeleteClick = (channel: NotificationChannel) => {
    setSelectedChannel(channel)
    setDeleteModalVisible(true)
  }

  const handleDeleteConfirm = async () => {
    if (!selectedChannel) return

    try {
      await deleteChannel.mutateAsync(selectedChannel.id)
      message.success('Channel deleted')
      setDeleteModalVisible(false)
    } catch {
      message.error('Failed to delete channel')
    }
  }

  const columns: ColumnsType<NotificationChannel> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name) => <Text strong>{name}</Text>,
    },
    {
      title: 'Type',
      dataIndex: 'channel_type',
      key: 'type',
      width: 120,
      render: (channelType: ChannelType) => (
        <Tag icon={channelTypeIcons[channelType]} color={channelTypeColors[channelType]}>
          {channelType.charAt(0).toUpperCase() + channelType.slice(1)}
        </Tag>
      ),
    },
    {
      title: 'Configuration',
      key: 'config',
      render: (_, record) => {
        const config = record.config
        if (record.channel_type === 'email') {
          return <Text type="secondary">{config.recipients as string || 'No recipients'}</Text>
        } else if (record.channel_type === 'slack') {
          return <Text type="secondary">Webhook configured</Text>
        } else if (record.channel_type === 'webhook') {
          return (
            <Text type="secondary" ellipsis style={{ maxWidth: 200 }}>
              {config.url as string || 'No URL'}
            </Text>
          )
        }
        return <Text type="secondary">-</Text>
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created',
      width: 120,
      render: (created) => new Date(created).toLocaleDateString(),
    },
    {
      title: 'Enabled',
      dataIndex: 'is_enabled',
      key: 'enabled',
      width: 90,
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggleEnabled(record)}
          loading={updateChannel.isPending}
          size="small"
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<SendOutlined />}
            onClick={() => handleTest(record.id)}
            loading={testChannel.isPending}
            title="Send Test"
          />
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteClick(record)}
            title="Delete"
          />
        </Space>
      ),
    },
  ]

  if (error) {
    return <Text type="danger">Error loading channels: {error.message}</Text>
  }

  return (
    <div>
      <Table
        columns={columns}
        dataSource={channels}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        size="small"
      />

      <Modal
        title="Delete Channel"
        open={deleteModalVisible}
        onOk={handleDeleteConfirm}
        onCancel={() => setDeleteModalVisible(false)}
        confirmLoading={deleteChannel.isPending}
        okText="Delete"
        okButtonProps={{ danger: true }}
      >
        {selectedChannel && (
          <Text>
            Are you sure you want to delete channel{' '}
            <Text strong>"{selectedChannel.name}"</Text>? This will also delete all associated
            notification rules. This action cannot be undone.
          </Text>
        )}
      </Modal>
    </div>
  )
}
