import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react'
import { Typography, Spin, Empty, theme } from 'antd'
import { TableOutlined, EyeOutlined, EnterOutlined } from '@ant-design/icons'
import type { SearchResult } from '../api/types'

const { Text } = Typography
const { useToken } = theme

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
    const { token } = useToken()
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
          background: token.colorBgElevated,
          borderRadius: 8,
          boxShadow: token.boxShadowSecondary,
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
                  background: index === selectedIndex ? token.colorBgTextHover : 'transparent',
                  borderBottom: index < Math.min(results.length, 7) - 1 ? `1px solid ${token.colorBorderSecondary}` : 'none',
                  transition: 'background 0.15s ease',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                }}
                onMouseEnter={(e) => {
                  if (index !== selectedIndex) {
                    e.currentTarget.style.background = token.colorBgTextHover
                  }
                }}
                onMouseLeave={(e) => {
                  if (index !== selectedIndex) {
                    e.currentTarget.style.background = 'transparent'
                  }
                }}
              >
                <span style={{ fontSize: 16, lineHeight: '20px', flexShrink: 0 }}>
                  {getObjectIcon(result.object_type)}
                </span>
                <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'nowrap' }}>
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
                        flexShrink: 0,
                      }}
                    >
                      {result.object_type}
                    </Text>
                  </div>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
                    {result.source_name}.{result.schema_name}
                  </Text>
                  {result.description && (
                    <Text
                      type="secondary"
                      style={{
                        fontSize: 12,
                        display: 'block',
                        marginTop: 2,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={result.description}
                    >
                      {result.description}
                    </Text>
                  )}
                </div>
              </div>
            ))}
            {/* Footer hint */}
            <div
              style={{
                padding: '8px 16px',
                background: token.colorFillTertiary,
                borderTop: `1px solid ${token.colorBorderSecondary}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 8,
              }}
            >
              <Text type="secondary" style={{ fontSize: 12 }}>
                Press Enter to see all results
              </Text>
              <EnterOutlined style={{ fontSize: 12, color: token.colorTextSecondary }} />
            </div>
          </>
        )}
      </div>
    )
  }
)

