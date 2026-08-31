import { useEffect, useState } from 'react'
import {
  Row, Col, Card, Steps, Button, Table, Tag, Alert, Menu, Tooltip, Form,
  Input, InputNumber, Select, Switch, Checkbox, Statistic, Typography,
  Space, Empty, Skeleton, message, List, Tabs, Collapse,
} from 'antd'
import {
  DatabaseOutlined, ApartmentOutlined, FileTextOutlined, CloudServerOutlined,
  PlayCircleOutlined, PlusOutlined, SearchOutlined, RobotOutlined, DownloadOutlined,
  BulbOutlined, RocketOutlined, RedoOutlined, ClockCircleOutlined,
  LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import {
  getResearchDataAssets, getResearchSkills, runResearchSkill, runResearchCode,
  recommendResearch, interpretResearchResult, searchLiterature, generatePaper,
  proposeResearchTopics, startAutoResearch, getAutoResearchJob,
  getAutoResearchHistory, evaluateCustomTopic,
} from '../../api/index.js'

const { TextArea } = Input
const { Title, Paragraph, Text } = Typography

const DEFAULT_CODE = `# 示例：对 visits 住院记录 DataFrame 做简单聚合
# 可用变量：visits（DataFrame）；请将最终结果赋给 result
result = visits.groupby('department').size().reset_index(name='count')
`

const PAPER_SECTIONS = [
  ['abstract', '摘要'],
  ['introduction', '引言'],
  ['methods', '方法'],
  ['results', '结果'],
  ['discussion', '讨论'],
  ['conclusion', '结论'],
  ['references', '参考文献'],
]

// 智能模式论文 sections 的 key 直接就是中文，按此顺序展示
const AUTO_PAPER_SECTIONS = ['摘要', '前言', '资料与方法', '结果', '讨论', '结论']

const FEASIBILITY_COLORS = { 高: 'green', 中: 'orange', 低: 'red' }

// 历史研究记录状态 → Tag 颜色与文案
const JOB_STATE_TAG = {
  running: { color: 'blue', text: '进行中' },
  done: { color: 'green', text: '已完成' },
  failed: { color: 'red', text: '失败' },
}

// 流水线步骤状态 → antd Steps 状态与图标
const STEP_STATUS = { pending: 'wait', running: 'process', done: 'finish', failed: 'error' }
const STEP_ICONS = {
  pending: <ClockCircleOutlined />,
  running: <LoadingOutlined />,
  done: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
}

// 通用键值对展示（图谱统计、文本数据、向量库等后端返回的 dict）
function KeyValueList({ data }) {
  const entries = Object.entries(data || {})
  if (!entries.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
  return (
    <List
      size="small"
      dataSource={entries}
      renderItem={([k, v]) => (
        <List.Item>
          <Tag color="blue">{k}</Tag>
          <Text>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</Text>
        </List.Item>
      )}
    />
  )
}

// 统一结果展示区（Skill 运行 / 自定义代码共用）
function ResultView({ result, onAddMaterial, added }) {
  const [interpreting, setInterpreting] = useState(false)
  const [interpretation, setInterpretation] = useState(result?.interpretation)

  useEffect(() => {
    setInterpretation(result?.interpretation)
  }, [result])

  if (!result) return null

  const handleInterpret = async () => {
    setInterpreting(true)
    try {
      const res = await interpretResearchResult(result.result_id)
      if (res?.interpretation) {
        setInterpretation(res.interpretation)
        message.success('解读已更新')
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setInterpreting(false)
    }
  }

  return (
    <div style={{ marginTop: 16 }}>
      <Card
        title={`分析结果：${result.skill_name || result.skill_id || '自定义代码'}`}
        extra={
          onAddMaterial && (
            <Button
              icon={<PlusOutlined />}
              disabled={added}
              onClick={() => onAddMaterial(result)}
            >
              {added ? '已加入素材' : '加入论文素材'}
            </Button>
          )
        }
      >
        {result.summary && (
          <Alert type="info" showIcon message="结果摘要" description={result.summary} style={{ marginBottom: 16 }} />
        )}
        {(result.tables || []).map((t, idx) => (
          <Card key={idx} type="inner" title={t.title || `表格 ${idx + 1}`} style={{ marginBottom: 16 }}>
            <Table
              size="small"
              columns={(t.columns || []).map((c) => ({ title: c, dataIndex: c, key: c }))}
              dataSource={(t.rows || []).map((row, i) => {
                const obj = { __key: i }
                ;(t.columns || []).forEach((c, j) => { obj[c] = row[j] })
                return obj
              })}
              rowKey="__key"
              pagination={{ pageSize: 10, size: 'small' }}
            />
          </Card>
        ))}
        <Row gutter={[16, 16]}>
          {(result.charts || []).map((c, idx) => (
            <Col span={24} lg={12} key={idx}>
              <Card type="inner" title={c.title || `图表 ${idx + 1}`}>
                <ReactECharts option={c.option || {}} style={{ height: 320 }} />
              </Card>
            </Col>
          ))}
        </Row>
        {result.facts && Object.keys(result.facts).length > 0 && (
          <Card type="inner" title="关键事实" style={{ marginTop: 16 }}>
            <KeyValueList data={result.facts} />
          </Card>
        )}
        <Card
          type="inner"
          title="AI 解读"
          style={{ marginTop: 16 }}
          extra={<Button size="small" onClick={handleInterpret} loading={interpreting}>重新解读</Button>}
        >
          {interpretation ? (
            <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{interpretation}</Paragraph>
          ) : (
            <Text type="secondary">暂无解读</Text>
          )}
        </Card>
      </Card>
    </div>
  )
}

// 按 params_schema 动态渲染的表单项
function ParamField({ schema, value, onChange }) {
  const common = { value, onChange, style: { width: '100%' } }
  switch (schema.type) {
    case 'number':
      return <InputNumber {...common} min={schema.min} max={schema.max} onChange={(v) => onChange(v)} />
    case 'select':
      return (
        <Select
          {...common}
          options={(schema.options || []).map((o) =>
            typeof o === 'object' ? o : { label: String(o), value: o }
          )}
        />
      )
    case 'boolean':
      return <Switch checked={!!value} onChange={onChange} />
    case 'string':
    default:
      return <Input {...common} />
  }
}

// ---------- 智能模式：议题推荐 → 自动流水线 → 论文展示 ----------
function SmartModePanel() {
  const [proposing, setProposing] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [topics, setTopics] = useState(null) // null = 尚未请求
  const [startingId, setStartingId] = useState(null) // 正在启动的 topic id
  const [job, setJob] = useState(null)

  // 历史研究记录
  const [history, setHistory] = useState(null) // null = 尚未加载
  const [historyLoading, setHistoryLoading] = useState(false)

  // 自定义议题
  const [idea, setIdea] = useState('')
  const [evaluating, setEvaluating] = useState(false)
  const [customTopic, setCustomTopic] = useState(null)
  const [customSupported, setCustomSupported] = useState(null)

  const jobId = job?.job_id
  const jobState = job?.state

  // 流水线轮询：每 3 秒一次，done/failed 停止；组件卸载时清理
  useEffect(() => {
    if (!jobId || jobState === 'done' || jobState === 'failed') return undefined
    const timer = setInterval(async () => {
      try {
        const res = await getAutoResearchJob(jobId)
        if (res?.job) setJob(res.job)
      } catch {
        // 拦截器已统一报错
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [jobId, jobState])

  // 进入智能模式即加载历史研究记录
  const loadHistory = async () => {
    setHistoryLoading(true)
    try {
      const res = await getAutoResearchHistory()
      setHistory(res?.jobs || [])
    } catch {
      // 拦截器已统一报错
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  // refresh=false 首次推荐；refresh=true 换一批（排除当前已展示议题）
  const handlePropose = async (refresh = false) => {
    if (refresh) setRefreshing(true)
    else setProposing(true)
    try {
      const res = await proposeResearchTopics({
        refresh,
        exclude_titles: refresh ? (topics || []).map((t) => t.title).filter(Boolean) : [],
      })
      if (res?.topics) {
        setTopics(res.topics)
        message.success(refresh ? '已换一批新议题' : '候选议题已生成')
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setProposing(false)
      setRefreshing(false)
    }
  }

  const handleEvaluate = async () => {
    if (!idea.trim()) {
      message.warning('请先描述您的研究设想')
      return
    }
    setEvaluating(true)
    try {
      const res = await evaluateCustomTopic(idea.trim())
      if (res?.topic) {
        setCustomTopic(res.topic)
        setCustomSupported(!!res.supported)
        message.success('议题评估完成')
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setEvaluating(false)
    }
  }

  const handleStart = async (topic) => {
    setStartingId(topic.id)
    try {
      const res = await startAutoResearch(topic)
      if (res?.job_id) {
        setJob({ job_id: res.job_id, state: 'running', steps: [], topic })
        message.success('自动研究已启动')
        try {
          const detail = await getAutoResearchJob(res.job_id)
          if (detail?.job) setJob(detail.job)
        } catch {
          // 拦截器已统一报错，等待轮询恢复
        }
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setStartingId(null)
    }
  }

  const handleRestart = () => {
    setJob(null)
    loadHistory()
  }

  // 历史记录「查看」：拉完整 job 并切到论文展示阶段
  const handleViewHistoryJob = async (record) => {
    try {
      const res = await getAutoResearchJob(record.job_id)
      if (res?.job) setJob(res.job)
    } catch {
      // 拦截器已统一报错
    }
  }

  // 历史记录「查看进度」：切到流水线视图并恢复轮询
  const handleResumeJob = (record) => {
    setJob({ job_id: record.job_id, state: 'running', steps: [], topic: { title: record.topic_title } })
  }

  const openDownload = (url) => {
    if (!url) return
    if (!url.startsWith('/api')) url = `/api${url.startsWith('/') ? '' : '/'}${url}`
    window.open(url, '_blank')
  }

  const handleAutoDownload = () => {
    let url = job?.download_url || ''
    if (!url && job?.filename) url = `/research/paper/download/${job.filename}`
    openDownload(url)
  }

  // ---------- 阶段 1：议题推荐 ----------
  // 议题卡片（推荐议题与自定义议题共用，extraTag 可附加"数据支持"标记）
  const renderTopicCard = (t, extraTag) => (
    <Card
      title={t.title}
      extra={
        <Space size={4}>
          {extraTag}
          <Tag color={FEASIBILITY_COLORS[t.feasibility] || 'default'}>可行性：{t.feasibility}</Tag>
        </Space>
      }
    >
      <Paragraph>
        <Text strong>研究问题：</Text>
        {t.question}
      </Paragraph>
      <Paragraph>
        <Text strong>推荐理由：</Text>
        {t.rationale}
      </Paragraph>
      {(t.skills || []).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Text strong>拟用分析方法：</Text>
          <List
            size="small"
            dataSource={t.skills}
            renderItem={(s) => (
              <List.Item style={{ padding: '4px 0' }}>
                <Tag color="blue">{s.name}</Tag>
                <Text type="secondary">{s.purpose}</Text>
              </List.Item>
            )}
          />
        </div>
      )}
      <Button
        type="primary"
        icon={<RocketOutlined />}
        loading={startingId === t.id}
        disabled={startingId !== null && startingId !== t.id}
        onClick={() => handleStart(t)}
      >
        开始自动研究
      </Button>
    </Card>
  )

  // 历史研究记录（阶段 1 顶部，默认展开）
  const renderHistory = () => (
    <Collapse
      style={{ marginBottom: 16 }}
      defaultActiveKey={['history']}
      items={[{
        key: 'history',
        label: '历史研究记录',
        children: (
          <Table
            size="small"
            loading={historyLoading}
            dataSource={history || []}
            rowKey="job_id"
            pagination={(history || []).length > 5 ? { pageSize: 5, size: 'small' } : false}
            locale={{ emptyText: '暂无历史研究记录' }}
            columns={[
              { title: '创建时间', dataIndex: 'created_at', width: 170, render: (v) => v || '-' },
              { title: '议题标题', dataIndex: 'topic_title', render: (v) => v || '-' },
              { title: '论文标题', dataIndex: 'paper_title', render: (v) => v || '-' },
              {
                title: '状态', dataIndex: 'state', width: 90,
                render: (v) => {
                  const tag = JOB_STATE_TAG[v] || { color: 'default', text: v || '未知' }
                  return <Tag color={tag.color}>{tag.text}</Tag>
                },
              },
              {
                title: '操作', key: 'actions', width: 150,
                render: (_, record) => (
                  <Space size={0}>
                    {record.state === 'done' && record.download_url && (
                      <>
                        <Button type="link" size="small" onClick={() => handleViewHistoryJob(record)}>
                          查看
                        </Button>
                        <Button type="link" size="small" onClick={() => openDownload(record.download_url)}>
                          下载
                        </Button>
                      </>
                    )}
                    {record.state === 'running' && (
                      <Button type="link" size="small" onClick={() => handleResumeJob(record)}>
                        查看进度
                      </Button>
                    )}
                  </Space>
                ),
              },
            ]}
          />
        ),
      }]}
    />
  )

  // 自定义议题：描述研究设想 → 评估数据支撑性并匹配分析方法
  const renderCustomTopic = () => (
    <Card title="描述您自己的研究设想" style={{ marginTop: 16 }}>
      <TextArea
        value={idea}
        onChange={(e) => setIdea(e.target.value)}
        rows={3}
        placeholder="如：化疗后骨髓抑制的发生规律"
      />
      <Button
        type="primary"
        style={{ marginTop: 12 }}
        loading={evaluating}
        onClick={handleEvaluate}
      >
        {evaluating ? '正在评估数据支撑性并匹配分析方法' : '评估我的议题'}
      </Button>
      {customTopic && (
        <div style={{ marginTop: 16 }}>
          {renderTopicCard(
            customTopic,
            customSupported
              ? <Tag color="green">数据支持</Tag>
              : <Tag color="red">数据支撑不足</Tag>
          )}
        </div>
      )}
    </Card>
  )

  const renderTopics = () => {
    if (topics === null) {
      return (
        <>
          {renderHistory()}
          <Card>
            <div style={{ textAlign: 'center', padding: '48px 0' }}>
              <BulbOutlined style={{ fontSize: 48, color: '#1677ff' }} />
              <Title level={4} style={{ marginTop: 16 }}>智能模式：一键完成科研分析与论文撰写</Title>
              <Paragraph type="secondary">
                系统将自动评估科室数据资产，推荐可落地的研究议题；选定议题后自动执行分析并生成论文初稿。
                <br />
                点击下方按钮开始（由 AI 生成候选议题，需要一定时间）。
              </Paragraph>
              <Button
                type="primary"
                size="large"
                icon={<BulbOutlined />}
                loading={proposing}
                onClick={() => handlePropose(false)}
              >
                {proposing ? '正在评估数据资产并生成候选议题，约需 1 分钟' : '分析数据并推荐研究议题'}
              </Button>
            </div>
          </Card>
          {renderCustomTopic()}
        </>
      )
    }
    return (
      <>
        {renderHistory()}
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="以下为系统根据现有数据资产推荐的候选研究议题，请选择一个开始自动研究"
          action={
            <Button size="small" icon={<RedoOutlined />} loading={refreshing} onClick={() => handlePropose(true)}>
              {refreshing ? '正在换一批新议题' : '重新推荐'}
            </Button>
          }
        />
        {topics.length === 0 ? (
          <Card><Empty description="暂未生成候选议题，请点击右上角重新推荐" /></Card>
        ) : (
          <Row gutter={[16, 16]}>
            {topics.map((t) => (
              <Col span={24} lg={12} key={t.id}>
                {renderTopicCard(t)}
              </Col>
            ))}
          </Row>
        )}
        {renderCustomTopic()}
      </>
    )
  }

  // ---------- 阶段 2：流水线运行 ----------
  const renderRunning = () => (
    <Card title={`研究议题：${job.topic?.title || '自动研究'}`}>
      {jobState === 'failed' ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="自动研究执行失败"
          description={job.error || '未知错误，请重试'}
          action={
            <Button size="small" icon={<RedoOutlined />} onClick={handleRestart}>
              重新开始
            </Button>
          }
        />
      ) : (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="正在自动执行分析与论文撰写，通常需要 3-6 分钟，请勿关闭页面"
        />
      )}
      <Steps
        direction="vertical"
        current={job.current_step ?? 0}
        items={(job.steps || []).map((s) => ({
          title: s.label,
          status: STEP_STATUS[s.state] || 'wait',
          icon: STEP_ICONS[s.state],
          description: s.state === 'running' ? '进行中' : s.detail,
        }))}
      />
    </Card>
  )

  // ---------- 阶段 3：论文展示 ----------
  const renderPaperResult = () => {
    const sections = job.paper?.sections || {}
    const sectionKeys = AUTO_PAPER_SECTIONS
      .filter((k) => sections[k])
      .concat(Object.keys(sections).filter((k) => !AUTO_PAPER_SECTIONS.includes(k)))
    return (
      <>
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message="自动研究已完成，论文初稿已生成"
        />
        <Card
          title={job.paper?.title || '生成的论文'}
          extra={
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              disabled={!job.download_url && !job.filename}
              onClick={handleAutoDownload}
            >
              下载 Word 文档
            </Button>
          }
          style={{ marginBottom: 16 }}
        >
          <div style={{ maxHeight: 600, overflow: 'auto' }}>
            <Typography>
              {sectionKeys.length > 0 ? (
                sectionKeys.map((key) => (
                  <div key={key}>
                    <Title level={4}>{key}</Title>
                    <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{sections[key]}</Paragraph>
                  </div>
                ))
              ) : (
                <Empty description="暂无论文内容" />
              )}
            </Typography>
          </div>
        </Card>
        <Collapse
          items={[{
            key: 'steps',
            label: '查看各步分析详情',
            children: (
              <List
                size="small"
                dataSource={job.steps || []}
                locale={{ emptyText: '暂无步骤信息' }}
                renderItem={(s) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <>
                          {s.label}{' '}
                          <Tag color={s.state === 'done' ? 'green' : s.state === 'failed' ? 'red' : 'default'}>
                            {s.state}
                          </Tag>
                        </>
                      }
                      description={
                        <>
                          <div>{s.detail || '暂无说明'}</div>
                          {s.result_id && <Text type="secondary">结果 ID：{s.result_id}</Text>}
                        </>
                      }
                    />
                  </List.Item>
                )}
              />
            ),
          }]}
        />
        <div style={{ textAlign: 'right', marginTop: 16 }}>
          <Button icon={<RedoOutlined />} onClick={handleRestart}>
            开始新的研究
          </Button>
        </div>
      </>
    )
  }

  if (!job) return renderTopics()
  if (jobState === 'done') return renderPaperResult()
  return renderRunning()
}

// ---------- 专家模式：四步向导（原有功能） ----------
function ExpertModePanel() {
  const [step, setStep] = useState(0)
  const [materials, setMaterials] = useState([]) // [{result_id, skill_name}]

  // 第一步：数据资产
  const [assetsLoading, setAssetsLoading] = useState(false)
  const [assets, setAssets] = useState(null)

  // 第二步：分析 Skills
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [categories, setCategories] = useState([])
  const [activeSkill, setActiveSkill] = useState(null)
  const [params, setParams] = useState({})
  const [running, setRunning] = useState(false)
  const [skillResult, setSkillResult] = useState(null)

  // 第三步：自定义代码
  const [code, setCode] = useState(DEFAULT_CODE)
  const [codeRunning, setCodeRunning] = useState(false)
  const [codeResult, setCodeResult] = useState(null)

  // 第四步：论文生成
  const [question, setQuestion] = useState('')
  const [paperTitle, setPaperTitle] = useState('')
  const [recommending, setRecommending] = useState(false)
  const [recommendation, setRecommendation] = useState(null)
  const [litQuery, setLitQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [articles, setArticles] = useState([])
  const [litSummary, setLitSummary] = useState('')
  const [checkedPmids, setCheckedPmids] = useState([])
  const [generating, setGenerating] = useState(false)
  const [paper, setPaper] = useState(null)
  const [paperFile, setPaperFile] = useState(null)

  const loadAssets = async () => {
    setAssetsLoading(true)
    try {
      const res = await getResearchDataAssets()
      setAssets(res?.assets || null)
    } catch {
      // 拦截器已统一报错
    } finally {
      setAssetsLoading(false)
    }
  }

  const loadSkills = async () => {
    setSkillsLoading(true)
    try {
      const res = await getResearchSkills()
      setCategories(res?.categories || [])
    } catch {
      // 拦截器已统一报错
    } finally {
      setSkillsLoading(false)
    }
  }

  useEffect(() => {
    loadAssets()
    loadSkills()
  }, [])

  const allSkills = categories.flatMap((c) => c.skills || [])
  const skillNameOf = (id) => allSkills.find((s) => s.id === id)?.name || id

  const selectSkill = (skill) => {
    setActiveSkill(skill)
    const defaults = {}
    ;(skill.params_schema || []).forEach((p) => { defaults[p.name] = p.default })
    setParams(defaults)
    setSkillResult(null)
  }

  const handleRunSkill = async () => {
    if (!activeSkill) return
    setRunning(true)
    setSkillResult(null)
    try {
      const res = await runResearchSkill(activeSkill.id, params)
      if (res?.result_id) {
        setSkillResult(res)
        message.success('分析完成')
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setRunning(false)
    }
  }

  const handleRunCode = async () => {
    if (!code.trim()) {
      message.warning('请输入要执行的代码')
      return
    }
    setCodeRunning(true)
    setCodeResult(null)
    try {
      const res = await runResearchCode(code)
      if (res?.result_id) {
        setCodeResult(res)
        message.success('执行完成')
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setCodeRunning(false)
    }
  }

  const addMaterial = (result) => {
    if (materials.some((m) => m.result_id === result.result_id)) return
    setMaterials([...materials, { result_id: result.result_id, skill_name: result.skill_name || '自定义代码' }])
    message.success('已加入论文素材')
  }

  const handleRecommend = async () => {
    if (!question.trim()) {
      message.warning('请先填写研究问题')
      return
    }
    setRecommending(true)
    setRecommendation(null)
    try {
      const res = await recommendResearch(question)
      if (res) setRecommendation(res)
    } catch {
      // 拦截器已统一报错
    } finally {
      setRecommending(false)
    }
  }

  const handleSearchLiterature = async () => {
    if (!litQuery.trim()) {
      message.warning('请输入检索关键词')
      return
    }
    setSearching(true)
    try {
      const res = await searchLiterature({ query: litQuery, max_results: 10 })
      if (res) {
        setArticles(res.articles || [])
        setLitSummary(res.summary || '')
        setCheckedPmids([])
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setSearching(false)
    }
  }

  const handleGeneratePaper = async () => {
    if (!question.trim()) {
      message.warning('请先填写研究问题')
      return
    }
    setGenerating(true)
    setPaper(null)
    try {
      const res = await generatePaper({
        question,
        result_ids: materials.map((m) => m.result_id),
        articles: articles.filter((a) => checkedPmids.includes(a.pmid)),
        title: paperTitle.trim() || undefined,
      })
      if (res?.paper) {
        setPaper(res.paper)
        setPaperFile({ filename: res.filename, download_url: res.download_url })
        message.success('论文生成完成')
      }
    } catch {
      // 拦截器已统一报错
    } finally {
      setGenerating(false)
    }
  }

  const handleDownload = () => {
    if (!paperFile) return
    let url = paperFile.download_url || ''
    if (!url && paperFile.filename) url = `/research/paper/download/${paperFile.filename}`
    if (url && !url.startsWith('/api')) url = `/api${url.startsWith('/') ? '' : '/'}${url}`
    if (url) window.open(url, '_blank')
  }

  // ---------- 第一步：数据资产 ----------
  const renderAssets = () => {
    if (assetsLoading) return <Skeleton active />
    if (!assets) return <Empty description="未获取到数据资产信息" />
    const graph = assets.graph || {}
    return (
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Alert type="info" showIcon message="系统已检测到以下可用于科研的数据类型" />
        </Col>
        <Col span={24}>
          <Card title={<><DatabaseOutlined /> 表格数据</>}>
            <Table
              size="small"
              columns={[
                { title: '表名', dataIndex: 'name' },
                { title: '行数', dataIndex: 'rows' },
                { title: '列数', dataIndex: 'cols' },
                {
                  title: '关键字段', dataIndex: 'key_columns',
                  render: (v) => (v || []).map((c) => <Tag key={c}>{c}</Tag>),
                },
                { title: '覆盖说明', dataIndex: 'coverage_note' },
              ]}
              dataSource={(assets.tables || []).map((t, i) => ({ ...t, __key: i }))}
              rowKey="__key"
              pagination={false}
            />
          </Card>
        </Col>
        <Col span={24} md={8}>
          <Card title={<><ApartmentOutlined /> 图谱数据</>}>
            {graph.available ? (
              <>
                <Statistic title="状态" value="可用" valueStyle={{ color: '#3f8600', fontSize: 20 }} />
                <Title level={5} style={{ marginTop: 16 }}>节点统计</Title>
                <KeyValueList data={graph.node_stats} />
                <Title level={5}>关系统计</Title>
                <KeyValueList data={graph.rel_stats} />
              </>
            ) : (
              <Alert type="warning" showIcon message="图谱数据不可用" description={graph.error || '知识图谱服务未连接'} />
            )}
          </Card>
        </Col>
        <Col span={24} md={8}>
          <Card title={<><FileTextOutlined /> 文本数据</>}>
            <KeyValueList data={assets.text_data} />
          </Card>
        </Col>
        <Col span={24} md={8}>
          <Card title={<><CloudServerOutlined /> 向量库</>}>
            <KeyValueList data={assets.vector_db} />
          </Card>
        </Col>
      </Row>
    )
  }

  // ---------- 第二步：分析 Skills ----------
  const renderSkills = () => {
    const menuItems = categories.map((c) => ({
      key: c.category,
      type: 'group',
      label: c.category,
      children: (c.skills || []).map((s) => ({
        key: s.id,
        label: (
          <Tooltip placement="right" title={`${s.description || ''}${s.data_requirements ? `\n数据要求：${s.data_requirements}` : ''}`}>
            <span>{s.name}</span>
          </Tooltip>
        ),
      })),
    }))
    return (
      <Row gutter={[16, 16]}>
        <Col span={24} md={7} lg={6}>
          <Card title="分析 Skills" loading={skillsLoading}>
            <Menu
              mode="inline"
              items={menuItems}
              selectedKeys={activeSkill ? [activeSkill.id] : []}
              onClick={({ key }) => {
                const skill = allSkills.find((s) => s.id === key)
                if (skill) selectSkill(skill)
              }}
              style={{ border: 'none' }}
            />
          </Card>
        </Col>
        <Col span={24} md={17} lg={18}>
          {!activeSkill ? (
            <Card><Empty description="请从左侧选择一个分析 Skill" /></Card>
          ) : (
            <>
              <Card title={activeSkill.name}>
                {activeSkill.description && (
                  <Paragraph type="secondary">{activeSkill.description}</Paragraph>
                )}
                <Form layout="vertical">
                  <Row gutter={16}>
                    {(activeSkill.params_schema || []).map((p) => (
                      <Col span={24} md={12} key={p.name}>
                        <Form.Item label={p.label || p.name} tooltip={p.description}>
                          <ParamField
                            schema={p}
                            value={params[p.name]}
                            onChange={(v) => setParams({ ...params, [p.name]: v })}
                          />
                        </Form.Item>
                      </Col>
                    ))}
                  </Row>
                </Form>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={running}
                  onClick={handleRunSkill}
                >
                  运行
                </Button>
              </Card>
              <ResultView
                result={skillResult}
                onAddMaterial={addMaterial}
                added={skillResult && materials.some((m) => m.result_id === skillResult.result_id)}
              />
            </>
          )}
        </Col>
      </Row>
    )
  }

  // ---------- 第三步：自定义代码 ----------
  const renderCode = () => (
    <>
      <Alert
        type="warning"
        showIcon
        message="实验性功能：在受限环境中执行 pandas 代码，仅面向受信任用户"
        style={{ marginBottom: 16 }}
      />
      <Card title="代码编辑器">
        <TextArea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={10}
          style={{ fontFamily: 'monospace' }}
        />
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={codeRunning}
          onClick={handleRunCode}
          style={{ marginTop: 12 }}
        >
          运行
        </Button>
      </Card>
      <ResultView
        result={codeResult}
        onAddMaterial={addMaterial}
        added={codeResult && materials.some((m) => m.result_id === codeResult.result_id)}
      />
    </>
  )

  // ---------- 第四步：论文生成 ----------
  const renderPaper = () => (
    <Row gutter={[16, 16]}>
      <Col span={24}>
        <Card title="研究问题">
          <TextArea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            placeholder="例如：化疗方案对血液肿瘤患者再入院率的影响"
          />
          <Space style={{ marginTop: 12 }}>
            <Button icon={<RobotOutlined />} loading={recommending} onClick={handleRecommend}>
              AI 推荐分析路径
            </Button>
          </Space>
          {recommendation && (
            <Alert
              type="info"
              showIcon
              style={{ marginTop: 12 }}
              message="推荐分析路径"
              description={
                <>
                  <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{recommendation.recommendation}</Paragraph>
                  {(recommendation.suggested_skills || []).length > 0 && (
                    <div>
                      推荐 Skills：
                      {recommendation.suggested_skills.map((id) => (
                        <Tag key={id} color="blue">{skillNameOf(id)}</Tag>
                      ))}
                    </div>
                  )}
                </>
              }
            />
          )}
        </Card>
      </Col>
      <Col span={24}>
        <Card title="文献检索">
          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={litQuery}
              onChange={(e) => setLitQuery(e.target.value)}
              placeholder="输入检索关键词（PubMed）"
              onPressEnter={handleSearchLiterature}
            />
            <Button type="primary" icon={<SearchOutlined />} loading={searching} onClick={handleSearchLiterature}>
              检索
            </Button>
          </Space.Compact>
          {litSummary && (
            <Alert type="info" showIcon message="文献综述" description={litSummary} style={{ marginTop: 12 }} />
          )}
          <List
            style={{ marginTop: 12 }}
            loading={searching}
            dataSource={articles}
            locale={{ emptyText: '暂无文献，请先检索' }}
            renderItem={(a) => (
              <List.Item>
                <Checkbox
                  checked={checkedPmids.includes(a.pmid)}
                  onChange={(e) => {
                    setCheckedPmids(e.target.checked
                      ? [...checkedPmids, a.pmid]
                      : checkedPmids.filter((p) => p !== a.pmid))
                  }}
                  style={{ marginRight: 12 }}
                />
                <List.Item.Meta
                  title={<>{a.title} <Tag>{a.journal} {a.year}</Tag></>}
                  description={
                    <>
                      <div>{(a.authors || []).join(', ')}</div>
                      <Paragraph ellipsis={{ rows: 2 }} type="secondary" style={{ marginBottom: 0 }}>
                        {a.abstract}
                      </Paragraph>
                    </>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      </Col>
      <Col span={24}>
        <Card title="生成论文">
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              已选素材：
              {materials.length === 0 ? <Text type="secondary">暂无（可在第二、三步结果区加入）</Text> : (
                materials.map((m) => (
                  <Tag
                    key={m.result_id}
                    closable
                    onClose={() => setMaterials(materials.filter((x) => x.result_id !== m.result_id))}
                  >
                    {m.skill_name}
                  </Tag>
                ))
              )}
              <Tag color="blue">已勾选文献 {checkedPmids.length} 篇</Tag>
            </div>
            <Input
              value={paperTitle}
              onChange={(e) => setPaperTitle(e.target.value)}
              placeholder="论文标题（可选，留空由 AI 拟定）"
            />
            <Button type="primary" loading={generating} onClick={handleGeneratePaper}>
              生成论文
            </Button>
          </Space>
        </Card>
      </Col>
      {paper && (
        <Col span={24}>
          <Card
            title={paper.title || '生成的论文'}
            extra={
              <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownload}>
                下载 Word 文档
              </Button>
            }
          >
            <div style={{ maxHeight: 600, overflow: 'auto' }}>
              <Typography>
                {PAPER_SECTIONS.map(([key, label]) => (
                  paper.sections?.[key] ? (
                    <div key={key}>
                      <Title level={4}>{label}</Title>
                      <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{paper.sections[key]}</Paragraph>
                    </div>
                  ) : null
                ))}
              </Typography>
            </div>
          </Card>
        </Col>
      )}
    </Row>
  )

  const stepContents = [renderAssets, renderSkills, renderCode, renderPaper]

  return (
    <div>
      <Card
        title="科研助手"
        extra={<Tag color="blue">已选论文素材：{materials.length} 项</Tag>}
        style={{ marginBottom: 16 }}
      >
        <Steps
          current={step}
          items={[
            { title: '数据资产' },
            { title: '分析 Skills' },
            { title: '自定义代码' },
            { title: '论文生成' },
          ]}
        />
      </Card>
      <Card style={{ marginBottom: 16 }}>
        {stepContents[step]()}
      </Card>
      <div style={{ textAlign: 'right' }}>
        {step > 0 && (
          <Button style={{ marginRight: 8 }} onClick={() => setStep(step - 1)}>上一步</Button>
        )}
        {step < 3 && (
          <Button type="primary" onClick={() => setStep(step + 1)}>下一步</Button>
        )}
      </div>
    </div>
  )
}

export default function ResearchAssistantView() {
  return (
    <Tabs
      defaultActiveKey="smart"
      size="large"
      items={[
        { key: 'smart', label: '智能模式', children: <SmartModePanel /> },
        { key: 'expert', label: '专家模式', children: <ExpertModePanel /> },
      ]}
    />
  )
}
