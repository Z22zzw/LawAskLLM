import { create } from 'zustand'
import { authApi } from '../lib/api'

interface UserInfo {
  id: number
  username: string
  email: string
  display_name: string
  is_active: boolean
  is_superadmin: boolean
}

interface AuthState {
  user: UserInfo | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: false,

  login: async (username, password) => {
    set({ loading: true })
    const data = await authApi.login(username, password)
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const me = await authApi.me()
    set({ user: me, loading: false })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('lawask_last_chat_session')
    set({ user: null })
    window.location.href = '/login'
  },

  fetchMe: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    try {
      const me = await authApi.me()
      set({ user: me })
    } catch {
      localStorage.clear()
    }
  },
}))
