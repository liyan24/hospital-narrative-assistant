import { useEffect, useState } from 'react'
import { Row, Col, Card, Skeleton, Badge } from 'antd'
import { getKgStats, getCacheSummary } from '../../api/index.js'

export default function DashboardView() {
  const [loading, setLoading] = useState(false)
  const [cacheLoading, setCacheLoading] = useState(false)
  const [kgStats, setKgStats] = useState(null)
  const [cacheStats, setCacheStats] = useState(null)

  const nodeCount = kgStats?.nodes
    ? Object.values(kgStats.nodes).reduce((a, b) => a + (Number(b) || 0), 0)
    : 0
  const relationshipCount = kgStats?.relationships
    ? Object.values(kgStats.relationships).reduce((a, b) => a + (Number(b) || 0), 0)
    : 0
  const labelCount = kgStats?.nodes ? Object.keys(kgStats.nodes).length : 0

  const cacheSummary = cacheStats?.stats || cacheStats || {}
  const cacheEntries = cacheSummary.total_entries || 0
  const cacheSize = cacheSummary.total_size_mb ?? 0
  const buildTime = new Date().toLocaleString()

  useEffect(() => {
    setLoading(true)
    getKgStats().then(setKgStats).finally(() => setLoading(false))

    setCacheLoading(true)
    getCacheSummary().then(setCacheStats).finally(() => setCacheLoading(false))
  }, [])

  return (
    <Row gutter={[16, 16]}>
      <Col span={24} lg={8}>
        <Card title="知识图谱统计">
          <Skeleton loading={loading}>
            <p><strong>节点数：</strong>{nodeCount}</p>
            <p><strong>关系数：</strong>{relationshipCount}</p>
            <p><strong>标签数：</strong>{labelCount}</p>
          </Skeleton>
        </Card>
      </Col>
      <Col span={24} lg={8}>
        <Card title="LLM 缓存">
          <Skeleton loading={cacheLoading}>
            <p><strong>缓存条目：</strong>{cacheEntries}</p>
            <p><strong>总大小：</strong>{Number(cacheSize).toFixed(2)} MB</p>
          </Skeleton>
        </Card>
      </Col>
      <Col span={24} lg={8}>
        <Card title="系统状态">
          <p><strong>后端服务：</strong><Badge status="success" text="运行中" /></p>
          <p><strong>前端版本：</strong>v0.1.0</p>
          <p><strong>构建时间：</strong>{buildTime}</p>
        </Card>
      </Col>
    </Row>
  )
}
