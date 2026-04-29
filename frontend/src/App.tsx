import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AppLayout from './components/layout/AppLayout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ChatPage from './pages/ChatPage'
import KbAdminPage from './pages/KbAdminPage'
import UserAdminPage from './pages/UserAdminPage'
import ExperimentPage from './pages/ExperimentPage'
import TrainVectorPage from './pages/TrainVectorPage'

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AppLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/kb" element={<KbAdminPage />} />
            <Route path="/train-vector" element={<TrainVectorPage />} />
            <Route path="/experiments" element={<ExperimentPage />} />
            <Route path="/admin" element={<UserAdminPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
