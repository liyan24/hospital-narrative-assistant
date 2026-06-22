import { useEffect, useState } from 'react'
import { Row, Col, Card, Table, Tag, Button, Select, Tabs, List, message } from 'antd'
import { useAuthStore } from '../../stores/auth.jsx'
import PatientSearch from '../../components/PatientSearch.jsx'
import PatientIdLink from '../../components/PatientIdLink.jsx'
import { getPatientQuality, getDailyBriefing, getConfig } from '../../api/index.js'
import dayjs from 'dayjs'

export default function QualityView() {
  const { user } = useAuthStore()
  const roles = user?.roles || []
  const roleCode = roles[0]?.role_code
  const canManage = roleCode === 'quality_controller' || roleCode === 'department_manager' || roleCode === 'admin'

  const [patientId, setPatientId] = useState('')
  const [issues, setIssues] = useState([])
  const [briefing, setBriefing] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadBriefing()
  }, [])

  const loadBriefing = async () => {
    try {
      let targetDate = dayjs()
      const cfg = await getConfig()
      if (cfg.simulation_date) {
        targetDate = dayjs(cfg.simulation_date)
      }
      const res = await getDailyBriefing(targetDate.format('YYYY-MM-DD'))
      setBriefing(res.briefing)
    } catch {}
  }

  const searchPatientIssues = async (pid = patientId) => {
    if (!pid) return
    setLoading(true)
    try {
      const res = await getPatientQuality(pid)
      const list = (res.issues || []).map((item, idx) => ({
        key: `${item.type || 'issue'}-${idx}`,
        type: item.type,
        description: item.description,
        level: item.level,
        status: item.status || 'pending',
        patient_id: pid,
        visit_id: item.visit_id,
        date: item.date,
      }))
      setIssues(list)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { title: '类型', dataIndex: 'type', render: (v) => <Tag color="orange">{v}</Tag> },
    { title: '描述', dataIndex: 'description' },
    { title: '患者ID', dataIndex: 'patient_id', render: (v) => v ? <PatientIdLink patientId={v} /> : '-' },
    { title: '状态', dataIndex: 'status', render: (v) => <Tag color={v === 'resolved' ? 'green' : 'orange'}>{v === 'resolved' ? '已整改' : '待整改'}</Tag> },
    {
      title: '操作',
      dataIndex: 'action',
      render: (_, record) => canManage ? (
        <Select
          value={record.status}
          style={{ width: 120 }}
          onChange={(value) => {
            const next = issues.map((i) => i.key === record.key ? { ...i, status: value } : i)
            setIssues(next)
            message.success('状态已更新')
          }}
          options={[
            { value: 'pending', label: '待整改' },
            { value: 'in_progress', label: '整改中' },
            { value: 'resolved', label: '已整改' },
          ]}
        />
      ) : '—',
    },
  ]

  const allIssues = (briefing?.quality_control_issues || []).map((item, idx) => ({ ...item, key: idx, patient_id: item.patient_id || '-' }))

  return (
    <div>
      <Card title="质控闭环管理" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col span={24} md={12}>
            <PatientSearch value={patientId} onChange={(val) => { setPatientId(val); if (val) searchPatientIssues(val) }} />
          </Col>
          <Col span={24} md={12}>
            <Button type="primary" onClick={searchPatientIssues} loading={loading}>查询患者质控问题</Button>
          </Col>
        </Row>
      </Card>

      <Tabs defaultActiveKey="all">
        <Tabs.TabPane tab="今日质控异常" key="all">
          <Table columns={columns} dataSource={allIssues} rowKey="key" size="small" />
        </Tabs.TabPane>
        <Tabs.TabPane tab="患者质控问题" key="patient">
          <Table columns={columns} dataSource={issues} rowKey="key" size="small" />
        </Tabs.TabPane>
        <Tabs.TabPane tab="整改追踪" key="tracking">
          <List
            size="small"
            dataSource={allIssues.filter((i) => i.status !== 'resolved')}
            renderItem={(item) => (
              <List.Item>
                <Tag color="orange">{item.type}</Tag>
                {item.description}
                {canManage && (
                  <Button size="small" type="link" onClick={() => message.success('已发送整改提醒')}>发送提醒</Button>
                )}
              </List.Item>
            )}
          />
        </Tabs.TabPane>
      </Tabs>
    </div>
  )
}
