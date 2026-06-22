import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, Switch, Popconfirm, message, Tag, Space } from 'antd'
import { getUsers, createUser, updateUser, deleteUser, getRoles } from '../../api/index.js'

const ROLE_OPTIONS = [
  { value: 'admin', label: '系统管理员' },
  { value: 'hospital_manager', label: '医务部/院领导' },
  { value: 'department_manager', label: '科室主任' },
  { value: 'quality_controller', label: '质控员' },
  { value: 'attending_doctor', label: '主治医师' },
  { value: 'resident_doctor', label: '住院医师' },
  { value: 'doctor', label: '医生' },
  { value: 'researcher', label: '科研人员' },
  { value: 'viewer', label: '只读用户' },
]

export default function UserManagementView() {
  const [loading, setLoading] = useState(false)
  const [users, setUsers] = useState([])
  const [visible, setVisible] = useState(false)
  const [form] = Form.useForm()
  const [editingId, setEditingId] = useState(null)

  const columns = [
    { title: '用户名', dataIndex: 'username' },
    { title: '姓名', dataIndex: 'name' },
    {
      title: '角色',
      dataIndex: 'roles',
      render: (roles) => (
        <Space wrap>
          {(roles || []).map((r) => {
            const opt = ROLE_OPTIONS.find((o) => o.value === r)
            return <Tag color="blue" key={r}>{opt?.label || r}</Tag>
          })}
        </Space>
      ),
    },
    { title: '科室', dataIndex: 'department' },
    { title: '状态', dataIndex: 'status', render: (v) => v ? '启用' : '禁用' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <>
          <Button type="link" onClick={() => showModal(record)}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={() => removeUser(record.id)}>
            <Button type="link" danger>删除</Button>
          </Popconfirm>
        </>
      ),
    },
  ]

  const loadUsers = async () => {
    setLoading(true)
    try {
      const data = await getUsers()
      setUsers(data)
    } finally {
      setLoading(false)
    }
  }

  const showModal = (record) => {
    setEditingId(record?.id || null)
    form.setFieldsValue({
      username: record?.username || '',
      name: record?.name || '',
      role_codes: record?.roles || [],
      department: record?.department || '',
      status: record ? record.status === 1 : true,
    })
    setVisible(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    const payload = { ...values, status: values.status ? 1 : 0 }
    if (editingId) {
      await updateUser(editingId, payload)
    } else {
      await createUser(payload)
    }
    message.success('保存成功')
    setVisible(false)
    await loadUsers()
  }

  const removeUser = async (id) => {
    await deleteUser(id)
    message.success('删除成功')
    await loadUsers()
  }

  useEffect(() => {
    loadUsers()
  }, [])

  return (
    <Card>
      <Button type="primary" onClick={() => showModal()} style={{ marginBottom: 16 }}>新增用户</Button>
      <Table columns={columns} dataSource={users} rowKey="id" loading={loading} />
      <Modal open={visible} title={editingId ? '编辑用户' : '新增用户'} onOk={submit} onCancel={() => setVisible(false)}>
        <Form form={form} labelCol={{ span: 6 }} wrapperCol={{ span: 16 }}>
          <Form.Item label="用户名" name="username" rules={[{ required: true }]}>
            <Input disabled={!!editingId} />
          </Form.Item>
          {!editingId && (
            <Form.Item label="密码" name="password" rules={[{ required: true }]}>
              <Input.Password />
            </Form.Item>
          )}
          <Form.Item label="姓名" name="name">
            <Input />
          </Form.Item>
          <Form.Item label="角色" name="role_codes" rules={[{ required: true }]}>
            <Select mode="multiple" options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item label="科室" name="department">
            <Input />
          </Form.Item>
          <Form.Item label="状态" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
