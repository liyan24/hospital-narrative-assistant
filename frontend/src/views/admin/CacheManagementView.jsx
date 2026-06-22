import { useEffect, useState } from 'react'
import { Row, Col, Card, Select, Button, Skeleton, message } from 'antd'
import { getCacheSummary, clearCache } from '../../api/index.js'

export default function CacheManagementView() {
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [summary, setSummary] = useState(null)
  const [namespace, setNamespace] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await getCacheSummary()
      setSummary(data)
    } finally {
      setLoading(false)
    }
  }

  const clearNamespace = async () => {
    if (!namespace) return
    setClearing(true)
    try {
      await clearCache({ namespace })
      message.success('清理成功')
      setNamespace(null)
      await load()
    } finally {
      setClearing(false)
    }
  }

  const clearAll = async () => {
    setClearing(true)
    try {
      await clearCache({ all: true })
      message.success('全部缓存已清理')
      await load()
    } finally {
      setClearing(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <Row gutter={[16, 16]}>
      <Col span={24} lg={12}>
        <Card title="缓存概览">
          <Skeleton loading={loading}>
            <p><strong>命名空间数：</strong>{summary?.namespaces?.length || 0}</p>
            <p><strong>总条目数：</strong>{summary?.total_entries || 0}</p>
            <p><strong>总大小：</strong>{summary?.total_size_mb?.toFixed(2) || 0} MB</p>
          </Skeleton>
        </Card>
      </Col>
      <Col span={24} lg={12}>
        <Card title="清理缓存">
          <Select
            placeholder="选择命名空间"
            allowClear
            style={{ width: '100%', marginBottom: 16 }}
            value={namespace}
            onChange={setNamespace}
            options={(summary?.namespaces || []).map((ns) => ({ value: ns, label: ns }))}
          />
          <Button danger onClick={clearNamespace} loading={clearing} style={{ marginRight: 8 }}>按命名空间清理</Button>
          <Button danger onClick={clearAll} loading={clearing}>清理全部缓存</Button>
        </Card>
      </Col>
    </Row>
  )
}
