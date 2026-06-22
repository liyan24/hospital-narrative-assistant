import { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, List, Tag, Button, Empty, Spin, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/auth.jsx'
import { getDailyBriefing, getKgStats, getDepartmentOperation, getConfig } from '../../api/index.js'
import PatientIdLink from '../../components/PatientIdLink.jsx'
import dayjs from 'dayjs'

export default function DashboardView() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const role = user?.role || 'attending_doctor'
  const roles = user?.roles || []
  const roleCode = roles[0]?.role_code || role

  const [loading, setLoading] = useState(true)
  const [briefing, setBriefing] = useState(null)
  const [kgStats, setKgStats] = useState(null)
  const [deptOp, setDeptOp] = useState(null)
  const [simDate, setSimDate] = useState(dayjs().format('YYYY-MM-DD'))

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      let targetDate = dayjs()
      try {
        const cfg = await getConfig()
        if (cfg.simulation_date) {
          targetDate = dayjs(cfg.simulation_date)
          setSimDate(targetDate.format('YYYY-MM-DD'))
        }
      } catch {
        // ignore
      }

      const managerRoles = ['department_manager', 'hospital_manager']
      const needDeptOp = managerRoles.includes(roleCode)

      const promises = [
        getDailyBriefing(targetDate.format('YYYY-MM-DD')).catch(() => null),
        getKgStats().catch(() => null),
      ]
      if (needDeptOp) {
        promises.push(getDepartmentOperation({ period: 'latest_year', compare: true }).catch(() => null))
      }
      const [b, kg, dept] = await Promise.all(promises)
      setBriefing(b?.briefing)
      setKgStats(kg)
      setDeptOp(dept)
    } catch (e) {
      message.error('加载工作台失败')
    } finally {
      setLoading(false)
    }
  }

  const stats = {
    admissions: briefing?.overview?.admissions || 0,
    inpatients: briefing?.overview?.inpatients || 0,
    surgeries: briefing?.overview?.surgeries || 0,
    focus: briefing?.overview?.focus_patients || 0,
  }

  const focusPatients = briefing?.focus_patients || []
  const qualityIssues = briefing?.quality_issues || []

  const renderDoctorDashboard = () => (
    <>
      <Col span={24}>
        <Card title={`欢迎，${user?.name || '医生'}`}>
          <p>当前模拟日期：<Tag color="blue">{simDate}</Tag>，今日待关注患者 {stats.focus} 人，新入院 {stats.admissions} 人。</p>
          <Button type="primary" onClick={() => navigate('/portal/ward-round')}>进入查房助手</Button>
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="重点关注患者">
          <List
            size="small"
            dataSource={focusPatients.slice(0, 5)}
            renderItem={(item) => (
              <List.Item>
                <Tag color="red">重点</Tag>
                <PatientIdLink patientId={item.patient_id} showIcon={false} />
                {item.name || ''} — {item.reason}
              </List.Item>
            )}
          />
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="今日快捷入口">
          <Button type="link" onClick={() => navigate('/portal/patient-search')}>患者全息视图</Button>
          <Button type="link" onClick={() => navigate('/portal/ward-round')}>查房助手</Button>
          <Button type="link" onClick={() => navigate('/portal/briefing')}>晨会简报</Button>
          <Button type="link" onClick={() => navigate('/portal/quality')}>质控问题</Button>
        </Card>
      </Col>
    </>
  )

  const renderManagerDashboard = () => (
    <>
      <Col span={24}>
        <Card title={`${user?.name || '主任'}，科室概览`}>
          <p>当前模拟日期：<Tag color="blue">{simDate}</Tag></p>
          <Row gutter={16}>
            <Col span={6}><Statistic title="新入院" value={stats.admissions} /></Col>
            <Col span={6}><Statistic title="在院" value={stats.inpatients} /></Col>
            <Col span={6}><Statistic title="手术" value={stats.surgeries} /></Col>
            <Col span={6}><Statistic title="重点患者" value={stats.focus} /></Col>
          </Row>
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="质控异常">
          <List
            size="small"
            dataSource={qualityIssues.slice(0, 5)}
            renderItem={(item) => (
              <List.Item>
                <Tag color="orange">{item.type}</Tag>
                {item.description}
              </List.Item>
            )}
          />
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="科室运营趋势">
          {deptOp ? (
            <>
              <p><strong>周期：</strong>{deptOp.period}</p>
              <p><strong>重点变化：</strong>{Object.entries(deptOp.changes || {}).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join('；')}</p>
            </>
          ) : <Empty />}
        </Card>
      </Col>
    </>
  )

  const renderHospitalDashboard = () => (
    <>
      <Col span={24}>
        <Card title={`${user?.name || '院领导'}，全院概览`}>
          <p>当前模拟日期：<Tag color="blue">{simDate}</Tag></p>
          <Row gutter={16}>
            <Col span={6}><Statistic title="知识图谱节点" value={kgStats?.node_count || 0} /></Col>
            <Col span={6}><Statistic title="关系" value={kgStats?.relationship_count || 0} /></Col>
            <Col span={6}><Statistic title="在院患者" value={stats.inpatients} /></Col>
            <Col span={6}><Statistic title="重点患者" value={stats.focus} /></Col>
          </Row>
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="科室风险预警">
          <List
            size="small"
            dataSource={focusPatients.slice(0, 5)}
            renderItem={(item) => (
              <List.Item>
                <Tag color="red">风险</Tag>
                <PatientIdLink patientId={item.patient_id} showIcon={false} />
                {item.name || ''} — {item.reason}
              </List.Item>
            )}
          />
        </Card>
      </Col>
    </>
  )

  const renderQualityDashboard = () => (
    <>
      <Col span={24}>
        <Card title={`${user?.name || '质控员'}，今日质控概览`}>
          <p>当前模拟日期：<Tag color="blue">{simDate}</Tag></p>
          <Row gutter={16}>
            <Col span={8}><Statistic title="质控问题" value={qualityIssues.length} /></Col>
            <Col span={8}><Statistic title="重点患者" value={stats.focus} /></Col>
            <Col span={8}><Statistic title="待整改" value={qualityIssues.filter((q) => q.status === 'pending').length} /></Col>
          </Row>
          <Button type="primary" style={{ marginTop: 16 }} onClick={() => navigate('/portal/quality')}>进入质控管理</Button>
        </Card>
      </Col>
      <Col span={24}>
        <Card title="异常事件清单">
          <List
            size="small"
            dataSource={qualityIssues.slice(0, 10)}
            renderItem={(item) => (
              <List.Item>
                <Tag color="orange">{item.type}</Tag>
                {item.description}
              </List.Item>
            )}
          />
        </Card>
      </Col>
    </>
  )

  const renderResearcherDashboard = () => (
    <>
      <Col span={24}>
        <Card title={`${user?.name || '科研人员'}，科研工作台`}>
          <Row gutter={16}>
            <Col span={8}><Statistic title="患者总数" value={kgStats?.node_count || 0} /></Col>
            <Col span={8}><Statistic title="就诊记录" value={stats.inpatients} /></Col>
            <Col span={8}><Statistic title="药品/检查关系" value={kgStats?.relationship_count || 0} /></Col>
          </Row>
          <Button type="primary" style={{ marginTop: 16 }} onClick={() => navigate('/portal/research')}>进入科研队列</Button>
        </Card>
      </Col>
    </>
  )

  const renderAdminDashboard = () => (
    <>
      <Col span={24}>
        <Card title={`${user?.name || '管理员'}，系统概览`}>
          <Row gutter={16}>
            <Col span={8}><Statistic title="知识图谱节点" value={kgStats?.node_count || 0} /></Col>
            <Col span={8}><Statistic title="关系" value={kgStats?.relationship_count || 0} /></Col>
            <Col span={8}><Statistic title="在院患者" value={stats.inpatients} /></Col>
          </Row>
          <Button type="primary" style={{ marginTop: 16 }} onClick={() => navigate('/admin')}>进入后台管理</Button>
        </Card>
      </Col>
    </>
  )

  const renderContent = () => {
    switch (roleCode) {
      case 'hospital_manager': return renderHospitalDashboard()
      case 'department_manager': return renderManagerDashboard()
      case 'quality_controller': return renderQualityDashboard()
      case 'researcher': return renderResearcherDashboard()
      case 'admin': return renderAdminDashboard()
      case 'attending_doctor':
      case 'resident_doctor':
      case 'viewer':
      case 'doctor':
      default: return renderDoctorDashboard()
    }
  }

  return (
    <Spin spinning={loading} tip="加载工作台数据中...">
      <Row gutter={[16, 16]}>
        {renderContent()}
      </Row>
    </Spin>
  )
}
