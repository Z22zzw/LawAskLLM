import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scale, Eye, EyeOff } from 'lucide-react'
import { useAuthStore } from '../store/auth'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch {
      setError('用户名或密码错误，请重试。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-parchment flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-terracotta mb-4 shadow-ring">
            <Scale size={24} className="text-ivory" />
          </div>
          <h1 className="font-serif text-3xl text-deep-dark mb-1">法律智能助手</h1>
          <p className="text-stone-gray text-sm">Law LLM Platform · 基于 RAG 的法律问答系统</p>
        </div>

        {/* Card */}
        <div className="card p-8">
          <h2 className="font-serif text-xl text-deep-dark mb-6">登录账号</h2>

          {error && (
            <div className="mb-4 px-3 py-2 rounded-md bg-red-50 border border-red-100 text-error-crimson text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-olive-gray mb-1.5">用户名 / 邮箱</label>
              <input
                className="input"
                placeholder="请输入用户名或邮箱"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus
                required
              />
            </div>

            <div>
              <label className="block text-sm text-olive-gray mb-1.5">密码</label>
              <div className="relative">
                <input
                  className="input pr-10"
                  type={showPw ? 'text' : 'password'}
                  placeholder="请输入密码"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-gray hover:text-olive-gray"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-2.5 mt-2"
            >
              {loading ? '登录中…' : '登录'}
            </button>
          </form>

          <p className="text-center text-xs text-stone-gray mt-6">
            默认账号：<code className="text-olive-gray">admin</code> / <code className="text-olive-gray">Admin@123456</code>
          </p>
        </div>

        <p className="text-center text-xs text-stone-gray mt-6">
          © 2026 法律 LLM 平台 · 保留现有 RAG 能力
        </p>
      </div>
    </div>
  )
}
