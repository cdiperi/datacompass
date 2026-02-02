/**
 * Redirect component for legacy /objects/:id URLs.
 * Fetches the object by ID and redirects to the semantic URL.
 */

import { Navigate, useParams } from 'react-router-dom'
import { Spin, Alert } from 'antd'
import { useObject } from '../hooks/useObjects'
import { getObjectUrl } from '../utils/urls'

export function ObjectRedirect() {
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
        message="Error loading object"
        description={error.message}
      />
    )
  }

  if (object) {
    return <Navigate to={getObjectUrl(object)} replace />
  }

  return (
    <Alert
      type="warning"
      showIcon
      message="Object not found"
    />
  )
}
