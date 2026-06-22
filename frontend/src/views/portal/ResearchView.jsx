import { useEffect, useState } from 'react'
import { Row, Col, Card, Button, Table, Input, Select, Statistic, message } from 'antd'
import { getPatients } from '../../api/index.js'
import PatientIdLink from '../../components/PatientIdLink.jsx'

export default function ResearchView() {
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState({ keyword: '', ageMin: '', ageMax: '', gender: '' })
  const [selectedRows, setSelectedRows] = useState([])

  useEffect(() => {
    loadPatients()
  }, [])

  const loadPatients = async () => {
    setLoading(true)
    try {
      const res = await getPatients({ limit: 50, offset: 0 })
      setPatients(res.patients || [])
    } finally {
      setLoading(false)
    }
  }

  const filtered = patients.filter((p) => {
    if (filters.keyword && !p.patient_id?.includes(filters.keyword) && !p.medical_record_no?.includes(filters.keyword)) return false
    if (filters.ageMin && (p.age || 0) < Number(filters.ageMin)) return false
    if (filters.ageMax && (p.age || 0) > Number(filters.ageMax)) return false
    if (filters.gender && p.gender !== filters.gender) return false
    return true
  })

  const columns = [
    { title: '患者ID', dataIndex: 'patient_id', render: (v) => <PatientIdLink patientId={v} /> },
    { title: '病案号', dataIndex: 'medical_record_no' },
    { title: '年龄', dataIndex: 'age' },
    { title: '性别', dataIndex: 'gender' },
    { title: '婚姻', dataIndex: 'marriage' },
    { title: '职业', dataIndex: 'occupation' },
  ]

  const exportData = () => {
    const data = selectedRows.length > 0 ? selectedRows : filtered
    const csv = [
      columns.map((c) => c.title).join(','),
      ...data.map((row) => columns.map((c) => `"${row[c.dataIndex] || ''}"`).join(',')),
    ].join('\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `patient_cohort_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    message.success(`已导出 ${data.length} 条记录`)
  }

  return (
    <div>
      <Card title="科研队列筛选" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col span={24} md={6}>
            <Input placeholder="患者ID / 病案号" value={filters.keyword} onChange={(e) => setFilters({ ...filters, keyword: e.target.value })} />
          </Col>
          <Col span={24} md={4}>
            <Input placeholder="最小年龄" value={filters.ageMin} onChange={(e) => setFilters({ ...filters, ageMin: e.target.value })} />
          </Col>
          <Col span={24} md={4}>
            <Input placeholder="最大年龄" value={filters.ageMax} onChange={(e) => setFilters({ ...filters, ageMax: e.target.value })} />
          </Col>
          <Col span={24} md={4}>
            <Select
              placeholder="性别"
              allowClear
              style={{ width: '100%' }}
              value={filters.gender}
              onChange={(v) => setFilters({ ...filters, gender: v })}
              options={[{ value: '男', label: '男' }, { value: '女', label: '女' }]}
            />
          </Col>
          <Col span={24} md={6}>
            <Button type="primary" onClick={exportData}>导出选中/筛选结果</Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col span={24} md={6}>
          <Card><Statistic title="筛选结果" value={filtered.length} /></Card>
        </Col>
        <Col span={24} md={6}>
          <Card><Statistic title="已选中" value={selectedRows.length} /></Card>
        </Col>
      </Row>

      <Card title="患者列表" style={{ marginTop: 16 }}>
        <Table
          rowSelection={{ type: 'checkbox', onChange: (_, rows) => setSelectedRows(rows) }}
          columns={columns}
          dataSource={filtered}
          rowKey="patient_id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  )
}
