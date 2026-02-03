import { Dropdown, Button, Avatar, Space, Typography } from 'antd'
import { UserOutlined, LogoutOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useQueryClient } from '@tanstack/react-query'
import type { MenuProps } from 'antd'

const { Text } = Typography

export function UserMenu() {
  const { user, isAuthenticated, authDisabled, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Don't render if auth is disabled
  if (authDisabled) {
    return null
  }

  // Show login link if not authenticated
  if (!isAuthenticated) {
    return (
      <Button type="link" onClick={() => navigate('/login')}>
        Sign In
      </Button>
    )
  }

  const handleLogout = () => {
    logout()
    queryClient.clear()
    navigate('/login')
  }

  const displayName = user?.display_name || user?.email || 'User'
  const initials = displayName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  const items: MenuProps['items'] = [
    {
      key: 'user-info',
      label: (
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontWeight: 500 }}>{user?.display_name || 'User'}</div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {user?.email}
          </Text>
        </div>
      ),
      disabled: true,
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Sign Out',
      onClick: handleLogout,
    },
  ]

  return (
    <Dropdown menu={{ items }} trigger={['click']} placement="bottomRight">
      <Button type="text" style={{ padding: '4px 8px', height: 'auto' }}>
        <Space>
          <Avatar size="small" style={{ backgroundColor: '#1677ff' }}>
            {initials || <UserOutlined />}
          </Avatar>
          <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {displayName}
          </span>
        </Space>
      </Button>
    </Dropdown>
  )
}
