import { useParams, Link } from 'react-router-dom'
import { Typography, Spin, Alert, Breadcrumb, Tabs } from 'antd'
import { HomeOutlined, PartitionOutlined, TableOutlined } from '@ant-design/icons'
import { useObject } from '../hooks/useObjects'
import { ObjectDetail } from '../components/ObjectDetail'
import { LineageList } from '../components/LineageList'
import { paramsToFqn, getSourceUrl, getSchemaUrl } from '../utils/urls'

const { Title } = Typography

export function ObjectDetailPage() {
  const { source, schema, object } = useParams<{ source: string; schema: string; object: string }>()
  const fqn = paramsToFqn(source!, schema!, object!)
  const { data: objectData, isLoading, error } = useObject(fqn)

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

  if (!objectData) {
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
      children: <ObjectDetail object={objectData} />,
    },
    {
      key: 'lineage',
      label: (
        <span>
          <PartitionOutlined />
          Lineage
        </span>
      ),
      children: <LineageList objectId={objectData.id} />,
    },
  ]

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/"><HomeOutlined /></Link> },
          { title: <Link to="/catalog">Catalog</Link> },
          { title: <Link to={getSourceUrl(objectData.source_name)}>{objectData.source_name}</Link> },
          { title: <Link to={getSchemaUrl(objectData.source_name, objectData.schema_name)}>{objectData.schema_name}</Link> },
          { title: objectData.object_name },
        ]}
      />

      <Title level={2}>
        {objectData.object_name}
      </Title>

      <Tabs defaultActiveKey="details" items={tabItems} />
    </div>
  )
}
