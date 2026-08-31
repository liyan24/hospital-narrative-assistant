import { useMemo } from 'react'
import { Layout, Menu, Button, Dropdown, Space, Badge, Tag } from 'antd'
import { UserOutlined, MedicineBoxOutlined, TeamOutlined, FileSearchOutlined, ExperimentOutlined, BarChartOutlined, SafetyOutlined } from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth.jsx'

const { Header, Content } = Layout

export default function PortalLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const authStore = useAuthStore()
  const roles = authStore.user?.roles || []
  const roleCode = authStore.roleCode || roles[0]?.role_code || 'attending_doctor'
  const permissions = authStore.user?.permissions || []
  const features = authStore.features || {}

  const has = (code) => permissions.includes(code)

  const menuItems = useMemo(() => {
    const items = []
    items.push({ key: '/portal', icon: <MedicineBoxOutlined />, label: '工作台' })

    if (features.patient_holographic !== false) {
      items.push({ key: '/portal/patient-search', icon: <FileSearchOutlined />, label: '患者全息视图' })
    }
    if (features.ward_round !== false) {
      items.push({ key: '/portal/ward-round', icon: <TeamOutlined />, label: '查房助手' })
    }
    if (features.daily_briefing !== false) {
      items.push({ key: '/portal/briefing', icon: <BarChartOutlined />, label: '科室晨会简报' })
    }
    if ((has('quality:view') || has('quality:manage')) && features.quality_control !== false) {
      items.push({ key: '/portal/quality', icon: <SafetyOutlined />, label: '质控闭环管理' })
    }
    if ((has('similar:view') || has('pathway:view')) && features.similar_patient !== false) {
      items.push({ key: '/portal/similar-patient', icon: <MedicineBoxOutlined />, label: '相似患者 / 诊疗路径' })
    }
    if (has('research:view') && features.research_export !== false) {
      items.push({ key: '/portal/research', icon: <ExperimentOutlined />, label: '科研队列' })
      items.push({ key: '/portal/research-assistant', icon: <ExperimentOutlined />, label: '科研助手' })
    }
    return items
  }, [permissions, features])

  const roleNameMap = {
    admin: '系统管理员',
    hospital_manager: '医务部/院领导',
    department_manager: '科室主任',
    quality_controller: '质控员',
    attending_doctor: '主治医师',
    resident_doctor: '住院医师',
    researcher: '科研人员',
    viewer: '只读用户',
    doctor: '医生',
  }

  const userMenuItems = [
    { key: 'profile', label: `角色：${roleNameMap[roleCode] || roleCode}` },
    { key: 'logout', label: '退出登录', onClick: () => { authStore.logout(); navigate('/login') } },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', background: '#001529', padding: '0 24px' }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginRight: 40, whiteSpace: 'nowrap' }}>
          医院叙事生成助手
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={(e) => navigate(e.key)}
          style={{ flex: 1, background: 'transparent' }}
        />
        <Space>
          {authStore.isAdmin && (
            <Button type="link" ghost onClick={() => navigate('/admin')}>后台管理</Button>
          )}
          <Dropdown menu={{ items: userMenuItems }}>
            <Button type="link" ghost><UserOutlined /> {authStore.user?.name || '医生'}</Button>
          </Dropdown>
        </Space>
      </Header>
      <Content style={{ padding: 20, background: '#f0f2f5' }}>
        <Outlet />
      </Content>
    </Layout>
  )
}
