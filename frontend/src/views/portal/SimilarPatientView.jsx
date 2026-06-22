import { useState } from 'react'
import { Row, Col, Card, Button, List, Tag, Table, Input, message, Empty } from 'antd'
import PatientSearch from '../../components/PatientSearch.jsx'
import PatientIdLink from '../../components/PatientIdLink.jsx'
import { getSimilarPatients, getPathway } from '../../api/index.js'

export default function SimilarPatientView() {
  const [patientId, setPatientId] = useState('')
  const [disease, setDisease] = useState('')
  const [similar, setSimilar] = useState(null)
  const [pathway, setPathway] = useState(null)
  const [loading, setLoading] = useState(false)
  const [pathLoading, setPathLoading] = useState(false)

  const searchSimilar = async () => {
    if (!patientId) return
    setLoading(true)
    try {
      const res = await getSimilarPatients(patientId)
      setSimilar(res)
    } finally {
      setLoading(false)
    }
  }

  const searchPathway = async () => {
    if (!disease) return
    setPathLoading(true)
    try {
      const res = await getPathway(disease)
      setPathway(res)
    } finally {
      setPathLoading(false)
    }
  }

  const columns = [
    { title: '患者ID', dataIndex: 'patient_id', render: (v) => <PatientIdLink patientId={v} /> },
    { title: '相似度', dataIndex: 'score', render: (v) => `${(Number(v) * 100).toFixed(1)}%` },
    { title: '共同诊断', dataIndex: 'common_diseases', render: (v) => (v || []).slice(0, 3).join('、') },
    { title: '共同用药', dataIndex: 'common_drugs', render: (v) => (v || []).slice(0, 3).join('、') },
  ]

  return (
    <Row gutter={[16, 16]}>
      <Col span={24} md={12}>
        <Card title="相似患者推荐">
          <PatientSearch value={patientId} onChange={setPatientId} style={{ marginBottom: 16 }} />
          <Button type="primary" onClick={searchSimilar} loading={loading}>查找相似患者</Button>
          {similar?.similar_patients?.length > 0 ? (
            <>
              <p style={{ marginTop: 16 }}><strong>目标患者：</strong><PatientIdLink patientId={similar.patient_id} /></p>
              <Table
                columns={columns}
                dataSource={similar.similar_patients}
                rowKey="patient_id"
                size="small"
                style={{ marginTop: 16 }}
              />
            </>
          ) : (
            <Empty description="选择患者后查找相似病例" style={{ marginTop: 24 }} />
          )}
        </Card>
      </Col>

      <Col span={24} md={12}>
        <Card title="诊疗路径推荐">
          <Input
            placeholder="输入疾病名称，例如：肺癌"
            value={disease}
            onChange={(e) => setDisease(e.target.value)}
            style={{ marginBottom: 16 }}
          />
          <Button type="primary" onClick={searchPathway} loading={pathLoading}>查看诊疗路径</Button>
          {pathway?.narrative && (
            <div style={{ marginTop: 16, padding: 12, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4 }}>
              <p style={{ whiteSpace: 'pre-line' }}>{pathway.narrative}</p>
            </div>
          )}
          {pathway?.data && (
            <List
              size="small"
              style={{ marginTop: 16 }}
              dataSource={Object.entries(pathway.data).slice(0, 6)}
              renderItem={([k, v]) => (
                <List.Item>
                  <Tag color="blue">{k}</Tag>
                  {Array.isArray(v) ? v.slice(0, 5).join('、') : String(v)}
                </List.Item>
              )}
            />
          )}
        </Card>
      </Col>
    </Row>
  )
}
