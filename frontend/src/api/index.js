import request from './request.js'

export const login = (data) => request.post('/auth/login', data)
export const getMe = () => request.get('/auth/me')

export const getPatients = (params) => request.get('/data/patients', { params })
export const searchPatients = (keyword) => request.get('/data/patients/search', { params: { keyword } })

export const getPatientStoryline = (patientId) => request.get(`/narrative/patient/storyline/${patientId}`)
export const getPatientQuality = (patientId) => request.get(`/narrative/patient/${patientId}/quality-control`)
export const getPatientRisk = (patientId) => request.get('/narrative/risk-prediction', { params: { patient_id: patientId } })
export const getPatientReadmission = (patientId) => request.get(`/narrative/readmission/patient/${patientId}`)
export const getSimilarPatients = (patientId) => request.get(`/narrative/similar-patients/${patientId}`)
export const getPathway = (diseaseName) => request.get(`/narrative/pathway/${encodeURIComponent(diseaseName)}`)

export const askRag = (data) => request.post('/narrative/rag/ask', data)

export const getDailyBriefing = (date) => request.get('/daily/briefing', { params: { date } })
export const generateDailyBriefing = (date) => request.post('/daily/briefing/generate', null, { params: { date } })

export const getDepartmentOperation = (params) => request.get('/narrative/department-operation', { params })
export const generateDepartmentOperation = (data) => request.post('/narrative/department-operation', data)

export const getLatestReports = () => request.get('/narrative/reports/latest')
export const getReport = (reportId) => request.get(`/narrative/report/${reportId}`)
export const generateReport = (data) => request.post('/narrative/report/generate', data)

export const getKgStats = () => request.get('/kg/stats')
export const getKgVisualization = () => request.get('/kg/visualization')

export const getCacheSummary = () => request.get('/narrative/cache/stats')
export const clearCache = (params) => request.post('/narrative/cache/clear-all', params)

export const getUsers = () => request.get('/admin/users')
export const createUser = (data) => request.post('/admin/users', data)
export const updateUser = (id, data) => request.put(`/admin/users/${id}`, data)
export const deleteUser = (id) => request.delete(`/admin/users/${id}`)
export const getRoles = () => request.get('/admin/roles')
export const getPermissions = () => request.get('/admin/permissions')
export const updateRolePermissions = (roleId, data) => request.put(`/admin/roles/${roleId}/permissions`, data)

export const getFeatures = () => request.get('/admin/features')
export const updateFeatures = (data) => request.put('/admin/features', data)

export const getConfig = () => request.get('/admin/config')
export const updateConfig = (data) => request.put('/admin/config', data)
