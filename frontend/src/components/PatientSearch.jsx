import { useState, useEffect } from 'react'
import { Select, Spin } from 'antd'
import { searchPatients } from '../api/index.js'

export default function PatientSearch({ value, onChange, style }) {
  const [options, setOptions] = useState([])
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    if (value && options.length === 0) {
      searchPatients(value).then((res) => {
        const list = res.patients || res || []
        const found = list.find((p) => p.patient_id === value)
        if (found) {
          setOptions([{
            value: found.patient_id,
            label: `${found.patient_id} ${found.name || ''} ${found.medical_record_no || ''}`,
          }])
        }
      }).catch(() => {})
    }
  }, [value])

  const handleSearch = async (keyword) => {
    if (!keyword || keyword.length < 2) {
      setOptions([])
      return
    }
    setFetching(true)
    try {
      const res = await searchPatients(keyword)
      const list = res.patients || res || []
      setOptions(list.map((p) => ({
        value: p.patient_id,
        label: `${p.patient_id} ${p.name || ''} ${p.medical_record_no || ''}`,
      })))
    } catch {
      setOptions([])
    } finally {
      setFetching(false)
    }
  }

  return (
    <Select
      showSearch
      allowClear
      placeholder="搜索患者ID / 姓名 / 病案号"
      value={value}
      onChange={onChange}
      onSearch={handleSearch}
      notFoundContent={fetching ? <Spin size="small" /> : '输入关键词搜索'}
      filterOption={false}
      style={{ width: '100%', ...style }}
      options={options}
    />
  )
}
