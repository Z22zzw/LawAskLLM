import { useEffect, useState } from 'react'
import { Plus, Trash2, Edit2, Shield, Check, X } from 'lucide-react'
import { userApi } from '../lib/api'
import { UserOut } from '../types'
import clsx from 'clsx'

export default function UserAdminPage() {
  const [users, setUsers] = useState<UserOut[]>([])
  const [roles, setRoles] = useState<any[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ username: '', email: '', password: '', display_name: '', is_superadmin: false })
  const [error, setError] = useState('')

  useEffect(() => {
    userApi.list().then(setUsers)
    userApi.listRoles().then(setRoles)
  }, [])

  const createUser = async () => {
    setError('')
    try {
      const u = await userApi.create(form)
      setUsers(prev => [u, ...prev])
      setShowCreate(false)
      setForm({ username: '', email: '', password: '', display_name: '', is_superadmin: false })
    } catch (e: any) {
      setError(e.response?.data?.detail || '创建失败')
    }
  }

  const toggleActive = async (u: UserOut) => {
    const updated = await userApi.update(u.id, { is_active: !u.is_active })
    setUsers(prev => prev.map(x => x.id === u.id ? updated : x))
  }

  const deleteUser = async (id: number) => {
    if (!confirm('确认删除该用户？')) return
    await userApi.delete(id)
    setUsers(prev => prev.filter(u => u.id !== id))
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-2xl text-deep-dark">用户管理</h1>
          <p className="text-sm text-stone-gray mt-0.5">管理平台账号与角色权限</p>
        </div>
        <button onClick={() => setShowCreate(v => !v)} className="btn-primary">
          <Plus size={14} /> 新建用户
        </button>
      </div>

      {showCreate && (
        <div className="card p-5 mb-6 space-y-3">
          <h3 className="font-serif text-base text-deep-dark mb-1">新建用户</h3>
          {error && <p className="text-xs text-error-crimson">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-stone-gray mb-1 block">用户名</label>
              <input className="input" value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-stone-gray mb-1 block">邮箱</label>
              <input className="input" type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-stone-gray mb-1 block">密码</label>
              <input className="input" type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-stone-gray mb-1 block">显示名</label>
              <input className="input" value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-olive-gray">
            <input type="checkbox" checked={form.is_superadmin} onChange={e => setForm(f => ({ ...f, is_superadmin: e.target.checked }))} />
            设为超级管理员
          </label>
          <div className="flex gap-2 pt-1">
            <button onClick={createUser} className="btn-primary">创建</button>
            <button onClick={() => setShowCreate(false)} className="btn-ghost">取消</button>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-cream bg-parchment text-left">
              <th className="px-4 py-3 text-xs text-stone-gray font-medium">用户</th>
              <th className="px-4 py-3 text-xs text-stone-gray font-medium">邮箱</th>
              <th className="px-4 py-3 text-xs text-stone-gray font-medium">角色</th>
              <th className="px-4 py-3 text-xs text-stone-gray font-medium">状态</th>
              <th className="px-4 py-3 text-xs text-stone-gray font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b border-border-cream hover:bg-parchment/50 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-terracotta/10 flex items-center justify-center text-terracotta text-xs font-medium">
                      {(u.display_name || u.username)[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-deep-dark">{u.display_name || u.username}</p>
                      <p className="text-xs text-stone-gray">@{u.username}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-olive-gray">{u.email}</td>
                <td className="px-4 py-3">
                  {u.is_superadmin
                    ? <span className="badge-terra flex items-center gap-1"><Shield size={10}/>超管</span>
                    : u.roles.length
                      ? <span className="badge-warm">{u.roles.map(r => r.name).join(', ')}</span>
                      : <span className="text-stone-gray text-xs">无角色</span>
                  }
                </td>
                <td className="px-4 py-3">
                  <span className={u.is_active ? 'badge-green' : 'badge-red'}>
                    {u.is_active ? '正常' : '禁用'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleActive(u)}
                      className={clsx('text-xs px-2 py-1 rounded border transition-colors',
                        u.is_active
                          ? 'border-border-warm text-stone-gray hover:border-error-crimson hover:text-error-crimson'
                          : 'border-border-warm text-stone-gray hover:text-[#5e7d6a]'
                      )}
                    >
                      {u.is_active ? '禁用' : '启用'}
                    </button>
                    <button onClick={() => deleteUser(u.id)} className="text-stone-gray hover:text-error-crimson">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!users.length && (
          <div className="text-center py-10 text-stone-gray text-sm">暂无用户</div>
        )}
      </div>
    </div>
  )
}
