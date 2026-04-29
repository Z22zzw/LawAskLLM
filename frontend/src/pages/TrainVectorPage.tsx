import { useEffect, useRef, useState } from 'react'
import { Loader2, RefreshCw, Trash2, Upload, File, Database } from 'lucide-react'
import { kbApi } from '../lib/api'
import { getKbIndexJob, persistKbIndexJob, clearKbIndexJob } from '../lib/kbBuildStorage'
import { KbDocument, KnowledgeBase } from '../types'

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  pending: { label: '待处理', cls: 'badge-warm' },
  indexing: { label: '入库中', cls: 'badge-warm' },
  indexed: { label: '已入库', cls: 'badge-green' },
  failed: { label: '失败', cls: 'badge-red' },
}

export default function TrainVectorPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [active, setActive] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<KbDocument[]>([])
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [uploading, setUploading] = useState(false)
  const [splitRole, setSplitRole] = useState<'train' | 'test'>('train')
  const [kbIndexJobId, setKbIndexJobId] = useState<string | null>(null)
  const [kbIndexJob, setKbIndexJob] = useState<{ status: string; logs: string[]; error?: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => { void loadKbs() }, [])

  useEffect(() => {
    if (!active || !kbIndexJobId) return
    let cancelled = false
    let intervalId = 0
    const tick = async () => {
      try {
        const st = await kbApi.indexJobStatus(active.id, kbIndexJobId)
        if (cancelled) return
        setKbIndexJob(st)
        if (st.status === 'done' || st.status === 'error') {
          clearKbIndexJob()
          window.clearInterval(intervalId)
          const d = await kbApi.listDocs(active.id)
          if (!cancelled) setDocs(d)
        }
      } catch {
        if (!cancelled) {
          clearKbIndexJob()
          setKbIndexJobId(null)
          window.clearInterval(intervalId)
        }
      }
    }
    void tick()
    intervalId = window.setInterval(() => void tick(), 1200)
    return () => { cancelled = true; window.clearInterval(intervalId) }
  }, [active?.id, kbIndexJobId])

  const loadKbs = async () => {
    const data: KnowledgeBase[] = await kbApi.list()
    setKbs(data)
    const pending = getKbIndexJob()
    if (pending?.jobId && data.some(k => k.id === pending.kbId)) {
      const kb = data.find(k => k.id === pending.kbId)!
      setKbIndexJobId(pending.jobId)
      await selectKb(kb)
      return
    }
    if (data.length && !active) await selectKb(data[0])
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
    setNewName('')
    setNewDesc('')
    await selectKb(kb)
  }

  const deleteKb = async (id: number) => {
    if (!confirm('确认删除该向量库？将同时移除数据库记录、向量文件与上传目录，操作不可恢复。')) return
    await kbApi.delete(id)
    const remaining = kbs.filter(k => k.id !== id)
    setKbs(remaining)
    if (active?.id === id) {
      clearKbIndexJob()
      setKbIndexJob(null)
      setKbIndexJobId(null)
      if (remaining.length) void selectKb(remaining[0])
      else { setActive(null); setDocs([]) }
    }
  }

  const clearKbVectors = async () => {
    if (!active) return
    if (!confirm('确认清空该库的向量索引？文档与上传文件将保留，可重新构建。')) return
    await kbApi.clearVectorData(active.id)
    clearKbIndexJob()
    setKbIndexJob(null)
    setKbIndexJobId(null)
    const d = await kbApi.listDocs(active.id)
    setDocs(d)
    const list = await kbApi.list()
    setKbs(list)
    const next = list.find((k: KnowledgeBase) => k.id === active.id)
    if (next) setActive(next)
  }

  const uploadDocs = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!active || !e.target.files?.length) return
    setUploading(true)
    for (const file of Array.from(e.target.files)) {
      await kbApi.uploadDoc(active.id, file, splitRole)
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

  const startKbVectorIndex = async () => {
    if (!active) return
    setKbIndexJob(null)
    const { job_id } = await kbApi.startIndex(active.id)
    setKbIndexJobId(job_id)
    persistKbIndexJob(active.id, job_id)
  }

  return (
    <div className="flex h-screen">
      <aside className="w-64 flex flex-col bg-ivory border-r border-border-cream flex-shrink-0">
        <div className="px-4 py-5 border-b border-border-cream">
          <h1 className="font-serif text-lg text-deep-dark">训练集向量构建</h1>
          <p className="text-xs text-stone-gray mt-0.5">手动上传 train/test 并构建</p>
        </div>
        <div className="p-3 border-b border-border-cream">
          <button onClick={() => setCreating(true)} className="btn-secondary w-full justify-center">新建实验向量库</button>
        </div>
        {creating && (
          <div className="p-3 border-b border-border-cream bg-parchment space-y-2">
            <input className="input text-xs" placeholder="向量库名称" value={newName} onChange={e => setNewName(e.target.value)} />
            <input className="input text-xs" placeholder="描述（可选）" value={newDesc} onChange={e => setNewDesc(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={createKb} className="btn-primary text-xs px-3 py-1.5">创建</button>
              <button onClick={() => setCreating(false)} className="btn-ghost text-xs">取消</button>
            </div>
          </div>
        )}
        <div className="flex-1 overflow-y-auto py-2">
          {kbs.map(kb => (
            <div key={kb.id} className="group mx-2 mb-1 flex items-start gap-1">
              <button
                type="button"
                onClick={() => void selectKb(kb)}
                className={`flex-1 min-w-0 text-left px-3 py-2.5 rounded-md ${active?.id === kb.id ? 'bg-warm-sand' : 'hover:bg-warm-sand/50'}`}
              >
                <p className="text-sm font-medium text-deep-dark truncate">{kb.name}</p>
                <p className="text-xs text-stone-gray">{kb.doc_count} 份文档</p>
              </button>
              <button
                type="button"
                title="删除知识库"
                onClick={e => { e.stopPropagation(); void deleteKb(kb.id) }}
                className="mt-2 flex-shrink-0 p-1 rounded-md text-stone-gray hover:bg-warm-sand hover:text-error-crimson"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        {active ? (
          <>
            <div className="px-6 py-5 border-b border-border-cream bg-ivory/80">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-serif text-xl text-deep-dark">{active.name}</h2>
                  <p className="text-sm text-stone-gray mt-1">同一向量库内通过 split_role 区分 train/test。</p>
                  <div className="mt-2"><span className="badge-warm">Collection: {active.vector_collection}</span></div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <select className="input text-sm py-2 px-3" value={splitRole} onChange={e => setSplitRole(e.target.value as 'train' | 'test')}>
                    <option value="train">上传到训练集(train)</option>
                    <option value="test">上传到测试集(test)</option>
                  </select>
                  <input ref={fileRef} type="file" multiple className="hidden" onChange={uploadDocs} accept=".pdf,.txt,.md,.json" />
                  <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading} className="btn-primary">
                    <Upload size={14} /> {uploading ? '上传中…' : '上传文件'}
                  </button>
                  <button type="button" onClick={startKbVectorIndex} disabled={!docs.length || kbIndexJob?.status === 'running'} className="btn-secondary inline-flex items-center gap-1.5">
                    {kbIndexJob?.status === 'running' && <Loader2 size={14} className="animate-spin" />}
                    构建向量库
                  </button>
                  <button type="button" onClick={() => clearKbVectors()} className="btn-secondary inline-flex items-center gap-1.5" title="仅删除向量索引">
                    <Database size={14} /> 清空向量
                  </button>
                  <button type="button" onClick={() => void selectKb(active)} className="btn-secondary"><RefreshCw size={14} /></button>
                </div>
              </div>
              {kbIndexJob && (
                <div className="mt-3 rounded-lg border border-border-cream bg-parchment p-3 text-xs">
                  <p className="font-medium text-olive-gray mb-1">文档索引：{kbIndexJob.status}</p>
                  {kbIndexJob.error && <p className="text-error-crimson mb-1">{kbIndexJob.error}</p>}
                  <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-stone-gray font-mono">{kbIndexJob.logs.slice(-20).join('\n')}</pre>
                </div>
              )}
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              {!docs.length ? (
                <div className="text-center py-16 text-stone-gray">
                  <Database size={40} className="mx-auto mb-3 opacity-30" />
                  <p className="font-serif text-lg text-deep-dark mb-1">暂无训练/测试集文档</p>
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
                            {(doc.file_size / 1024).toFixed(1)} KB · {doc.split_role.toUpperCase()} · {doc.chunk_count} 块
                          </p>
                        </div>
                        <span className="badge-warm">{doc.split_role}</span>
                        <span className={s.cls}>{s.label}</span>
                        <button onClick={() => void deleteDoc(doc.id)} className="text-stone-gray hover:text-error-crimson">
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
              <Database size={48} className="mx-auto mb-3 opacity-20" />
              <p className="font-serif text-xl text-deep-dark mb-1">选择或新建实验向量库</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
