import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Row, Col, Button, Empty, message, Tag } from 'antd'
import PatientSearch from '../../components/PatientSearch.jsx'

const DEFAULT_PATIENT_ID = '4116-002-000000000000000000000021'

export default function PatientSearchView() {
  const navigate = useNavigate()
  const [patientId, setPatientId] = useState(DEFAULT_PATIENT_ID)

  const handleView = () => {
    if (!patientId) {
      message.warning('请先选择患者')
      return
    }
    navigate(`/portal/patient/${patientId}`)
  }

  return (
    <Row gutter={[16, 16]} justify="center">
      <Col span={24} md={12}>
        <Card title="患者全息视图查询">
          <PatientSearch value={patientId} onChange={setPatientId} style={{ width: '100%', marginBottom: 16 }} />
          <div style={{ marginBottom: 16 }}>
            <Tag color="blue">默认测试患者：{DEFAULT_PATIENT_ID}</Tag>
          </div>
          <Button type="primary" block size="large" onClick={handleView}>查看全息视图</Button>
          <div style={{ marginTop: 16 }}>
            <Empty description="选择患者后查看完整诊疗时间轴、风险预测与质控问题" />
          </div>
        </Card>
      </Col>
    </Row>
  )
}
