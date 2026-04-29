export interface Session {
  id: number
  session_uuid: string
  name: string
  legal_domain: string
  kb_ids: number[]
  created_at: string
  updated_at: string
}

export interface Citation {
  id: number
  dataset: string
  source_name: string
  legal_domain: string
  snippet: string
  score: number
  relevance: 'strong' | 'weak' | 'unrelated' | ''
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  intent: string
  coverage: string
  citations: Citation[]
  created_at: string
}

export interface KnowledgeBase {
  id: number
  name: string
  description: string
  legal_domains: string[]
  vector_collection: string
  embed_model: string
  doc_count: number
  created_at: string
  updated_at: string
}

export interface KbDocument {
  id: number
  kb_id: number
  filename: string
  file_type: string
  file_size: number
  split_role: 'train' | 'test'
  status: 'pending' | 'indexing' | 'indexed' | 'failed'
  error_msg: string
  chunk_count: number
  created_at: string
}

export interface UserOut {
  id: number
  username: string
  email: string
  display_name: string
  is_active: boolean
  is_superadmin: boolean
  roles: { id: number; name: string; description: string; is_system: boolean }[]
  created_at: string
}

export interface VectorStats {
  collection_name: string
  kb_id: number
  kb_name: string
  vector_count: number
  size_mb: number
  status: string
}

export const LEGAL_DOMAINS = [
  { code: '', label: '综合（不限领域）' },
  { code: 'xingfa', label: '刑法' },
  { code: 'minfa', label: '民法' },
  { code: 'xingzhengfa', label: '行政法与行政诉讼' },
  { code: 'susongfa', label: '民事/刑事诉讼法' },
  { code: 'jingjifa', label: '经济法' },
  { code: 'guojifa', label: '国际法与国际私法' },
  { code: 'lilunfa', label: '法理与法治理论' },
  { code: 'qita', label: '其它' },
]
