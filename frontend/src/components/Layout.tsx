import { Layout as AntLayout, theme } from 'antd'
import { Outlet, useLocation } from 'react-router-dom'
import { CollapsibleSidebar } from './CollapsibleSidebar'
import { SearchBar } from './SearchBar'
import { UserMenu } from './UserMenu'
import { useSidebar } from '../hooks/useSidebar'

const { Header, Content } = AntLayout
const { useToken } = theme

const COLLAPSED_WIDTH = 60
const EXPANDED_WIDTH = 220

export function Layout() {
  const { collapsed } = useSidebar()
  const location = useLocation()
  const isHomePage = location.pathname === '/'
  const { token } = useToken()

  const sidebarWidth = collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <CollapsibleSidebar />
      <AntLayout
        style={{
          marginLeft: sidebarWidth,
          transition: 'margin-left 0.2s ease',
        }}
      >
        {/* Hide header on home page for clean search-first experience */}
        {!isHomePage && (
          <Header
            style={{
              background: token.colorBgContainer,
              padding: '0 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              borderBottom: `1px solid ${token.colorBorderSecondary}`,
              position: 'sticky',
              top: 0,
              zIndex: 10,
            }}
          >
            {/* Centered search bar using absolute positioning */}
            <div
              style={{
                position: 'absolute',
                left: '50%',
                transform: 'translateX(-50%)',
              }}
            >
              <SearchBar width={450} />
            </div>
            {/* Right-aligned user menu */}
            <UserMenu />
          </Header>
        )}
        <Content
          style={{
            margin: isHomePage ? 0 : 24,
            padding: isHomePage ? 0 : 24,
            background: isHomePage ? token.colorBgLayout : token.colorBgContainer,
            minHeight: isHomePage ? 'calc(100vh - 0px)' : 280,
          }}
        >
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
