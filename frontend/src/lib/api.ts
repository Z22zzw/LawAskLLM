import axios from 'axios'

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          err.config.headers.Authorization = `Bearer ${data.access_token}`
          return api.request(err.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      } else {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

// ── Auth ──
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }).then(r => r.data),
  register: (body: object) => api.post('/auth/register', body).then(r => r.data),
  me: () => api.get('/auth/me').then(r => r.data),
}

// ── Chat ──
export const chatApi = {
  listSessions: () => api.get('/chat/sessions').then(r => r.data),
  createSession: (body: object) => api.post('/chat/sessions', body).then(r => r.data),
  updateSession: (uuid: string, body: object) => api.patch(`/chat/sessions/${uuid}`, body).then(r => r.data),
  deleteSession: (uuid: string) => api.delete(`/chat/sessions/${uuid}`),
  listMessages: (uuid: string) => api.get(`/chat/sessions/${uuid}/messages`).then(r => r.data),
  getCitations: (msgId: number) => api.get(`/chat/messages/${msgId}/citations`).then(r => r.data),
}

// ── Knowledge ──
export const kbApi = {
  list: () => api.get('/knowledge-bases').then(r => r.data),
  create: (body: object) => api.post('/knowledge-bases', body).then(r => r.data),
  get: (id: number) => api.get(`/knowledge-bases/${id}`).then(r => r.data),
  update: (id: number, body: object) => api.patch(`/knowledge-bases/${id}`, body).then(r => r.data),
  delete: (id: number) => api.delete(`/knowledge-bases/${id}`),
  /** 保留知识库与文档，仅清空 Chroma 向量与块记录 */
  clearVectorData: (id: number) => api.post(`/knowledge-bases/${id}/vector/clear`).then(() => undefined),
  listDocs: (id: number) => api.get(`/knowledge-bases/${id}/documents`).then(r => r.data),
  uploadDoc: (id: number, file: File, splitRole: 'train' | 'test' = 'train') => {
    const fd = new FormData(); fd.append('file', file); fd.append('split_role', splitRole)
    return api.post(`/knowledge-bases/${id}/documents`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
  deleteDoc: (kbId: number, docId: number) => api.delete(`/knowledge-bases/${kbId}/documents/${docId}`),
  vectorStats: () => api.get('/knowledge-bases/vector/stats').then(r => r.data),
  startIndex: (kbId: number) => api.post(`/knowledge-bases/${kbId}/index/start`).then(r => r.data),
  indexJobStatus: (kbId: number, jobId: string) =>
    api.get(`/knowledge-bases/${kbId}/index/jobs/${jobId}`).then(r => r.data),
}

export const datasetBuildApi = {
  options: () => api.get('/dataset-build/options').then(r => r.data),
  run: (body: object) => api.post('/dataset-build/run', body).then(r => r.data),
  jobStatus: (jobId: string) => api.get(`/dataset-build/jobs/${jobId}`).then(r => r.data),
}

// ── Users ──
export const userApi = {
  list: () => api.get('/users').then(r => r.data),
  create: (body: object) => api.post('/users', body).then(r => r.data),
  update: (id: number, body: object) => api.patch(`/users/${id}`, body).then(r => r.data),
  delete: (id: number) => api.delete(`/users/${id}`),
  listRoles: () => api.get('/roles').then(r => r.data),
  createRole: (body: object) => api.post('/roles', body).then(r => r.data),
  updateRole: (id: number, body: object) => api.patch(`/roles/${id}`, body).then(r => r.data),
  listPermissions: () => api.get('/permissions').then(r => r.data),
}

// ── SSE chat completion ──
export function streamCompletion(
  body: {
    session_uuid: string
    question: string
    legal_domain?: string
    kb_ids?: number[] | null
    top_k?: number
  },
  handlers: {
    onTrace?: (step: string) => void
    onChunk?: (text: string) => void
    onCitations?: (data: any[]) => void
    onDone?: (payload: any) => void
    onError?: (e: Error) => void
  }
): () => void {
  const token = localStorage.getItem('access_token') || ''
  let cancelled = false

  fetch('/api/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (!cancelled) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const part of parts) {
          const eventLine = part.match(/^event: (.+)$/m)?.[1]
          const dataLine = part.match(/^data: (.+)$/m)?.[1]
          if (!eventLine || !dataLine) continue
          const payload = JSON.parse(dataLine)
          if (eventLine === 'chain_trace') handlers.onTrace?.(payload.step)
          else if (eventLine === 'answer_chunk') handlers.onChunk?.(payload.content)
          else if (eventLine === 'citations') handlers.onCitations?.(payload.data)
          else if (eventLine === 'done') handlers.onDone?.(payload)
          else if (eventLine === 'error')
            handlers.onError?.(new Error(String((payload as { detail?: string })?.detail || '对话流式错误')))
        }
      }
    })
    .catch((e) => handlers.onError?.(e))

  return () => { cancelled = true }
}
