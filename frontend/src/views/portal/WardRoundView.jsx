import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Input, Button, List, Tag, Skeleton, message,
  Avatar, Typography, Space, Divider, Empty, Collapse, Alert, Tooltip
} from 'antd'
import {
  UserOutlined, SendOutlined, RobotOutlined, MedicineBoxOutlined,
  FileSearchOutlined, WarningOutlined, AudioOutlined, AudioMutedOutlined,
  QuestionCircleOutlined, FundOutlined
} from '@ant-design/icons'
import PatientSearch from '../../components/PatientSearch.jsx'
import PatientIdLink from '../../components/PatientIdLink.jsx'
import {
  getPatientStoryline, getPatientRisk, getPatientQuality, askRag
} from '../../api/index.js'

const { Search } = Input
const { Text } = Typography
const { Panel } = Collapse

const suggestedQuestions = [
  '该患者为什么再入院风险高？',
  '患者当前有哪些质控问题？',
  '有哪些药物相互作用需要关注？',
  '请总结该患者最近一次入院情况。',
]

export default function WardRoundView() {
  const navigate = useNavigate()
  const [patientId, setPatientId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [focusList, setFocusList] = useState([])

  const [question, setQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [messages, setMessages] = useState([])
  const [recording, setRecording] = useState(false)
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadWardRound = async () => {
    if (!patientId) return
    setLoading(true)
    try {
      const [storyline, risk, quality] = await Promise.all([
        getPatientStoryline(patientId),
        getPatientRisk(patientId).catch(() => null),
        getPatientQuality(patientId).catch(() => null),
      ])
      setResult(storyline)
      setFocusList(buildFocusList(risk, quality))
      setMessages([])
    } catch (e) {
      message.error('查询失败')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const buildFocusList = (risk, quality) => {
    const list = []
    if (risk?.risk_level) {
      list.push({
        type: 'risk',
        label: '风险',
        text: `风险等级：${risk.risk_level}（评分 ${risk.risk_score ?? '-'}）`,
        icon: <WarningOutlined />,
      })
    }
    Object.entries(quality?.issues || {}).forEach(([key, issues]) => {
      if (Array.isArray(issues) && issues.length > 0) {
        list.push({ type: 'qc', label: '质控', text: `${key} ${issues.length} 项`, icon: <FileSearchOutlined /> })
      }
    })
    if (list.length === 0) list.push({ type: 'normal', label: '正常', text: '暂无特殊关注事项', icon: <MedicineBoxOutlined /> })
    return list
  }

  const buildContext = () => {
    return messages
      .filter((m) => m.role === 'user')
      .slice(-3)
      .map((m) => m.content)
      .join('\n')
  }

  const handleAsk = async (manualQuestion) => {
    const q = manualQuestion || question.trim()
    if (!q) return
    if (!patientId) {
      message.warning('请先选择患者')
      return
    }
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    setQuestion('')
    setChatLoading(true)
    try {
      const res = await askRag({
        question: q,
        patient_id: patientId,
        context: buildContext(),
      })
      const uncertain = isUncertain(res.answer)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          sources: res.sources,
          retrieved: res.retrieved,
          uncertain,
        },
      ])
    } catch (e) {
      message.error('问答失败')
    } finally {
      setChatLoading(false)
    }
  }

  const isUncertain = (answer) => {
    if (!answer) return true
    const keywords = ['未找到', '不支持', '无法确定', '没有足够', '暂无', '不确定', '暂不', '未检索']
    return keywords.some((k) => answer.includes(k))
  }

  const toggleRecord = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      message.warning('当前浏览器不支持语音识别')
      return
    }
    if (recording) return
    const recognition = new SpeechRecognition()
    recognition.lang = 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.onstart = () => setRecording(true)
    recognition.onend = () => setRecording(false)
    recognition.onerror = () => {
      message.error('语音识别失败')
      setRecording(false)
    }
    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript
      setQuestion((prev) => (prev ? `${prev} ${text}` : text))
    }
    recognition.start()
  }

  const renderRetrieved = (retrieved) => {
    if (!retrieved) return null
    return (
      <Collapse ghost size="small">
        <Panel header="查看答案来源" key="1">
          {retrieved.type === 'patient_timeline' && (
            <div>
              <Text type="secondary">来源类型：患者时间线</Text>
              <p>就诊次数：{retrieved.visit_count}</p>
              {(retrieved.visits || []).slice(0, 3).map((v, idx) => (
                <Tag color="blue" key={idx}>{v.admission_date || v.discharge_date || '未知日期'} {v.chief_complaint?.slice(0, 20)}</Tag>
              ))}
            </div>
          )}
          {retrieved.type === 'knowledge_graph' && (
            <div>
              <Text type="secondary">来源类型：知识图谱</Text>
              <p>检索到 {retrieved.nodes?.length || 0} 个节点，{retrieved.relationships?.length || 0} 条关系</p>
            </div>
          )}
          {retrieved.type === 'department_stats' && (
            <div>
              <Text type="secondary">来源类型：科室统计</Text>
              <pre style={{ fontSize: 12 }}>{JSON.stringify(retrieved.metrics || {}, null, 2)}</pre>
            </div>
          )}
        </Panel>
      </Collapse>
    )
  }

  return (
    <div>
      <Card title="查房助手" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col span={24} md={12}>
            <PatientSearch value={patientId} onChange={setPatientId} />
          </Col>
          <Col span={24} md={12}>
            <Button type="primary" onClick={loadWardRound} loading={loading}>查询患者</Button>
            <Button style={{ marginLeft: 8 }} onClick={() => patientId && navigate(`/portal/patient/${patientId}`)}>查看全息视图</Button>
          </Col>
        </Row>
        <Divider style={{ margin: '16px 0' }} />
        <Text type="secondary"><QuestionCircleOutlined /> 推荐问题：</Text>
        <Space wrap style={{ marginTop: 8 }}>
          {suggestedQuestions.map((q) => (
            <Tag color="cyan" key={q} style={{ cursor: 'pointer' }} onClick={() => handleAsk(q)}>{q}</Tag>
          ))}
        </Space>
      </Card>

      {loading && <Skeleton active />}
      {!loading && result && (
        <Row gutter={[16, 16]}>
          <Col span={24} lg={8}>
            <Card title="患者摘要">
              <p><strong>患者ID：</strong><PatientIdLink patientId={result.patient?.patient_id} /></p>
              <p><strong>病案号：</strong>{result.patient?.medical_record_no || '-'}</p>
              <p><strong>年龄：</strong>{result.patient?.age || '-'}</p>
              <p><strong>主要诊断：</strong>{result.timeline?.visits?.[0]?.diseases?.filter((d) => d.is_main).map((d) => d.display_name || d.name).join('、') || '-'}</p>
              <p><strong>就诊次数：</strong>{result.visit_count}</p>
            </Card>
            <Card title="今日关注" style={{ marginTop: 16 }}>
              <List
                size="small"
                dataSource={focusList}
                renderItem={(item) => (
                  <List.Item>
                    <Tag color={item.type === 'risk' ? 'red' : item.type === 'qc' ? 'orange' : 'blue'}>{item.icon} {item.label}</Tag>
                    {item.text}
                  </List.Item>
                )}
              />
            </Card>
          </Col>

          <Col span={24} lg={16}>
            <Card title="查房问答助手" style={{ height: '100%' }}>
              <div style={{ maxHeight: 360, overflowY: 'auto', padding: '0 8px', marginBottom: 16, background: '#f5f5f5', borderRadius: 8 }}>
                {messages.length === 0 ? (
                  <Empty description="可询问该患者的诊疗、风险、用药等问题" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  messages.map((msg, idx) => (
                    <div key={idx} style={{ margin: '12px 0', display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                      <Space direction="vertical" style={{ maxWidth: '80%' }}>
                        <Space>
                          <Avatar icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />} style={{ background: msg.role === 'user' ? '#1890ff' : '#52c41a' }} />
                          <Text type="secondary">{msg.role === 'user' ? '我' : '查房助手'}</Text>
                        </Space>
                        <div style={{ padding: 10, borderRadius: 8, background: msg.role === 'user' ? '#1890ff' : '#fff', color: msg.role === 'user' ? '#fff' : 'rgba(0,0,0,0.85)', whiteSpace: 'pre-wrap' }}>
                          {msg.content}
                        </div>
                        {msg.role === 'assistant' && (
                          <>
                            {msg.uncertain && (
                              <Alert
                                type="warning"
                                message="证据不足或无法确认"
                                description="当前知识图谱或患者数据中未能找到充分证据支持上述结论，建议结合临床判断。"
                                showIcon
                                style={{ background: '#fffbe6' }}
                              />
                            )}
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              <FundOutlined /> 来源：{msg.sources?.slice(0, 3).join('、') || '知识图谱'}
                            </Text>
                            {renderRetrieved(msg.retrieved)}
                          </>
                        )}
                      </Space>
                    </div>
                  ))
                )}
                <div ref={chatEndRef} />
              </div>
              <Search
                placeholder="例如：该患者为什么再入院风险高？"
                enterButton={<><SendOutlined /> 提问</>}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onSearch={() => handleAsk()}
                loading={chatLoading}
                addonAfter={
                  <Tooltip title={recording ? '正在收听…' : '语音输入'}>
                    <Button
                      icon={recording ? <AudioOutlined /> : <AudioMutedOutlined />}
                      type={recording ? 'primary' : 'default'}
                      onClick={toggleRecord}
                      danger={recording}
                    />
                  </Tooltip>
                }
              />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}
