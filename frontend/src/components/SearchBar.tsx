import { Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useState, type KeyboardEvent } from 'react'

interface SearchBarProps {
  defaultValue?: string
  placeholder?: string
}

export function SearchBar({ defaultValue = '', placeholder = 'Search catalog...' }: SearchBarProps) {
  const navigate = useNavigate()
  const [value, setValue] = useState(defaultValue)

  const handleSearch = () => {
    if (value.trim()) {
      navigate(`/search?q=${encodeURIComponent(value.trim())}`)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  return (
    <Input
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      prefix={<SearchOutlined />}
      allowClear
      style={{ width: 300 }}
    />
  )
}
