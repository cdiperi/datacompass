import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Typography, Input, Select, Space, List, Tag, Empty, Spin, Alert } from 'antd'
import { SearchOutlined, TableOutlined, DatabaseOutlined } from '@ant-design/icons'
import { useDebouncedSearch } from '../hooks/useSearch'
import { useSources } from '../hooks/useSources'
import type { SearchResult } from '../api/types'
import { getObjectUrl } from '../utils/urls'

const { Title, Text } = Typography

const objectTypes = ['TABLE', 'VIEW', 'MATERIALIZED_VIEW', 'FUNCTION']

const objectTypeColors: Record<string, string> = {
  TABLE: 'blue',
  VIEW: 'green',
  MATERIALIZED_VIEW: 'purple',
  FUNCTION: 'orange',
}

export function SearchResultsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const queryParam = searchParams.get('q') || ''
  const sourceFilter = searchParams.get('source') || undefined
  const typeFilter = searchParams.get('object_type') || undefined

  const [query, setQuery] = useState(queryParam)

  // Sync local query state with URL params
  useEffect(() => {
    setQuery(queryParam)
  }, [queryParam])

  const { data: sources } = useSources()
  const { data: results, isLoading, error } = useDebouncedSearch(query, {
    source: sourceFilter,
    object_type: typeFilter,
  })

  const handleQueryChange = (value: string) => {
    setQuery(value)
    const newParams = new URLSearchParams(searchParams)
    if (value) {
      newParams.set('q', value)
    } else {
      newParams.delete('q')
    }
    setSearchParams(newParams)
  }

  const handleFilterChange = (key: string, value: string | undefined) => {
    const newParams = new URLSearchParams(searchParams)
    if (value) {
      newParams.set(key, value)
    } else {
      newParams.delete(key)
    }
    setSearchParams(newParams)
  }

  const handleResultClick = (result: SearchResult) => {
    navigate(getObjectUrl(result))
  }

  const renderHighlight = (text: string, highlights: Record<string, string>, field: string) => {
    if (highlights[field]) {
      // The backend returns highlighted text with <mark> tags, render as HTML
      return <span dangerouslySetInnerHTML={{ __html: highlights[field] }} />
    }
    return text
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message={
          <>
            <strong>Search error</strong>
            <div>{error.message}</div>
          </>
        }
      />
    )
  }

  return (
    <div>
      <Title level={2}>Search Results</Title>

      <Space direction="vertical" style={{ width: '100%', marginBottom: 24 }}>
        <Input
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Search catalog..."
          prefix={<SearchOutlined />}
          size="large"
          allowClear
          style={{ maxWidth: 500 }}
        />
        <Space wrap>
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
        </Space>
      </Space>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : !query ? (
        <Empty
          description="Enter a search query"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : results && results.length > 0 ? (
        <>
          <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
            {results.length} result{results.length !== 1 ? 's' : ''} found
          </Text>
          <List
            itemLayout="horizontal"
            dataSource={results}
            renderItem={(result) => (
              <List.Item
                onClick={() => handleResultClick(result)}
                style={{ cursor: 'pointer' }}
              >
                <List.Item.Meta
                  avatar={<TableOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
                  title={
                    <Space>
                      <Text strong>
                        {renderHighlight(result.object_name, result.highlights, 'object_name')}
                      </Text>
                      <Tag color={objectTypeColors[result.object_type] || 'default'}>
                        {result.object_type}
                      </Tag>
                      {result.tags.map((tag) => (
                        <Tag key={tag} color="blue">{tag}</Tag>
                      ))}
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      <Text type="secondary">
                        <DatabaseOutlined style={{ marginRight: 4 }} />
                        {result.source_name}.{result.schema_name}
                      </Text>
                      {result.description && (
                        <Text>
                          {renderHighlight(result.description, result.highlights, 'description')}
                        </Text>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </>
      ) : (
        <Empty
          description="No results found"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
    </div>
  )
}
