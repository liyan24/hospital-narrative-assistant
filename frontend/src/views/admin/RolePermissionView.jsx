import { useEffect, useState } from 'react'
import { Card, Table, Transfer, Button, message, Tag, Spin } from 'antd'
import { getRoles, getPermissions, updateRolePermissions } from '../../api/index.js'

export default function RolePermissionView() {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [roles, setRoles] = useState([])
  const [permissions, setPermissions] = useState([])
  const [selectedRole, setSelectedRole] = useState(null)
  const [targetKeys, setTargetKeys] = useState([])

  const normalizePermissions = (role) => {
    if (!role || !role.permissions) return []
    return role.permissions.map((p) => (typeof p === 'string' ? p : p.permission_code))
  }

  const loadData = async () => {
    setLoading(true)
    try {
      const [rolesData, permsData] = await Promise.all([getRoles(), getPermissions()])
      const list = rolesData || []
      setRoles(list)
      setPermissions(permsData || [])
      if (list.length > 0 && !selectedRole) {
        handleSelectRole(list[0])
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSelectRole = (role) => {
    setSelectedRole(role)
    setTargetKeys(normalizePermissions(role))
  }

  const handleSave = async () => {
    if (!selectedRole) return
    setSaving(true)
    try {
      await updateRolePermissions(selectedRole.id, { permission_codes: targetKeys })
      message.success('角色权限保存成功')
      await loadData()
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const columns = [
    { title: '角色编码', dataIndex: 'role_code' },
    { title: '角色名称', dataIndex: 'role_name' },
    { title: '描述', dataIndex: 'description' },
    {
      title: '当前权限',
      dataIndex: 'permissions',
      render: (_, record) => {
        const perms = normalizePermissions(record)
        return (
          <span>
            {perms.slice(0, 4).map((p) => (
              <Tag color="blue" key={p}>{p}</Tag>
            ))}
            {perms.length > 4 && <Tag>+{perms.length - 4}</Tag>}
          </span>
        )
      },
    },
  ]

  return (
    <Spin spinning={loading}>
      <Card>
        <p>选择角色后，在右侧勾选该角色拥有的权限，点击保存生效。</p>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={roles}
          pagination={false}
          rowClassName={(record) => (selectedRole?.id === record.id ? 'ant-table-row-selected' : '')}
          onRow={(record) => ({
            onClick: () => handleSelectRole(record),
            style: { cursor: 'pointer' },
          })}
          size="small"
        />

        {selectedRole && (
          <div style={{ marginTop: 24 }}>
            <h4>编辑权限：{selectedRole.role_name}（{selectedRole.role_code}）</h4>
            <Transfer
              dataSource={(permissions || []).map((p) => ({
                key: p.permission_code,
                title: `${p.permission_name} (${p.permission_code})`,
                description: p.description,
              }))}
              titles={['可用权限', '已授权限']}
              targetKeys={targetKeys}
              onChange={setTargetKeys}
              render={(item) => item.title}
              listStyle={{ width: '48%', height: 360 }}
              oneWay
            />
            <Button type="primary" onClick={handleSave} loading={saving} style={{ marginTop: 16 }}>
              保存权限配置
            </Button>
          </div>
        )}
      </Card>
    </Spin>
  )
}
