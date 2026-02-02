import { Layout as AntLayout, Menu } from 'antd'
import { ClockCircleOutlined, HomeOutlined, SafetyCertificateOutlined, ScheduleOutlined, TableOutlined } from '@ant-design/icons'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { SearchBar } from './SearchBar'

const { Header, Sider, Content } = AntLayout

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

export function Layout() {
  const navigate = useNavigate()
  const location = useLocation()

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  // Determine selected menu key - catalog paths should highlight the Catalog menu item
  const getSelectedKey = () => {
    if (location.pathname === '/') return '/'
    if (location.pathname.startsWith('/catalog')) return '/catalog'
    return location.pathname
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider theme="light" width={200}>
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            fontSize: 16,
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          Data Compass
        </div>
        <Menu
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <AntLayout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <SearchBar />
        </Header>
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: '#fff',
            minHeight: 280,
          }}
        >
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
