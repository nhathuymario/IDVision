import { Routes, Route, Navigate } from 'react-router-dom'
import CheckinPage from './pages/CheckinPage.jsx'
import AdminLogin from './pages/AdminLogin.jsx'
import AdminLayout from './pages/admin/AdminLayout.jsx'
import Dashboard from './pages/admin/Dashboard.jsx'
import Employees from './pages/admin/Employees.jsx'
import Attendance from './pages/admin/Attendance.jsx'

export default function App() {
  return (
    <Routes>
      {/* Employee Check-in */}
      <Route path="/" element={<CheckinPage />} />
      <Route path="/checkin" element={<CheckinPage />} />

      {/* Admin */}
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="employees" element={<Employees />} />
        <Route path="attendance" element={<Attendance />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
