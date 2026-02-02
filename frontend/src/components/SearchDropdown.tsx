import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react'
import { Typography, Spin, Empty } from 'antd'
import { TableOutlined, EyeOutlined, EnterOutlined } from '@ant-design/icons'
import type { SearchResult } from '../api/types'

const { Text } = Typography

interface SearchDropdownProps {
  results: SearchResult[]
  isLoading: boolean
  isVisible: boolean
  selectedIndex: number
  onSelectResult: (result: SearchResult) => void
  onClose: () => void
}

export interface SearchDropdownHandle {
  scrollToSelected: () => void
}

function getObjectIcon(objectType: string) {
  switch (objectType.toUpperCase()) {
    case 'VIEW':
      return <EyeOutlined style={{ color: '#722ed1' }} />
    case 'TABLE':
    default:
      return <TableOutlined style={{ color: '#1677ff' }} />
  }
}

function getTypeColor(objectType: string) {
  switch (objectType.toUpperCase()) {
    case 'VIEW':
      return '#722ed1'
    case 'TABLE':
    default:
      return '#1677ff'
  }
}

export const SearchDropdown = forwardRef<SearchDropdownHandle, SearchDropdownProps>(
  function SearchDropdown(
    { results, isLoading, isVisible, selectedIndex, onSelectResult, onClose },
    ref
  ) {
    const containerRef = useRef<HTMLDivElement>(null)
    const itemRefs = useRef<(HTMLDivElement | null)[]>([])

    useImperativeHandle(ref, () => ({
      scrollToSelected: () => {
        const selectedItem = itemRefs.current[selectedIndex]
        if (selectedItem && containerRef.current) {
          selectedItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        }
      },
    }))

    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
          onClose()
        }
      }

      if (isVisible) {
        document.addEventListener('mousedown', handleClickOutside)
      }

      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }, [isVisible, onClose])

    if (!isVisible) {
      return null
    }

    return (
      <div
        ref={containerRef}
        style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          marginTop: 4,
          background: '#fff',
          borderRadius: 8,
          boxShadow: '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
          overflow: 'hidden',
          zIndex: 1000,
          maxHeight: 400,
          overflowY: 'auto',
        }}
      >
        {isLoading ? (
          <div style={{ padding: 24, textAlign: 'center' }}>
            <Spin size="small" />
          </div>
        ) : results.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No results found"
            style={{ padding: '16px 0' }}
          />
        ) : (
          <>
            {results.slice(0, 7).map((result, index) => (
              <div
                key={result.id}
                ref={(el) => { itemRefs.current[index] = el }}
                onClick={() => onSelectResult(result)}
                style={{
                  padding: '10px 16px',
                  cursor: 'pointer',
                  background: index === selectedIndex ? '#f5f5f5' : 'transparent',
                  borderBottom: index < Math.min(results.length, 7) - 1 ? '1px solid #f0f0f0' : 'none',
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (index !== selectedIndex) {
                    e.currentTarget.style.background = '#fafafa'
                  }
                }}
                onMouseLeave={(e) => {
                  if (index !== selectedIndex) {
                    e.currentTarget.style.background = 'transparent'
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 16 }}>{getObjectIcon(result.object_type)}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Text strong style={{ fontSize: 14 }}>
                        {result.object_name}
                      </Text>
                      <Text
                        style={{
                          fontSize: 11,
                          padding: '1px 6px',
                          borderRadius: 4,
                          background: `${getTypeColor(result.object_type)}15`,
                          color: getTypeColor(result.object_type),
                          fontWeight: 500,
                        }}
                      >
                        {result.object_type}
                      </Text>
                    </div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {result.source_name}.{result.schema_name}
                    </Text>
                    {result.description && (
                      <div style={{ marginTop: 2 }}>
                        <Text
                          type="secondary"
                          style={{ fontSize: 12 }}
                          ellipsis={{ tooltip: result.description }}
                        >
                          {result.description.length > 80
                            ? `${result.description.slice(0, 80)}...`
                            : result.description}
                        </Text>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {/* Footer hint */}
            <div
              style={{
                padding: '8px 16px',
                background: '#fafafa',
                borderTop: '1px solid #f0f0f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 8,
              }}
            >
              <Text type="secondary" style={{ fontSize: 12 }}>
                Press Enter to see all results
              </Text>
              <EnterOutlined style={{ fontSize: 12, color: '#8c8c8c' }} />
            </div>
          </>
        )}
      </div>
    )
  }
)

