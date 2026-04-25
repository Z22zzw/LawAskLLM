import { NavLink, useNavigate } from 'react-router-dom'
import { MessageSquare, BookOpen, Users, LayoutDashboard, LogOut, Scale } from 'lucide-react'
import { useAuthStore } from '../../store/auth'
import clsx from 'clsx'

const navItems = [
  { to: '/',       icon: LayoutDashboard, label: '控制台' },
  { to: '/chat',   icon: MessageSquare,   label: '智能问答' },
  { to: '/kb',     icon: BookOpen,        label: '知识库' },
  { to: '/admin',  icon: Users,           label: '用户管理', adminOnly: true },
]

export default function Sidebar() {
  const { user, logout } = useAuthStore()

  return (
    <aside className="flex flex-col w-56 min-h-screen bg-ivory border-r border-border-cream">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-border-cream">
        <div className="w-8 h-8 rounded-md bg-terracotta flex items-center justify-center flex-shrink-0">
          <Scale size={16} className="text-ivory" />
        </div>
        <div>
          <p className="font-serif text-sm font-medium text-deep-dark leading-tight">法律智能助手</p>
          <p className="text-[10px] text-stone-gray tracking-wide uppercase mt-0.5">Law LLM Platform</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label, adminOnly }) => {
          if (adminOnly && !user?.is_superadmin) return null
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx('nav-item', isActive && 'active')
              }
            >
              <Icon size={16} />
              <span>{label}</span>
            </NavLink>
          )
        })}
      </nav>

      {/* User info + logout */}
      <div className="px-3 py-4 border-t border-border-cream space-y-1">
        <div className="px-3 py-2">
          <p className="text-sm font-medium text-deep-dark truncate">{user?.display_name || user?.username}</p>
          <p className="text-xs text-stone-gray truncate">{user?.email}</p>
          {user?.is_superadmin && (
            <span className="badge-terra mt-1">超级管理员</span>
          )}
        </div>
        <button onClick={logout} className="nav-item w-full text-error-crimson hover:bg-red-50 hover:text-error-crimson">
          <LogOut size={16} />
          <span>退出登录</span>
        </button>
      </div>
    </aside>
  )
}
