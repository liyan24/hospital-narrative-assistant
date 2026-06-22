import { Link } from 'react-router-dom'
import { Button } from 'antd'
import { FileSearchOutlined } from '@ant-design/icons'

export default function PatientIdLink({ patientId, showIcon = true, children }) {
  if (!patientId) return '-'
  return (
    <Link to={`/portal/patient/${patientId}`}>
      <Button type="link" size="small" style={{ padding: 0 }}>
        {showIcon && <FileSearchOutlined style={{ marginRight: 4 }} />}
        {children || patientId}
      </Button>
    </Link>
  )
}
