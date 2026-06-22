import { useEffect, useState } from 'react'
import { Row, Col, Card, DatePicker, Button, Table, List, Tag, Skeleton, Statistic, message, Badge, Empty } from 'antd'
import dayjs from 'dayjs'
import { useAuthStore } from '../../stores/auth.jsx'
import { getDailyBriefing, generateDailyBriefing, getDepartmentOperation, getConfig } from '../../api/index.js'
import PatientIdLink from '../../components/PatientIdLink.jsx'

export default function BriefingView() {
  const { user } = useAuthStore()
  const roles = user?.roles || []
  const roleCode = roles[0]?.role_code || 'attending_doctor'

  const [date, setDate] = useState(dayjs())
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [briefing, setBriefing] = useState(null)
  const [deptLoading, setDeptLoading] = useState(false)
  const [deptOp, setDeptOp] = useState(null)

  const stats = [
    { title: '新入院', value: briefing?.overview?.admissions || 0 },
    { title: '在院患者', value: briefing?.overview?.inpatients || 0 },
    { title: '今日手术', value: briefing?.overview?.surgeries || 0 },
    { title: '重点患者', value: briefing?.overview?.focus_patients || 0 },
  ]

  const focusColumns = [
    { title: '患者ID', dataIndex: 'patient_id', render: (v) => <PatientIdLink patientId={v} /> },
    { title: '姓名', dataIndex: 'name' },
    { title: '诊断', dataIndex: 'diagnosis' },
    { title: '关注原因', dataIndex: 'reason' },
  ]

  const admissionColumns = [
    { title: '患者ID', dataIndex: 'patient_id', render: (v) => <PatientIdLink patientId={v} /> },
    { title: '姓名', dataIndex: 'name' },
    { title: '入院时间', dataIndex: 'admission_date' },
    { title: '主诉', dataIndex: 'chief_complaint' },
  ]

  const surgeryColumns = [
    { title: '患者ID', dataIndex: 'patient_id', render: (v) => <PatientIdLink patientId={v} /> },
    { title: '姓名', dataIndex: 'name' },
    { title: '手术名称', dataIndex: 'surgery_name' },
    { title: '麻醉方式', dataIndex: 'anesthesia_method' },
  ]

  const loadBriefing = async (targetDate = date) => {
    setLoading(true)
    try {
      const res = await getDailyBriefing(targetDate.format('YYYY-MM-DD'))
      setBriefing(res.briefing)
    } finally {
      setLoading(false)
    }
  }

  const loadDept = async () => {
    setDeptLoading(true)
    try {
      const res = await getDepartmentOperation({ period: 'latest_year', compare: true })
      setDeptOp(res)
    } finally {
      setDeptLoading(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await generateDailyBriefing(date.format('YYYY-MM-DD'))
      message.success('生成完成')
      await loadBriefing()
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    const init = async () => {
      let targetDate = dayjs()
      try {
        const cfg = await getConfig()
        if (cfg.simulation_date) {
          targetDate = dayjs(cfg.simulation_date)
        }
      } catch {
        // ignore
      }
      setDate(targetDate)
      await loadBriefing(targetDate)
      if (roleCode === 'department_manager' || roleCode === 'hospital_manager') {
        loadDept()
      }
    }
    init()
  }, [])

  const renderDoctorView = () => (
    <>
      {stats.map((stat) => (
        <Col span={24} lg={6} key={stat.title}>
          <Card><Statistic title={stat.title} value={stat.value} /></Card>
        </Col>
      ))}
      <Col span={24}>
        <Card title="今日重点患者">
          <Table columns={focusColumns} dataSource={briefing?.focus_patients || []} rowKey="patient_id" size="small" />
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="新入院患者">
          <Table columns={admissionColumns} dataSource={briefing?.new_admissions || []} rowKey="patient_id" size="small" />
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="今日手术安排">
          <Table columns={surgeryColumns} dataSource={briefing?.surgeries || []} rowKey="patient_id" size="small" />
        </Card>
      </Col>
      <Col span={24}>
        <Card title="质控问题">
          <List
            size="small"
            dataSource={briefing?.quality_issues || []}
            renderItem={(item) => (
              <List.Item>
                <Tag color="orange">{item.type}</Tag>
                {item.description}
                {item.doctor && <Tag style={{ marginLeft: 8 }}>{item.doctor}</Tag>}
              </List.Item>
            )}
          />
        </Card>
      </Col>
    </>
  )

  const renderManagerView = () => (
    <>
      <Col span={24}>
        <Card title="科室运营概览">
          <Row gutter={16}>
            {stats.map((stat) => (
              <Col span={24} lg={6} key={stat.title}>
                <Statistic title={stat.title} value={stat.value} />
              </Col>
            ))}
          </Row>
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="本周重点关注患者">
          <Table columns={focusColumns} dataSource={briefing?.focus_patients || []} rowKey="patient_id" size="small" />
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="科室运营趋势" loading={deptLoading}>
          {deptOp ? (
            <>
              <p><strong>当前周期：</strong>{deptOp.current_period?.start} ~ {deptOp.current_period?.end}</p>
              <p><strong>关键变化：</strong></p>
              <List
                size="small"
                dataSource={Object.entries(deptOp.changes || {}).slice(0, 6)}
                renderItem={([k, v]) => (
                  <List.Item>
                    <Tag color={String(v).includes('升') || String(v).includes('增加') ? 'red' : 'green'}>{k}</Tag>
                    {v}
                  </List.Item>
                )}
              />
            </>
          ) : <Empty />}
        </Card>
      </Col>
      <Col span={24}>
        <Card title="质控异常清单">
          <Table
            columns={[
              { title: '类型', dataIndex: 'type' },
              { title: '描述', dataIndex: 'description' },
              { title: '状态', dataIndex: 'status', render: (v) => <Tag color={v === 'resolved' ? 'green' : 'orange'}>{v || '待整改'}</Tag> },
              { title: '责任医生', dataIndex: 'doctor' },
            ]}
            dataSource={briefing?.quality_issues || []}
            rowKey={(r, idx) => idx}
            size="small"
          />
        </Card>
      </Col>
    </>
  )

  const renderHospitalView = () => (
    <>
      <Col span={24}>
        <Card title="全院概览">
          <Row gutter={16}>
            {stats.map((stat) => (
              <Col span={24} lg={6} key={stat.title}>
                <Statistic title={stat.title} value={stat.value} />
              </Col>
            ))}
          </Row>
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="风险患者清单">
          <Table columns={focusColumns} dataSource={briefing?.focus_patients || []} rowKey="patient_id" size="small" />
        </Card>
      </Col>
      <Col span={24} md={12}>
        <Card title="关键质量指标" loading={deptLoading}>
          {deptOp ? (
            <List
              size="small"
              dataSource={Object.entries(deptOp.current_metrics || {}).slice(0, 8)}
              renderItem={([k, v]) => (
                <List.Item>
                  <Tag color="blue">{k}</Tag>
                  {v}
                </List.Item>
              )}
            />
          ) : <Empty />}
        </Card>
      </Col>
      <Col span={24}>
        <Card title="各科室风险概览">
          <List
            size="small"
            dataSource={briefing?.quality_issues || []}
            renderItem={(item) => (
              <List.Item>
                <Badge status="warning" />
                {item.type}：{item.description}
              </List.Item>
            )}
          />
        </Card>
      </Col>
    </>
  )

  const renderQualityView = () => (
    <>
      <Col span={24}>
        <Card title="质控异常概览">
          <Row gutter={16}>
            <Col span={8}><Statistic title="异常事件" value={(briefing?.quality_issues || []).length} /></Col>
            <Col span={8}><Statistic title="重点患者" value={stats.find((s) => s.title === '重点患者')?.value} /></Col>
            <Col span={8}><Statistic title="待整改" value={(briefing?.quality_issues || []).filter((q) => q.status === 'pending').length} /></Col>
          </Row>
        </Card>
      </Col>
      <Col span={24}>
        <Card title="异常事件清单">
          <Table
            columns={[
              { title: '类型', dataIndex: 'type' },
              { title: '描述', dataIndex: 'description' },
              { title: '状态', dataIndex: 'status', render: (v) => <Tag color={v === 'resolved' ? 'green' : 'orange'}>{v || '待整改'}</Tag> },
              { title: '责任医生', dataIndex: 'doctor' },
            ]}
            dataSource={briefing?.quality_issues || []}
            rowKey={(r, idx) => idx}
            size="small"
          />
        </Card>
      </Col>
      <Col span={24}>
        <Card title="整改追踪">
          <List
            size="small"
            dataSource={(briefing?.quality_issues || []).filter((q) => q.status === 'pending')}
            renderItem={(item) => (
              <List.Item>
                <Tag color="red">待整改</Tag>
                {item.description} — 责任医生：{item.doctor || '-'}
              </List.Item>
            )}
          />
        </Card>
      </Col>
    </>
  )

  const renderContent = () => {
    switch (roleCode) {
      case 'hospital_manager': return renderHospitalView()
      case 'department_manager': return renderManagerView()
      case 'quality_controller': return renderQualityView()
      case 'attending_doctor':
      case 'resident_doctor':
      case 'viewer':
      case 'doctor':
      default: return renderDoctorView()
    }
  }

  const roleName = roleCode === 'hospital_manager' ? '院领导' : roleCode === 'department_manager' ? '科主任' : roleCode === 'quality_controller' ? '质控员' : '医生'

  return (
    <div>
      <Card title="科室晨会简报" style={{ marginBottom: 16 }}>
        <DatePicker value={date} onChange={(d) => setDate(d)} />
        <Button type="primary" onClick={() => loadBriefing()} loading={loading} style={{ marginLeft: 8 }}>刷新简报</Button>
        <Button onClick={handleGenerate} loading={generating} style={{ marginLeft: 8 }}>重新生成</Button>
        <Tag color="blue" style={{ marginLeft: 16 }}>当前视图：{roleName}</Tag>
      </Card>
      {loading && <Skeleton active />}
      {!loading && briefing && (
        <Row gutter={[16, 16]}>
          {renderContent()}
        </Row>
      )}
    </div>
  )
}
