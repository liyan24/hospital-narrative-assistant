import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Form, Input, Button, Divider, Tag, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useAuthStore } from '../../stores/auth.jsx'
import { login } from '../../api/index.js'

export default function LoginView() {
  const navigate = useNavigate()
  const authStore = useAuthStore()
  const [loading, setLoading] = useState(false)

  const onFinish = async (values) => {
    setLoading(true)
    try {
      const res = await login(values)
      const roles = res.user?.roles || []
      const isAdmin = roles.some((r) => r.role_code === 'admin')
      authStore.setAuth({
        token: res.access_token,
        user: {
          id: res.user.id,
          name: res.user.name,
          username: res.user.username,
          department: res.user.department,
          role: isAdmin ? 'admin' : 'doctor',
          roles,
          permissions: res.user.permissions,
        },
      })
      message.success('登录成功')
      navigate(isAdmin ? '/admin' : '/portal')
    } catch (e) {
      // request.js 已统一提示
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #1890ff 0%, #36cfc9 100%)',
    }}>
      <Card title="医院叙事生成助手" style={{ width: 400, borderRadius: 8 }}>
        <Form onFinish={onFinish}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={loading}>登录</Button>
          </Form.Item>
        </Form>
        <Divider>演示账号</Divider>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Tag color="blue">医生 doctor / doctor123</Tag>
          <Tag color="cyan">主治 attending / attending123</Tag>
          <Tag color="red">管理员 admin / admin123</Tag>
        </div>
      </Card>
    </div>
  )
}
