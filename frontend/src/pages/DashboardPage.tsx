import { useEffect, useState } from 'react'
import { MessageSquare, BookOpen, Users, Database } from 'lucide-react'
import { chatApi, kbApi, userApi } from '../lib/api'
import { useAuthStore } from '../store/auth'

interface Stat { label: string; value: string | number; icon: any; color: string }

export default function DashboardPage() {
  const { user } = useAuthStore()
  const [stats, setStats] = useState<Stat[]>([])

  useEffect(() => {
    Promise.allSettled([
      chatApi.listSessions(),
      kbApi.list(),
      user?.is_superadmin ? userApi.list() : Promise.resolve([]),
      kbApi.vectorStats().catch(() => []),
    ]).then(([sessions, kbs, users, vectors]) => {
      const sessionCount = sessions.status === 'fulfilled' ? sessions.value.length : '—'
      const kbCount = kbs.status === 'fulfilled' ? kbs.value.length : '—'
      const userCount = users.status === 'fulfilled' ? users.value.length : '—'
      const vecMb = vectors.status === 'fulfilled'
        ? (vectors.value as any[]).reduce((s: number, v: any) => s + (v.size_mb || 0), 0).toFixed(1) + ' MB'
        : '—'

      setStats([
        { label: '我的会话', value: sessionCount, icon: MessageSquare, color: 'bg-terracotta' },
        { label: '知识库', value: kbCount, icon: BookOpen, color: 'bg-[#5e7d6a]' },
        { label: '系统用户', value: userCount, icon: Users, color: 'bg-[#5b7fa6]' },
        { label: '向量库大小', value: vecMb, icon: Database, color: 'bg-[#7a6b52]' },
      ])
    })
  }, [user])

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Hero */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-deep-dark mb-2">
          欢迎回来，{user?.display_name || user?.username}
        </h1>
        <p className="text-olive-gray">法律智能助手平台 · 基于 RAG 检索增强生成</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card p-5 flex items-center gap-4">
            <div className={`${color} w-10 h-10 rounded-md flex items-center justify-center flex-shrink-0`}>
              <Icon size={18} className="text-ivory" />
            </div>
            <div>
              <p className="text-2xl font-serif text-deep-dark font-medium">{value}</p>
              <p className="text-xs text-stone-gray mt-0.5">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <a href="/chat" className="card p-6 hover:shadow-ring transition-shadow cursor-pointer group">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-md bg-terracotta/10 flex items-center justify-center group-hover:bg-terracotta/20 transition-colors">
              <MessageSquare size={18} className="text-terracotta" />
            </div>
            <h3 className="font-serif text-lg text-deep-dark">开始法律问答</h3>
          </div>
          <p className="text-sm text-olive-gray leading-relaxed">
            输入法律问题，系统将从知识库中检索相关条文与案例，结合大模型生成专业回答并标注引用证据。
          </p>
        </a>

        <a href="/kb" className="card p-6 hover:shadow-ring transition-shadow cursor-pointer group">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-md bg-[#5e7d6a]/10 flex items-center justify-center group-hover:bg-[#5e7d6a]/20 transition-colors">
              <BookOpen size={18} className="text-[#5e7d6a]" />
            </div>
            <h3 className="font-serif text-lg text-deep-dark">管理知识库</h3>
          </div>
          <p className="text-sm text-olive-gray leading-relaxed">
            上传文档，管理向量索引。支持 JEC-QA 司法考试题库、CAIL2018 案情数据集及自定义文档。
          </p>
        </a>
      </div>

      {/* 深色特性区块 */}
      <div className="section-dark rounded-xl p-8 mt-6">
        <h2 className="font-serif text-xl mb-4">核心能力</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-warm-silver">
          {[
            ['多路召回', '语义检索 + 关键词增强 + RRF 融合，双数据源均衡策略'],
            ['证据标注', '每条回答标注「证据[i]」或「通用知识」，可追溯到具体文档块'],
            ['法律领域', '刑法 · 民法 · 行政法 · 诉讼法等七大领域过滤检索'],
          ].map(([title, desc]) => (
            <div key={title} className="border border-dark-surface rounded-md p-4">
              <p className="text-ivory font-medium mb-1.5">{title}</p>
              <p className="leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
