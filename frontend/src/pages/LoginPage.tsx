import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Form, Input, Button, Card, Alert, Typography } from 'antd'
import { LockOutlined, MailOutlined } from '@ant-design/icons'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../api/client'

const { Title, Text } = Typography

interface LocationState {
  from?: { pathname: string }
}

interface LoginFormValues {
  email: string
  password: string
}

export function LoginPage() {
  const [form] = Form.useForm<LoginFormValues>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const from = (location.state as LocationState)?.from?.pathname || '/'

  const handleSubmit = async (values: LoginFormValues) => {
    setLoading(true)
    setError(null)

    try {
      await login(values.email, values.password)
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError('Invalid email or password')
        } else if (err.status === 400) {
          const body = err.body as { detail?: string }
          setError(body?.detail || 'Login failed')
        } else {
          setError(`Login failed: ${err.message}`)
        }
      } else {
        setError('An unexpected error occurred')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: '#f0f2f5',
      }}
    >
      <Card
        style={{
          width: 400,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={2} style={{ marginBottom: 8 }}>
            Data Compass
          </Title>
          <Text type="secondary">Sign in to your account</Text>
        </div>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            style={{ marginBottom: 24 }}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
        >
          <Form.Item
            name="email"
            rules={[
              { required: true, message: 'Please enter your email' },
              { type: 'email', message: 'Please enter a valid email' },
            ]}
          >
            <Input
              prefix={<MailOutlined />}
              placeholder="Email"
              size="large"
              autoFocus
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Please enter your password' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Password"
              size="large"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
            >
              Sign In
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center' }}>
          <Button type="link" disabled style={{ color: '#999' }}>
            Sign in with SSO (Coming Soon)
          </Button>
        </div>
      </Card>
    </div>
  )
}
