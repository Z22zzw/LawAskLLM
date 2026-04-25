import { useEffect, useRef, useState } from 'react'
import { Plus, Send, Trash2, Edit2, Check, X } from 'lucide-react'
import { chatApi, streamCompletion } from '../lib/api'
import { Session, Message, Citation, LEGAL_DOMAINS } from '../types'
import MessageBubble from '../components/chat/MessageBubble'
import CitationPanel from '../components/chat/CitationPanel'
import clsx from 'clsx'

export default function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [streamMsg, setStreamMsg] = useState('')
  const [streamCites, setStreamCites] = useState<Citation[]>([])
  const [trace, setTrace] = useState<string[]>([])
  const [domain, setDomain] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<(() => void) | null>(null)

  useEffect(() => { loadSessions() }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streamMsg])

  const loadSessions = async () => {
    const data = await chatApi.listSessions()
    setSessions(data)
    if (data.length && !activeId) switchSession(data[0].session_uuid)
  }

  const switchSession = async (uuid: string) => {
    setActiveId(uuid)
    setStreamMsg('')
    setStreamCites([])
    setTrace([])
    const msgs = await chatApi.listMessages(uuid)
    setMessages(msgs)
    const s = sessions.find(s => s.session_uuid === uuid) || (await chatApi.listSessions()).find((s: Session) => s.session_uuid === uuid)
    if (s) setDomain(s.legal_domain || '')
  }

  const newSession = async () => {
    const s = await chatApi.createSession({ name: '新对话', legal_domain: domain })
    setSessions(prev => [s, ...prev])
    setMessages([])
    setActiveId(s.session_uuid)
    setStreamMsg('')
    setStreamCites([])
  }

  const deleteSession = async (uuid: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await chatApi.deleteSession(uuid)
    const remaining = sessions.filter(s => s.session_uuid !== uuid)
    setSessions(remaining)
    if (activeId === uuid) {
      setMessages([])
      if (remaining.length) switchSession(remaining[0].session_uuid)
      else { setActiveId(null) }
    }
  }

  const saveRename = async (uuid: string) => {
    await chatApi.updateSession(uuid, { name: editName })
    setSessions(prev => prev.map(s => s.session_uuid === uuid ? { ...s, name: editName } : s))
    setEditingId(null)
  }

  const sendMessage = async () => {
    if (!input.trim() || sending || !activeId) return
    const q = input.trim()
    setInput('')
    setSending(true)
    setStreamMsg('')
    setStreamCites([])
    setTrace([])

    const userMsg: Message = {
      id: Date.now(), role: 'user', content: q,
      intent: '', coverage: '', citations: [], created_at: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMsg])

    let fullText = ''
    cancelRef.current = streamCompletion(
      { session_uuid: activeId, question: q, legal_domain: domain },
      {
        onTrace: step => setTrace(prev => [...prev, step]),
        onChunk: chunk => { fullText += chunk; setStreamMsg(fullText) },
        onCitations: data => setStreamCites(data as Citation[]),
        onDone: async (payload) => {
          setSending(false)
          setStreamMsg('')
          const msgs = await chatApi.listMessages(activeId)
          setMessages(msgs)
          setStreamCites([])
          const newSessions = await chatApi.listSessions()
          setSessions(newSessions)
        },
        onError: () => { setSending(false); setStreamMsg('') },
      }
    )
  }

  return (
    <div className="flex h-screen">
      {/* ── 会话列表侧栏 ── */}
      <aside className="w-60 flex flex-col bg-ivory border-r border-border-cream flex-shrink-0">
        <div className="p-3 border-b border-border-cream">
          <button onClick={newSession} className="btn-secondary w-full justify-center">
            <Plus size={14} /> 新建对话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {sessions.map(s => (
            <div
              key={s.session_uuid}
              onClick={() => switchSession(s.session_uuid)}
              className={clsx(
                'group flex items-center gap-2 mx-2 px-2 py-2 rounded-md cursor-pointer text-sm',
                activeId === s.session_uuid
                  ? 'bg-warm-sand text-deep-dark'
                  : 'text-olive-gray hover:bg-warm-sand/50'
              )}
            >
              {editingId === s.session_uuid ? (
                <div className="flex items-center gap-1 flex-1 min-w-0" onClick={e => e.stopPropagation()}>
                  <input
                    className="input py-0.5 px-1 text-xs h-6 flex-1"
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && saveRename(s.session_uuid)}
                    autoFocus
                  />
                  <button onClick={() => saveRename(s.session_uuid)} className="text-terracotta"><Check size={12}/></button>
                  <button onClick={() => setEditingId(null)} className="text-stone-gray"><X size={12}/></button>
                </div>
              ) : (
                <>
                  <span className="flex-1 truncate">{s.name}</span>
                  <div className="hidden group-hover:flex items-center gap-0.5">
                    <button onClick={e => { e.stopPropagation(); setEditingId(s.session_uuid); setEditName(s.name) }} className="p-0.5 hover:text-terracotta"><Edit2 size={11}/></button>
                    <button onClick={e => deleteSession(s.session_uuid, e)} className="p-0.5 hover:text-error-crimson"><Trash2 size={11}/></button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>

        {/* 领域选择 */}
        <div className="p-3 border-t border-border-cream">
          <label className="text-xs text-stone-gray mb-1 block">法律领域</label>
          <select
            value={domain}
            onChange={e => setDomain(e.target.value)}
            className="input py-1.5 text-xs"
          >
            {LEGAL_DOMAINS.map(d => (
              <option key={d.code} value={d.code}>{d.label}</option>
            ))}
          </select>
        </div>
      </aside>

      {/* ── 对话主区 ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶栏 */}
        <div className="px-6 py-4 border-b border-border-cream bg-ivory/80 backdrop-blur">
          <h2 className="font-serif text-lg text-deep-dark">
            {sessions.find(s => s.session_uuid === activeId)?.name || '法律智能问答'}
          </h2>
          <p className="text-xs text-stone-gray mt-0.5">
            基于 RAG 检索增强生成 · {LEGAL_DOMAINS.find(d => d.code === domain)?.label || '综合领域'}
          </p>
        </div>

        {/* 消息区 */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {!messages.length && !streamMsg && (
            <div className="text-center py-16">
              <p className="font-serif text-xl text-deep-dark mb-2">请输入您的法律问题</p>
              <p className="text-sm text-stone-gray">系统会从知识库中检索相关法律知识，结合大模型生成专业回答</p>
              <div className="flex flex-wrap justify-center gap-2 mt-6">
                {['合同的撤销条件是什么？', '故意伤害罪与正当防卫如何区分？', '劳动合同解除有哪些法定情形？'].map(q => (
                  <button key={q} onClick={() => { setInput(q) }} className="btn-secondary text-xs px-3 py-1.5">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(m => <MessageBubble key={m.id} message={m} />)}

          {streamMsg && (
            <MessageBubble
              message={{ id: 0, role: 'assistant', content: streamMsg, intent: '', coverage: '', citations: [], created_at: '' }}
              isStreaming
            />
          )}

          {sending && trace.length > 0 && (
            <div className="mb-3 px-4 py-2 rounded-md bg-warm-sand/50 border border-border-cream text-xs text-stone-gray">
              {trace[trace.length - 1]}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* 输入区 */}
        <div className="px-6 py-4 border-t border-border-cream bg-ivory/80">
          {streamCites.length > 0 && (
            <div className="mb-3 p-3 rounded-md bg-parchment border border-border-cream">
              <p className="text-xs font-medium text-olive-gray mb-2">参考证据</p>
              <CitationPanel citations={streamCites} />
            </div>
          )}
          <div className="flex gap-3">
            <textarea
              className="input flex-1 resize-none h-14 py-3 leading-snug"
              placeholder="请描述您的法律问题，建议提供具体情境…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
              disabled={sending}
            />
            <button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
              className="btn-primary px-4 self-end h-14"
            >
              <Send size={16} />
            </button>
          </div>
          <p className="text-xs text-stone-gray mt-1.5">Enter 发送 · Shift+Enter 换行</p>
        </div>
      </div>
    </div>
  )
}
