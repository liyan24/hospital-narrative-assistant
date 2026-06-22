import { useEffect, useState } from 'react'
import { Card, Form, Switch, Button, message, Divider } from 'antd'
import { getFeatures, updateFeatures } from '../../api/index.js'
import { useAuthStore } from '../../stores/auth.jsx'

const featureGroups = [
  {
    title: '核心诊疗模块',
    items: [
      { code: 'patient_holographic', label: '患者全息视图' },
      { code: 'ward_round', label: '查房助手' },
      { code: 'daily_briefing', label: '科室晨会简报' },
      { code: 'rag_qa', label: 'RAG 问答' },
      { code: 'report_generation', label: '智能报告生成' },
    ],
  },
  {
    title: '辅助决策与科研',
    items: [
      { code: 'risk_prediction', label: '风险预警' },
      { code: 'similar_patient', label: '相似患者推荐' },
      { code: 'pathway', label: '诊疗路径推荐' },
      { code: 'quality_control', label: '质控闭环管理' },
      { code: 'kg_visualization', label: '知识图谱可视化' },
      { code: 'tcm_analysis', label: '中医辨证' },
      { code: 'research_export', label: '科研导出' },
    ],
  },
]

export default function FeatureSwitchesView() {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const authStore = useAuthStore()

  const load = async () => {
    const data = await getFeatures()
    form.setFieldsValue(data)
  }

  const save = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      await updateFeatures(values)
      message.success('保存成功')
      await authStore.refreshFeatures()
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <Card>
      <Form form={form} labelCol={{ span: 8 }} wrapperCol={{ span: 16 }}>
        {featureGroups.map((group) => (
          <div key={group.title}>
            <Divider orientation="left">{group.title}</Divider>
            {group.items.map((item) => (
              <Form.Item key={item.code} label={item.label} name={item.code} valuePropName="checked">
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>
            ))}
          </div>
        ))}
        <Form.Item wrapperCol={{ offset: 8 }}>
          <Button type="primary" onClick={save} loading={saving}>保存</Button>
        </Form.Item>
      </Form>
    </Card>
  )
}
