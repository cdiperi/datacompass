import { useState, useMemo } from 'react'
import { Typography, Select, Space, Alert, Breadcrumb } from 'antd'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { HomeOutlined } from '@ant-design/icons'
import { useObjects } from '../hooks/useObjects'
import { useSources } from '../hooks/useSources'
import { ObjectTable } from '../components/ObjectTable'
import { getSourceUrl, getSchemaUrl } from '../utils/urls'

const { Title } = Typography

const objectTypes = ['TABLE', 'VIEW', 'MATERIALIZED_VIEW', 'FUNCTION']

export function BrowsePage() {
  const navigate = useNavigate()
  const { source: sourceParam, schema: schemaParam } = useParams<{ source?: string; schema?: string }>()

  // Decode URL params
  const sourceFilter = sourceParam ? decodeURIComponent(sourceParam) : undefined
  const schemaFilter = schemaParam ? decodeURIComponent(schemaParam) : undefined

  // Type filter state (not in URL since it's a secondary filter)
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined)

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Fetch data
  const { data: sources } = useSources()
  const { data: objects, isLoading, error } = useObjects({
    source: sourceFilter,
    object_type: typeFilter,
    schema: schemaFilter,
  })

  // Extract unique schemas from objects for the filter dropdown
  const schemas = useMemo(() => {
    if (!objects) return []
    const uniqueSchemas = [...new Set(objects.map((o) => o.schema_name))]
    return uniqueSchemas.sort()
  }, [objects])

  const handleSourceChange = (value: string | undefined) => {
    if (value) {
      navigate(getSourceUrl(value))
    } else {
      navigate('/catalog')
    }
    setPage(1)
  }

  const handleSchemaChange = (value: string | undefined) => {
    if (value && sourceFilter) {
      navigate(getSchemaUrl(sourceFilter, value))
    } else if (sourceFilter) {
      navigate(getSourceUrl(sourceFilter))
    } else {
      navigate('/catalog')
    }
    setPage(1)
  }

  const handleTypeChange = (value: string | undefined) => {
    setTypeFilter(value)
    setPage(1)
  }

  const handlePageChange = (newPage: number, newPageSize: number) => {
    setPage(newPage)
    setPageSize(newPageSize)
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message={
          <>
            <strong>Error loading objects</strong>
            <div>{error.message}</div>
          </>
        }
      />
    )
  }

  // Client-side pagination since we fetch all objects matching filters
  const paginatedObjects = objects
    ? objects.slice((page - 1) * pageSize, page * pageSize)
    : []

  // Build breadcrumb items
  const breadcrumbItems = [
    { title: <Link to="/"><HomeOutlined /></Link> },
    { title: sourceFilter ? <Link to="/catalog">Catalog</Link> : 'Catalog' },
  ]
  if (sourceFilter) {
    breadcrumbItems.push({
      title: schemaFilter ? <Link to={getSourceUrl(sourceFilter)}>{sourceFilter}</Link> : sourceFilter,
    })
  }
  if (schemaFilter) {
    breadcrumbItems.push({ title: schemaFilter })
  }

  // Determine page title
  let pageTitle = 'Browse Catalog'
  if (schemaFilter && sourceFilter) {
    pageTitle = `${sourceFilter}.${schemaFilter}`
  } else if (sourceFilter) {
    pageTitle = sourceFilter
  }

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 16 }} items={breadcrumbItems} />

      <Title level={2}>{pageTitle}</Title>

      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          placeholder="Filter by source"
          allowClear
          style={{ width: 200 }}
          value={sourceFilter}
          onChange={handleSourceChange}
          options={sources?.map((s) => ({ value: s.name, label: s.display_name || s.name }))}
        />
        <Select
          placeholder="Filter by schema"
          allowClear
          style={{ width: 200 }}
          value={schemaFilter}
          onChange={handleSchemaChange}
          options={schemas.map((s) => ({ value: s, label: s }))}
          disabled={!sourceFilter}
        />
        <Select
          placeholder="Filter by type"
          allowClear
          style={{ width: 200 }}
          value={typeFilter}
          onChange={handleTypeChange}
          options={objectTypes.map((t) => ({ value: t, label: t }))}
        />
      </Space>

      <ObjectTable
        objects={paginatedObjects}
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: pageSize,
          total: objects?.length || 0,
          onChange: handlePageChange,
        }}
      />
    </div>
  )
}
