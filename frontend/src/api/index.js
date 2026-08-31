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

// 科研助手：LLM 长调用单独放宽超时（全局默认 60s 不够）
export const getResearchDataAssets = () => request.get('/research/data-assets')
export const getResearchSkills = () => request.get('/research/skills')
export const runResearchSkill = (skillId, params) => request.post(`/research/skills/${skillId}/run`, { params }, { timeout: 300000 })
export const getResearchResult = (resultId) => request.get(`/research/results/${resultId}`)
export const runResearchCode = (code) => request.post('/research/code/run', { code }, { timeout: 120000 })
export const recommendResearch = (question) => request.post('/research/recommend', { question }, { timeout: 180000 })
export const interpretResearchResult = (resultId) => request.post('/research/interpret', { result_id: resultId }, { timeout: 180000 })
export const searchLiterature = (data) => request.post('/research/literature/search', data, { timeout: 180000 })
export const generatePaper = (data) => request.post('/research/paper/generate', data, { timeout: 600000 })

export const proposeResearchTopics = (data = {}) => request.post('/research/auto/topics', data, { timeout: 300000 })
export const startAutoResearch = (topic) => request.post('/research/auto/start', { topic }, { timeout: 60000 })
export const getAutoResearchJob = (jobId) => request.get(`/research/auto/${jobId}`)
export const getAutoResearchHistory = () => request.get('/research/auto/history')
export const evaluateCustomTopic = (idea) => request.post('/research/auto/topics/custom', { idea }, { timeout: 300000 })
