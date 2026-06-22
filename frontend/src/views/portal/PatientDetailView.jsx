import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Descriptions, Spin, Button, Skeleton,
  Tag, Tabs, List, Alert, Space, Divider, message, Empty, Typography
} from 'antd'
import {
  ArrowLeftOutlined, ExclamationCircleOutlined,
  ReloadOutlined, InfoCircleOutlined, WarningOutlined
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import {
  getPatientStoryline, getPatientRisk, getPatientQuality,
  getPatientReadmission, getSimilarPatients
} from '../../api/index.js'
import PatientIdLink from '../../components/PatientIdLink.jsx'

const { TabPane } = Tabs
const { Text } = Typography

export default function PatientDetailView() {
  const { patientId } = useParams()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [riskLoading, setRiskLoading] = useState(false)
  const [storyline, setStoryline] = useState(null)
  const [risk, setRisk] = useState(null)
  const [quality, setQuality] = useState(null)
  const [readmission, setReadmission] = useState(null)
  const [similar, setSimilar] = useState(null)

  const load = () => {
    setLoading(true)
    getPatientStoryline(patientId)
      .then(setStoryline)
      .catch(() => message.error('未找到患者信息'))
      .finally(() => setLoading(false))

    setRiskLoading(true)
    Promise.all([
      getPatientRisk(patientId).catch(() => null),
      getPatientQuality(patientId).catch(() => null),
      getPatientReadmission(patientId).catch(() => null),
      getSimilarPatients(patientId).catch(() => null),
    ]).then(([r, q, rm, sm]) => {
      setRisk(r)
      setQuality(q)
      setReadmission(rm)
      setSimilar(sm)
    }).finally(() => setRiskLoading(false))
  }

  useEffect(() => {
    load()
  }, [patientId])

  const visits = storyline?.timeline?.visits || []
  const patient = storyline?.patient || {}

  const abnormalFlags = useMemo(() => {
    const flags = []
    if (risk?.risk_score >= 70) flags.push({ type: '风险', text: `风险评分 ${risk.risk_score}（${risk.risk_level}）`, color: 'red', level: 3 })
    if (quality?.issues) {
      Object.entries(quality.issues).forEach(([key, issues]) => {
        if (Array.isArray(issues) && issues.length > 0) {
          flags.push({ type: '质控', text: `${key} ${issues.length} 项`, color: 'orange', level: 2 })
        }
      })
    }
    visits.forEach((v) => {
      if (v.length_of_stay >= 15) flags.push({ type: '住院天数', text: `${v.admission_date || v.discharge_date || ''} 住院 ${v.length_of_stay} 天`, color: 'volcano', level: 2 })
    })

    const drugNames = new Set()
    visits.forEach((v) => v.drugs?.forEach((d) => drugNames.add(d.name)))
    const chemoKeywords = ['化疗', '顺铂', '紫杉醇', '奥沙利铂', '吉西他滨', '氟尿嘧啶', '卡培他滨', '多西他赛', '替吉奥']
    const hasChemo = Array.from(drugNames).some((name) => chemoKeywords.some((k) => name?.includes(k)))
    if (hasChemo) flags.push({ type: '治疗', text: '患者接受过化疗', color: 'purple', level: 1 })

    const surgeryCount = visits.reduce((sum, v) => sum + (v.surgeries?.length || 0), 0)
    if (surgeryCount > 0) flags.push({ type: '手术', text: `累计手术 ${surgeryCount} 次`, color: 'blue', level: 1 })

    if (visits.length >= 3) flags.push({ type: '再入院', text: `就诊 ${visits.length} 次，需关注再入院风险`, color: 'magenta', level: 2 })

    return flags.sort((a, b) => b.level - a.level)
  }, [risk, quality, visits])

  const drugInteractions = useMemo(() => {
    const interactions = []
    const drugSet = new Set()
    visits.forEach((v) => v.drugs?.forEach((d) => drugSet.add(d.name)))
    const drugs = Array.from(drugSet)
    const pairs = []
    for (let i = 0; i < drugs.length; i++) {
      for (let j = i + 1; j < drugs.length; j++) {
        pairs.push([drugs[i], drugs[j]])
      }
    }
    const knownPairs = [
      ['顺铂', '紫杉醇'],
      ['奥沙利铂', '氟尿嘧啶'],
      ['华法林', '阿司匹林'],
      ['甲氨蝶呤', '磺胺'],
      ['吉西他滨', '顺铂'],
    ]
    pairs.forEach(([a, b]) => {
      const hit = knownPairs.find(([ka, kb]) =>
        (a.includes(ka) && b.includes(kb)) || (a.includes(kb) && b.includes(ka))
      )
      if (hit) interactions.push(`${a} + ${b}`)
    })
    return interactions
  }, [visits])

  const missingExams = useMemo(() => {
    const required = ['CT', 'MRI', '超声', '心电图', '血常规']
    const had = new Set()
    visits.forEach((v) => v.exams?.forEach((e) => {
      required.forEach((r) => {
        if (e.name?.includes(r)) had.add(r)
      })
    }))
    return required.filter((r) => !had.has(r))
  }, [visits])

  const hospitalOption = useMemo(() => {
    const labels = visits.map((v, i) => `第${i + 1}次`)
    const values = visits.map((v) => v.length_of_stay || 0)

    const markPointData = visits
      .map((v, i) => {
        const examCount = v.exams?.length || 0
        const labCount = v.labs?.length || 0
        if (examCount + labCount === 0) return null
        return {
          coord: [i, values[i]],
          value: `检查${examCount}/检验${labCount}`,
          itemStyle: { color: '#52c41a' },
          label: { show: true, fontSize: 10, position: 'top' },
        }
      })
      .filter(Boolean)

    return {
      title: { text: '历次住院天数', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: {
        trigger: 'axis',
        confine: true,
        enterable: true,
        position: function (point) {
          return [point[0] + 12, point[1] - 10]
        },
        extraCssText: 'max-width: 320px; white-space: pre-wrap; word-wrap: break-word;',
        formatter: (params) => {
          const idx = params[0].dataIndex
          const v = visits[idx]
          const exams = v.exams?.map((e) => e.name).slice(0, 8).join('、') || '无'
          const labs = v.labs?.map((l) => l.name).slice(0, 8).join('、') || '无'
          return `<div style="max-width: 300px;"><strong>第${idx + 1}次住院</strong><br/>住院天数：${values[idx]} 天<br/>检查：${exams}<br/>检验：${labs}</div>`
        },
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: labels },
      yAxis: { type: 'value', name: '天' },
      series: [{
        data: values,
        type: 'line',
        smooth: true,
        markLine: { data: [{ type: 'average', name: '平均值' }] },
        areaStyle: { color: 'rgba(24,144,255,0.1)' },
        itemStyle: { color: '#1890ff' },
        markPoint: {
          data: markPointData,
          symbolSize: 56,
        },
      }],
    }
  }, [visits])

  // 词云图：诊断与用药聚合
  const wordCloudData = useMemo(() => {
    const diseaseCounts = {}
    const drugCounts = {}
    visits.forEach((v) => {
      v.diseases?.forEach((d) => {
        const name = d.display_name || d.name
        if (name) diseaseCounts[name] = (diseaseCounts[name] || 0) + 1
      })
      v.drugs?.forEach((d) => {
        const name = d.name
        if (name) drugCounts[name] = (drugCounts[name] || 0) + 1
      })
    })
    const toArray = (obj) => Object.entries(obj)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 60)
    return {
      diseases: toArray(diseaseCounts),
      drugs: toArray(drugCounts),
    }
  }, [visits])

  const buildWordCloudOption = (title, data, colorPalette) => ({
    title: { text: title, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { show: true },
    series: [{
      type: 'wordCloud',
      shape: 'circle',
      left: 'center',
      top: 'center',
      width: '90%',
      height: '90%',
      sizeRange: [12, 48],
      rotationRange: [-45, 45],
      rotationStep: 45,
      gridSize: 8,
      drawOutOfBound: false,
      textStyle: {
        fontFamily: 'sans-serif',
        fontWeight: 'bold',
        color: (params) => colorPalette[params.dataIndex % colorPalette.length],
      },
      emphasis: {
        focus: 'self',
        textStyle: {
          textShadowBlur: 10,
          textShadowColor: '#333',
        },
      },
      data,
    }],
  })

  const diseaseCloudOption = useMemo(
    () => buildWordCloudOption('诊断词云', wordCloudData.diseases, ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272']),
    [wordCloudData.diseases]
  )
  const drugCloudOption = useMemo(
    () => buildWordCloudOption('用药词云', wordCloudData.drugs, ['#91cc75', '#5470c6', '#fac858', '#ee6666', '#73c0de', '#3ba272']),
    [wordCloudData.drugs]
  )

  return (
    <Spin spinning={loading}>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>返回</Button>
      {storyline && (
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Card title="患者基本信息" extra={<Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>}>
              <Descriptions bordered column={{ xxl: 4, xl: 3, lg: 3, md: 2, sm: 1, xs: 1 }}>
                <Descriptions.Item label="患者ID"><PatientIdLink patientId={patient.patient_id} /></Descriptions.Item>
                <Descriptions.Item label="病案号">{patient.medical_record_no || '-'}</Descriptions.Item>
                <Descriptions.Item label="年龄">{patient.age || '-'}</Descriptions.Item>
                <Descriptions.Item label="婚姻">{patient.marital_status || '-'}</Descriptions.Item>
                <Descriptions.Item label="职业">{patient.occupation || '-'}</Descriptions.Item>
                <Descriptions.Item label="就诊次数">{storyline.visit_count}</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>

          <Col span={24}>
            <Card title="关键异常提示">
              <Skeleton loading={riskLoading}>
                {abnormalFlags.length > 0 ? (
                  <Space wrap>
                    {abnormalFlags.map((f, idx) => (
                      <Tag icon={<ExclamationCircleOutlined />} color={f.color} key={idx}>{f.type}: {f.text}</Tag>
                    ))}
                  </Space>
                ) : (
                  <Alert type="success" message="暂无关键异常" />
                )}
                {drugInteractions.length > 0 && (
                  <Alert
                    type="warning"
                    icon={<WarningOutlined />}
                    message="潜在药物相互作用"
                    description={drugInteractions.join('；')}
                    style={{ marginTop: 12 }}
                    showIcon
                  />
                )}
                {missingExams.length > 0 && (
                  <Alert
                    type="info"
                    icon={<InfoCircleOutlined />}
                    message="缺失常规检查"
                    description={missingExams.join('、')}
                    style={{ marginTop: 12 }}
                    showIcon
                  />
                )}
              </Skeleton>
            </Card>
          </Col>

          <Col span={24} lg={16}>
            <Card title="诊疗时间轴">
              <Tabs defaultActiveKey="overview">
                <TabPane tab="住院情况概览" key="overview">
                  {visits.length === 0 ? <Empty /> : (
                    <ReactECharts option={hospitalOption} style={{ height: 380 }} />
                  )}
                </TabPane>
                <TabPane tab="就诊概览" key="visits">
                  {visits.length === 0 ? <Empty /> : (
                    <Row gutter={[16, 16]}>
                      <Col span={24} md={12}>
                        <ReactECharts option={diseaseCloudOption} style={{ height: 320 }} />
                      </Col>
                      <Col span={24} md={12}>
                        <ReactECharts option={drugCloudOption} style={{ height: 320 }} />
                      </Col>
                    </Row>
                  )}
                </TabPane>
              </Tabs>
            </Card>
          </Col>

          <Col span={24} lg={8}>
            <Card title="风险预测与质控">
              <Skeleton loading={riskLoading}>
                <p><strong>风险等级：</strong><Tag color={risk?.risk_level === '高' || risk?.risk_level === '极高' ? 'red' : 'blue'}>{risk?.risk_level || '-'}</Tag></p>
                <p><strong>风险评分：</strong>{risk?.risk_score ?? '-'}</p>
                <p><strong>重点因素：</strong>{risk?.risk_factors?.join('、') || '-'}</p>
                <Divider />
                <p><strong>质控问题：</strong></p>
                <List
                  size="small"
                  dataSource={Object.entries(quality?.issues || {}).filter(([_, issues]) => Array.isArray(issues) && issues.length > 0)}
                  renderItem={([key, issues]) => (
                    <List.Item>
                      <Tag color="orange">{key}</Tag> {issues.length} 项
                    </List.Item>
                  )}
                />
              </Skeleton>
            </Card>
          </Col>

          <Col span={24} lg={12}>
            <Card title="智能病程摘要" bodyStyle={{ height: 520, overflow: 'auto' }}>
              <p style={{ whiteSpace: 'pre-line' }}>{storyline.narrative}</p>
            </Card>
          </Col>

          <Col span={24} lg={12}>
            <Card title="再入院分析" bodyStyle={{ height: 520, overflow: 'auto' }}>
              <Skeleton loading={riskLoading}>
                {readmission?.narrative ? (
                  <p style={{ whiteSpace: 'pre-line' }}>{readmission.narrative}</p>
                ) : (
                  <Empty description="暂无再入院分析" />
                )}
              </Skeleton>
            </Card>
          </Col>

          <Col span={24} lg={12}>
            <Card title="相似患者">
              <Skeleton loading={riskLoading}>
                {similar?.similar_patients?.length > 0 ? (
                  <List
                    size="small"
                    dataSource={similar.similar_patients.slice(0, 5)}
                    renderItem={(item) => (
                      <List.Item>
                        <Tag color="blue">相似度 {(Number(item.score) * 100).toFixed(1)}%</Tag>
                        <PatientIdLink patientId={item.patient_id} />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="未找到相似患者" />
                )}
              </Skeleton>
            </Card>
          </Col>
        </Row>
      )}
    </Spin>
  )
}
