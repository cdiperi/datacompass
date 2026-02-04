/**
 * Settings page with extensible card-based structure.
 */

import { Card, Radio, Space, Typography } from 'antd'
import { BgColorsOutlined } from '@ant-design/icons'
import { useTheme } from '../hooks/useTheme'
import type { ThemeMode } from '../context/ThemeContext'

const { Title, Text } = Typography

export function SettingsPage() {
  const { mode, setMode } = useTheme()

  return (
    <div style={{ padding: 24, maxWidth: 800 }}>
      <Title level={2}>Settings</Title>
      <Text type="secondary">Configure your Data Compass preferences.</Text>

      {/* Appearance Section */}
      <Card
        title={
          <Space>
            <BgColorsOutlined />
            <span>Appearance</span>
          </Space>
        }
        style={{ marginTop: 24 }}
      >
        <div>
          <Text strong>Theme</Text>
          <div style={{ marginTop: 8 }}>
            <Radio.Group
              value={mode}
              onChange={(e) => setMode(e.target.value as ThemeMode)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="light">Light</Radio.Button>
              <Radio.Button value="dark">Dark</Radio.Button>
            </Radio.Group>
          </div>
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            Choose between light and dark color themes.
          </Text>
        </div>
      </Card>

      {/* Future settings sections can be added here following the same pattern:
      <Card
        title={
          <Space>
            <IconHere />
            <span>Section Name</span>
          </Space>
        }
        style={{ marginTop: 16 }}
      >
        Settings controls
      </Card>
      */}
    </div>
  )
}
