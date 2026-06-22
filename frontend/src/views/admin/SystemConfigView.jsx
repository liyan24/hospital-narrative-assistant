import { useEffect, useState } from 'react'
import { Card, Form, Input, InputNumber, Button, message } from 'antd'
import { getConfig, updateConfig } from '../../api/index.js'

export default function SystemConfigView() {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const load = async () => {
    const data = await getConfig()
    form.setFieldsValue(data)
  }

  const save = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      await updateConfig(values)
      message.success('保存成功')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <Card>
      <Form form={form} labelCol={{ span: 6 }} wrapperCol={{ span: 16 }}>
        <Form.Item label="LLM 模型" name="llm_model">
          <Input placeholder="例如 moonshot-v1-32k" />
        </Form.Item>
        <Form.Item label="Temperature" name="temperature">
          <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="缓存 TTL(小时)" name="cache_ttl_hours">
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="默认科室" name="default_department">
          <Input />
        </Form.Item>
        <Form.Item wrapperCol={{ offset: 6 }}>
          <Button type="primary" onClick={save} loading={saving}>保存</Button>
        </Form.Item>
      </Form>
    </Card>
  )
}
