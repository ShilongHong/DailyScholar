import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

// ===== Papers =====
export const fetchPapers = (params) => api.get('/papers', { params })
export const fetchPaperByDoi = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/detail`)
export const fetchPaperStats = () => api.get('/papers/stats')
export const confirmFilters = (filters) => api.post('/papers/filters/confirm', filters)
export const getConfirmedFilters = () => api.get('/papers/filters/confirmed')
export const togglePaperMark = (doi, marked) => api.post('/papers/mark', { doi, marked })
export const updatePaperComment = (doi, comment) => api.post('/papers/comment', { doi, comment })
export const deletePaper = (doi) => api.delete(`/papers/${encodeURIComponent(doi)}`)
export const retranslatePaper = (doi) => api.post(`/papers/${encodeURIComponent(doi)}/retranslate`)

// ===== Queue =====
export const fetchQueueStatus = () => api.get('/queue/status')

// ===== Logs =====
export const fetchLogFiles = () => api.get('/logs/list')
export const fetchLogContent = (params) => api.get('/logs/content', { params })

// ===== Config =====
export const fetchAllConfig = () => api.get('/config/all')
export const saveConfig = (section, config) => api.put(`/config/${section}`, { config })
export const saveResearchDescription = (content) => api.put('/config/research_description', { config: { content } })

// ===== Prompts =====
export const fetchPrompts = () => api.get('/prompts')
export const savePrompt = (key, content) => api.put(`/prompts/${key}`, { content })
export const resetPrompt = (key) => api.post(`/prompts/${key}/reset`)

// ===== Actions =====
export const triggerFetch = () => api.post('/actions/fetch-now')
export const triggerProcess = () => api.post('/actions/process-now')
export const triggerPush = () => api.post('/actions/push-now')

// ===== Scheduler =====
export const fetchSchedulerStatus = () => api.get('/scheduler/status')
export const reloadScheduler = () => api.post('/scheduler/reload')

// ===== Setup / Wizard =====
export const fetchSetupStatus = () => api.get('/setup/status')
export const testDBConnection = (config) => api.post('/setup/test-db', config)
export const testLLMConnection = (config) => api.post('/setup/test-llm', config)
export const testNotifyChannel = (channel, config) => api.post('/setup/test-notify', { channel, config })
export const generateResearch = (brief) => api.post('/setup/generate-research', { brief })
export const completeSetup = () => api.post('/setup/complete')
export const fetchExistingConfig = () => api.get('/setup/existing-config')
export const resetSetup = () => api.delete('/setup/reset')

// ===== Paper Reader =====
export const fetchPaperPdf = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/pdf`, { responseType: 'blob' })
export const convertPaperToMarkdown = (doi, mode = 'cloud') => api.post(`/papers/${encodeURIComponent(doi)}/convert`, { mode })
export const fetchConvertStatus = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/convert/status`)
export const fetchPaperMarkdown = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/markdown`)
export const fetchAnnotations = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/annotations`)
export const saveAnnotations = (doi, annotations) => api.post(`/papers/${encodeURIComponent(doi)}/annotations`, { annotations })
export const translateFullPaper = (doi, source = 'markdown', force = false) =>
  api.post(`/papers/${encodeURIComponent(doi)}/translate-full`, { source, force })
export const fetchTranslateFullStatus = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/translate-full/status`)
export const getTranslateFullStreamUrl = (doi) => `/api/papers/${encodeURIComponent(doi)}/translate-full/stream`

// ===== Chat (论文精读对话) =====
export const sendChatMessage = (doi, message) =>
  fetch(`/api/papers/${encodeURIComponent(doi)}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })
export const fetchChatHistory = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/chat/history`)
export const clearChatHistory = (doi) => api.delete(`/papers/${encodeURIComponent(doi)}/chat`)
export const fetchChatSuggestions = (doi) => api.get(`/papers/${encodeURIComponent(doi)}/chat/suggestions`)

// ===== Health =====
export const fetchHealth = () => api.get('/health')

export default api
