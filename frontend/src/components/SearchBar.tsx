import { Input, type InputRef } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useState, useRef, type KeyboardEvent } from 'react'
import { SearchDropdown, type SearchDropdownHandle } from './SearchDropdown'
import { useDebouncedSearch } from '../hooks/useSearch'
import { getObjectUrl } from '../utils/urls'

interface SearchBarProps {
  defaultValue?: string
  placeholder?: string
  autoFocus?: boolean
  size?: 'large' | 'middle' | 'small'
  width?: number | string
}

export function SearchBar({
  defaultValue = '',
  placeholder = 'Search tables, views, columns...',
  autoFocus = false,
  size = 'middle',
  width = 300,
}: SearchBarProps) {
  const navigate = useNavigate()
  const [value, setValue] = useState(defaultValue)
  const [isDropdownVisible, setIsDropdownVisible] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const dropdownRef = useRef<SearchDropdownHandle>(null)
  const inputRef = useRef<InputRef>(null)

  const { data: results = [], isLoading, isFetching } = useDebouncedSearch(value, { limit: 10 }, 150)

  const handleSearch = () => {
    if (value.trim()) {
      setIsDropdownVisible(false)
      navigate(`/search?q=${encodeURIComponent(value.trim())}`)
    }
  }

  const handleSelectResult = (result: (typeof results)[0]) => {
    setIsDropdownVisible(false)
    setValue('')
    navigate(getObjectUrl(result))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!isDropdownVisible || results.length === 0) {
      if (e.key === 'Enter') {
        handleSearch()
      }
      return
    }

    const maxIndex = Math.min(results.length, 7) - 1

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex((prev) => {
          const next = prev < maxIndex ? prev + 1 : 0
          setTimeout(() => dropdownRef.current?.scrollToSelected(), 0)
          return next
        })
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex((prev) => {
          const next = prev > 0 ? prev - 1 : maxIndex
          setTimeout(() => dropdownRef.current?.scrollToSelected(), 0)
          return next
        })
        break
      case 'Enter':
        e.preventDefault()
        if (selectedIndex >= 0 && selectedIndex <= maxIndex) {
          handleSelectResult(results[selectedIndex])
        } else {
          handleSearch()
        }
        break
      case 'Escape':
        e.preventDefault()
        setIsDropdownVisible(false)
        setSelectedIndex(-1)
        break
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setValue(newValue)
    setSelectedIndex(-1)
    if (newValue.trim()) {
      setIsDropdownVisible(true)
    } else {
      setIsDropdownVisible(false)
    }
  }

  const handleFocus = () => {
    if (value.trim() && results.length > 0) {
      setIsDropdownVisible(true)
    }
  }

  const handleCloseDropdown = () => {
    setIsDropdownVisible(false)
    setSelectedIndex(-1)
  }

  return (
    <div style={{ position: 'relative', width }}>
      <Input
        ref={inputRef}
        value={value}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onFocus={handleFocus}
        placeholder={placeholder}
        prefix={<SearchOutlined />}
        allowClear
        size={size}
        autoFocus={autoFocus}
        style={{ width: '100%' }}
      />
      <SearchDropdown
        ref={dropdownRef}
        results={results}
        isLoading={isLoading || isFetching}
        isVisible={isDropdownVisible && value.trim().length > 0}
        selectedIndex={selectedIndex}
        onSelectResult={handleSelectResult}
        onClose={handleCloseDropdown}
      />
    </div>
  )
}
