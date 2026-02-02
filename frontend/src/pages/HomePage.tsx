import { Row, Col, Typography, Statistic, Card, Spin, Empty, Alert } from 'antd'
import { DatabaseOutlined, TableOutlined } from '@ant-design/icons'
import { useSources } from '../hooks/useSources'
import { useObjects } from '../hooks/useObjects'
import { SourceCard } from '../components/SourceCard'
import { useNavigate } from 'react-router-dom'

const { Title } = Typography

export function HomePage() {
  const navigate = useNavigate()
  const { data: sources, isLoading: sourcesLoading, error: sourcesError } = useSources()
  const { data: objects, isLoading: objectsLoading } = useObjects()

  if (sourcesError) {
    return (
      <Alert
        type="error"
        showIcon
        message={
          <>
            <strong>Error loading sources</strong>
            <div>{sourcesError.message}</div>
          </>
        }
      />
    )
  }

  const totalObjects = objects?.length || 0

  return (
    <div>
      <Title level={2}>Dashboard</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Data Sources"
              value={sources?.length || 0}
              prefix={<DatabaseOutlined />}
              loading={sourcesLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Objects"
              value={totalObjects}
              prefix={<TableOutlined />}
              loading={objectsLoading}
            />
          </Card>
        </Col>
      </Row>

      <Title level={3}>Data Sources</Title>

      {sourcesLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : sources && sources.length > 0 ? (
        <Row gutter={[16, 16]}>
          {sources.map((source) => (
            <Col xs={24} sm={12} lg={8} key={source.id}>
              <SourceCard
                source={source}
                onClick={() => navigate(`/browse?source=${encodeURIComponent(source.name)}`)}
              />
            </Col>
          ))}
        </Row>
      ) : (
        <Empty
          description="No data sources configured"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
    </div>
  )
}
