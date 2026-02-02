import { Layout, Menu, Tooltip } from 'antd'
import {
  ClockCircleOutlined,
  HomeOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  TableOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useSidebar } from '../hooks/useSidebar'

const { Sider } = Layout

const COLLAPSED_WIDTH = 60
const EXPANDED_WIDTH = 220

const menuItems = [
  {
    key: '/',
    icon: <HomeOutlined />,
    label: 'Home',
  },
  {
    key: '/catalog',
    icon: <TableOutlined />,
    label: 'Catalog',
  },
  {
    key: '/dq',
    icon: <SafetyCertificateOutlined />,
    label: 'Data Quality',
  },
  {
    key: '/deprecation',
    icon: <ClockCircleOutlined />,
    label: 'Deprecation',
  },
  {
    key: '/scheduler',
    icon: <ScheduleOutlined />,
    label: 'Scheduler',
  },
]

export function CollapsibleSidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { collapsed, toggleCollapsed } = useSidebar()

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  // Determine selected menu key - catalog paths should highlight the Catalog menu item
  const getSelectedKey = () => {
    if (location.pathname === '/') return '/'
    if (location.pathname.startsWith('/catalog')) return '/catalog'
    if (location.pathname.startsWith('/dq')) return '/dq'
    if (location.pathname.startsWith('/deprecation')) return '/deprecation'
    if (location.pathname.startsWith('/scheduler')) return '/scheduler'
    return location.pathname
  }

  // Build menu items with tooltips when collapsed
  const menuItemsWithTooltips = menuItems.map((item) => ({
    ...item,
    label: collapsed ? (
      <Tooltip title={item.label} placement="right">
        <span>{item.label}</span>
      </Tooltip>
    ) : (
      item.label
    ),
  }))

  return (
    <Sider
      theme="light"
      width={EXPANDED_WIDTH}
      collapsedWidth={COLLAPSED_WIDTH}
      collapsed={collapsed}
      style={{
        borderRight: '1px solid #f0f0f0',
        overflow: 'auto',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 100,
      }}
    >
      {/* Toggle button row */}
      <div
        style={{
          height: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          padding: collapsed ? 0 : '0 16px',
          borderBottom: '1px solid #f0f0f0',
          cursor: 'pointer',
        }}
        onClick={toggleCollapsed}
      >
        {collapsed ? (
          <Tooltip title="Expand menu" placement="right">
            <MenuUnfoldOutlined style={{ fontSize: 18 }} />
          </Tooltip>
        ) : (
          <>
            <MenuFoldOutlined style={{ fontSize: 18, marginRight: 12 }} />
            <span style={{ fontWeight: 600, fontSize: 14 }}>Data Compass</span>
          </>
        )}
      </div>

      {/* Navigation menu */}
      <Menu
        mode="inline"
        selectedKeys={[getSelectedKey()]}
        items={menuItemsWithTooltips}
        onClick={handleMenuClick}
        style={{ borderRight: 0 }}
        inlineCollapsed={collapsed}
      />
    </Sider>
  )
}
