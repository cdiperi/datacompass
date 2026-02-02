import { Card, Statistic, Tag, Typography } from 'antd'
import { DatabaseOutlined, ClockCircleOutlined } from '@ant-design/icons'
import type { DataSource } from '../api/types'

const { Text } = Typography

interface SourceCardProps {
  source: DataSource
  onClick?: () => void
}

export function SourceCard({ source, onClick }: SourceCardProps) {
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never'
    return new Date(dateStr).toLocaleDateString()
  }

  return (
    <Card
      hoverable={!!onClick}
      onClick={onClick}
      style={{ width: '100%' }}
    >
      <Card.Meta
        avatar={<DatabaseOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {source.display_name || source.name}
            <Tag color={source.is_active ? 'green' : 'default'}>
              {source.is_active ? 'Active' : 'Inactive'}
            </Tag>
          </div>
        }
        description={
          <>
            <Text type="secondary">{source.source_type}</Text>
            <div style={{ marginTop: 8, display: 'flex', gap: 24 }}>
              <Statistic
                title="Last Scan"
                value={formatDate(source.last_scan_at)}
                prefix={<ClockCircleOutlined />}
                styles={{ content: { fontSize: 14 } }}
              />
              {source.last_scan_status && (
                <Tag color={source.last_scan_status === 'success' ? 'green' : 'red'}>
                  {source.last_scan_status}
                </Tag>
              )}
            </div>
          </>
        }
      />
    </Card>
  )
}
