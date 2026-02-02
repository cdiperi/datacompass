import { useParams, Link } from 'react-router-dom'
import { Typography, Spin, Alert, Breadcrumb, Tabs } from 'antd'
import { HomeOutlined, PartitionOutlined, TableOutlined } from '@ant-design/icons'
import { useObject } from '../hooks/useObjects'
import { ObjectDetail } from '../components/ObjectDetail'
import { LineageList } from '../components/LineageList'

const { Title } = Typography

export function ObjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: object, isLoading, error } = useObject(id || '')

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message={
          <>
            <strong>Error loading object</strong>
            <div>{error.message}</div>
          </>
        }
      />
    )
  }

  if (!object) {
    return (
      <Alert
        type="warning"
        showIcon
        message="Object not found"
      />
    )
  }

  const tabItems = [
    {
      key: 'details',
      label: (
        <span>
          <TableOutlined />
          Details
        </span>
      ),
      children: <ObjectDetail object={object} />,
    },
    {
      key: 'lineage',
      label: (
        <span>
          <PartitionOutlined />
          Lineage
        </span>
      ),
      children: <LineageList objectId={object.id} />,
    },
  ]

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/"><HomeOutlined /></Link> },
          { title: <Link to="/browse">Browse</Link> },
          { title: object.source_name },
          { title: object.schema_name },
          { title: object.object_name },
        ]}
      />

      <Title level={2}>
        {object.object_name}
      </Title>

      <Tabs defaultActiveKey="details" items={tabItems} />
    </div>
  )
}
