import { Outlet, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import Sidebar from './Sidebar'
import { useAuthStore } from '../../store/auth'

export default function AppLayout() {
  const { user, fetchMe } = useAuthStore()

  useEffect(() => {
    if (!user) fetchMe()
  }, [])

  if (!localStorage.getItem('access_token')) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="flex min-h-screen bg-parchment">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
