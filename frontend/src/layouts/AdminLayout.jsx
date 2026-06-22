import { useState } from 'react'
import { Layout, Menu, Button } from 'antd'
import {
  DashboardOutlined,
  TeamOutlined,
  ControlOutlined,
  SettingOutlined,
  DatabaseOutlined,
  RollbackOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth.jsx'

const { Sider, Header, Content } = Layout

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const authStore = useAuthStore()

  const menuItems = [
    { key: '/admin', icon: <DashboardOutlined />, label: '概览' },
    { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
    { key: '/admin/roles', icon: <SafetyCertificateOutlined />, label: '角色权限' },
    { key: '/admin/features', icon: <ControlOutlined />, label: '功能开关' },
    { key: '/admin/config', icon: <SettingOutlined />, label: '系统配置' },
    { key: '/admin/cache', icon: <DatabaseOutlined />, label: '缓存管理' },
    { key: '/portal', icon: <RollbackOutlined />, label: '返回前台' },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 64, lineHeight: '64px', color: '#fff', fontSize: 18, fontWeight: 600, textAlign: 'center', background: '#002140' }}>
          {collapsed ? '管' : '后台管理'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={(e) => navigate(e.key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', boxShadow: '0 1px 4px rgba(0,0,0,0.1)' }}>
          <span>系统管理后台</span>
          <Button type="link" onClick={() => { authStore.logout(); navigate('/login') }}>退出登录</Button>
        </Header>
        <Content style={{ margin: 16, padding: 20, background: '#fff', minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
