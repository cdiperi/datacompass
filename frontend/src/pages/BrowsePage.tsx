import { useState, useMemo } from 'react'
import { Typography, Select, Space, Alert } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { useObjects } from '../hooks/useObjects'
import { useSources } from '../hooks/useSources'
import { ObjectTable } from '../components/ObjectTable'

const { Title } = Typography

const objectTypes = ['TABLE', 'VIEW', 'MATERIALIZED_VIEW', 'FUNCTION']

export function BrowsePage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Get filter values from URL params
  const sourceFilter = searchParams.get('source') || undefined
  const typeFilter = searchParams.get('object_type') || undefined
  const schemaFilter = searchParams.get('schema') || undefined

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

  const handleFilterChange = (key: string, value: string | undefined) => {
    const newParams = new URLSearchParams(searchParams)
    if (value) {
      newParams.set(key, value)
    } else {
      newParams.delete(key)
    }
    setSearchParams(newParams)
    setPage(1) // Reset to first page on filter change
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

  return (
    <div>
      <Title level={2}>Browse Catalog</Title>

      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          placeholder="Filter by source"
          allowClear
          style={{ width: 200 }}
          value={sourceFilter}
          onChange={(value) => handleFilterChange('source', value)}
          options={sources?.map((s) => ({ value: s.name, label: s.display_name || s.name }))}
        />
        <Select
          placeholder="Filter by type"
          allowClear
          style={{ width: 200 }}
          value={typeFilter}
          onChange={(value) => handleFilterChange('object_type', value)}
          options={objectTypes.map((t) => ({ value: t, label: t }))}
        />
        <Select
          placeholder="Filter by schema"
          allowClear
          style={{ width: 200 }}
          value={schemaFilter}
          onChange={(value) => handleFilterChange('schema', value)}
          options={schemas.map((s) => ({ value: s, label: s }))}
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
