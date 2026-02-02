import { useState } from 'react'
import { Tag, Input, Tooltip, theme } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

interface TagEditorProps {
  tags: string[]
  onAddTag: (tag: string) => void
  onRemoveTag: (tag: string) => void
  disabled?: boolean
}

export function TagEditor({ tags, onAddTag, onRemoveTag, disabled = false }: TagEditorProps) {
  const { token } = theme.useToken()
  const [inputVisible, setInputVisible] = useState(false)
  const [inputValue, setInputValue] = useState('')

  const handleClose = (removedTag: string) => {
    if (!disabled) {
      onRemoveTag(removedTag)
    }
  }

  const showInput = () => {
    setInputVisible(true)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value)
  }

  const handleInputConfirm = () => {
    const trimmedValue = inputValue.trim()
    if (trimmedValue && !tags.includes(trimmedValue)) {
      onAddTag(trimmedValue)
    }
    setInputVisible(false)
    setInputValue('')
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {tags.map((tag) => (
        <Tag
          key={tag}
          closable={!disabled}
          onClose={() => handleClose(tag)}
          color="blue"
        >
          {tag}
        </Tag>
      ))}
      {!disabled && (
        inputVisible ? (
          <Input
            type="text"
            size="small"
            style={{ width: 78 }}
            value={inputValue}
            onChange={handleInputChange}
            onBlur={handleInputConfirm}
            onPressEnter={handleInputConfirm}
            autoFocus
          />
        ) : (
          <Tooltip title="Add tag">
            <Tag
              onClick={showInput}
              style={{
                background: token.colorBgContainer,
                borderStyle: 'dashed',
                cursor: 'pointer',
              }}
            >
              <PlusOutlined /> New Tag
            </Tag>
          </Tooltip>
        )
      )}
    </div>
  )
}
