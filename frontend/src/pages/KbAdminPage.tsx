import { useEffect, useRef, useState } from 'react'
import { Plus, Trash2, Upload, BookOpen, File, RefreshCw } from 'lucide-react'
import { kbApi } from '../lib/api'
import { KnowledgeBase, KbDocument, LEGAL_DOMAINS } from '../types'
import clsx from 'clsx'

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  pending:  { label: '待处理', cls: 'badge-warm' },
  indexing: { label: '入库中', cls: 'badge-warm' },
  indexed:  { label: '已入库', cls: 'badge-green' },
  failed:   { label: '失败',   cls: 'badge-red' },
}

export default function KbAdminPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [active, setActive] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<KbDocument[]>([])
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => { loadKbs() }, [])

  const loadKbs = async () => {
    const data = await kbApi.list()
    setKbs(data)
    if (data.length && !active) selectKb(data[0])
  }

  const selectKb = async (kb: KnowledgeBase) => {
    setActive(kb)
    const d = await kbApi.listDocs(kb.id)
    setDocs(d)
  }

  const createKb = async () => {
    if (!newName.trim()) return
    const kb = await kbApi.create({ name: newName.trim(), description: newDesc })
    setKbs(prev => [kb, ...prev])
    setCreating(false)
    setNewName(''); setNewDesc('')
    selectKb(kb)
  }

  const deleteKb = async (id: number) => {
    if (!confirm('确认删除该知识库？此操作不可恢复。')) return
    await kbApi.delete(id)
    const remaining = kbs.filter(k => k.id !== id)
    setKbs(remaining)
    if (active?.id === id) {
      if (remaining.length) selectKb(remaining[0])
      else { setActive(null); setDocs([]) }
    }
  }

  const uploadDoc = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!active || !e.target.files?.length) return
    setUploading(true)
    for (const file of Array.from(e.target.files)) {
      await kbApi.uploadDoc(active.id, file)
    }
    const d = await kbApi.listDocs(active.id)
    setDocs(d)
    setUploading(false)
    e.target.value = ''
  }

  const deleteDoc = async (docId: number) => {
    if (!active) return
    await kbApi.deleteDoc(active.id, docId)
    setDocs(prev => prev.filter(d => d.id !== docId))
  }

  return (
    <div className="flex h-screen">
      {/* ── 知识库列表 ── */}
      <aside className="w-64 flex flex-col bg-ivory border-r border-border-cream flex-shrink-0">
        <div className="px-4 py-5 border-b border-border-cream">
          <h1 className="font-serif text-lg text-deep-dark">知识库管理</h1>
          <p className="text-xs text-stone-gray mt-0.5">管理文档与向量索引</p>
        </div>

        <div className="p-3 border-b border-border-cream">
          <button onClick={() => setCreating(true)} className="btn-secondary w-full justify-center">
            <Plus size={14} /> 新建知识库
          </button>
        </div>

        {creating && (
          <div className="p-3 border-b border-border-cream bg-parchment space-y-2">
            <input className="input text-xs" placeholder="知识库名称" value={newName} onChange={e => setNewName(e.target.value)} autoFocus />
            <input className="input text-xs" placeholder="描述（可选）" value={newDesc} onChange={e => setNewDesc(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={createKb} className="btn-primary text-xs px-3 py-1.5">创建</button>
              <button onClick={() => setCreating(false)} className="btn-ghost text-xs">取消</button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto py-2">
          {kbs.map(kb => (
            <div
              key={kb.id}
              onClick={() => selectKb(kb)}
              className={clsx(
                'group flex items-start gap-2 mx-2 px-3 py-2.5 rounded-md cursor-pointer',
                active?.id === kb.id ? 'bg-warm-sand' : 'hover:bg-warm-sand/50'
              )}
            >
              <BookOpen size={14} className="text-terracotta mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-deep-dark truncate">{kb.name}</p>
                <p className="text-xs text-stone-gray">{kb.doc_count} 份文档</p>
              </div>
              <button
                onClick={e => { e.stopPropagation(); deleteKb(kb.id) }}
                className="hidden group-hover:block text-stone-gray hover:text-error-crimson p-0.5"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* ── 文档管理区 ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {active ? (
          <>
            <div className="px-6 py-5 border-b border-border-cream bg-ivory/80">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-serif text-xl text-deep-dark">{active.name}</h2>
                  {active.description && <p className="text-sm text-stone-gray mt-0.5">{active.description}</p>}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    <span className="badge-warm">Collection: {active.vector_collection}</span>
                    <span className="badge-warm">嵌入模型: {active.embed_model}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <input ref={fileRef} type="file" multiple className="hidden" onChange={uploadDoc} accept=".pdf,.txt,.md,.docx,.json" />
                  <button
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                    className="btn-primary"
                  >
                    <Upload size={14} /> {uploading ? '上传中…' : '上传文档'}
                  </button>
                  <button onClick={() => selectKb(active)} className="btn-secondary">
                    <RefreshCw size={14} />
                  </button>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {!docs.length ? (
                <div className="text-center py-16 text-stone-gray">
                  <File size={40} className="mx-auto mb-3 opacity-30" />
                  <p className="font-serif text-lg text-deep-dark mb-1">暂无文档</p>
                  <p className="text-sm">点击「上传文档」添加 PDF、TXT、MD 等格式文件</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {docs.map(doc => {
                    const s = STATUS_MAP[doc.status] || { label: doc.status, cls: 'badge-warm' }
                    return (
                      <div key={doc.id} className="card px-4 py-3 flex items-center gap-4">
                        <File size={16} className="text-terracotta flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-deep-dark truncate">{doc.filename}</p>
                          <p className="text-xs text-stone-gray">
                            {(doc.file_size / 1024).toFixed(1)} KB · {doc.chunk_count} 块 · {new Date(doc.created_at).toLocaleDateString('zh-CN')}
                          </p>
                        </div>
                        <span className={s.cls}>{s.label}</span>
                        {doc.status === 'failed' && <span className="text-xs text-error-crimson">{doc.error_msg}</span>}
                        <button onClick={() => deleteDoc(doc.id)} className="text-stone-gray hover:text-error-crimson">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-stone-gray">
            <div className="text-center">
              <BookOpen size={48} className="mx-auto mb-3 opacity-20" />
              <p className="font-serif text-xl text-deep-dark mb-1">选择或新建知识库</p>
              <p className="text-sm">从左侧选择知识库以管理文档</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
