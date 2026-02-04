import { Typography } from 'antd'
import { CompassOutlined } from '@ant-design/icons'
import { SearchBar } from '../components/SearchBar'

const { Title, Text } = Typography

export function HomePage() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 'calc(110px + 21vh) 24px 24px 24px',
      }}
    >
      {/* Brand */}
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <CompassOutlined
          style={{
            fontSize: 64,
            color: '#1677ff',
            marginBottom: 16,
          }}
        />
        <Title
          level={1}
          style={{
            margin: 0,
            fontWeight: 300,
            letterSpacing: -1,
          }}
        >
          Data Compass
        </Title>
        <Text type="secondary" style={{ fontSize: 16 }}>
          Navigate your data with confidence
        </Text>
      </div>

      {/* Search */}
      <div style={{ width: '100%', maxWidth: 560 }}>
        <SearchBar
          autoFocus
          size="large"
          width="100%"
          placeholder="Search for tables, views, columns..."
        />
      </div>
    </div>
  )
}
