import { useEffect, useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Users, ClipboardList, LogOut, ShieldCheck, Menu, X, ChevronRight } from 'lucide-react'
import { adminMe } from '../../api'
import './AdminLayout.css'

const NAV_ITEMS = [
  { to: '/admin/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/admin/employees', icon: Users, label: 'Nhân viên' },
  { to: '/admin/attendance', icon: ClipboardList, label: 'Chấm công' },
]

export default function AdminLayout() {
  const [adminName, setAdminName] = useState(localStorage.getItem('admin_name') || 'Admin')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('admin_token')
    if (!token) {
      navigate('/admin/login')
      return
    }
    adminMe().catch(() => {
      localStorage.removeItem('admin_token')
      navigate('/admin/login')
    })
  }, [navigate])

  function handleLogout() {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_name')
    navigate('/admin/login')
  }

  return (
    <div className="admin-layout">
      {/* Sidebar */}
      <aside className={`admin-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <ShieldCheck size={24} />
            <span>IDVision</span>
          </div>
          <button className="sidebar-close" onClick={() => setSidebarOpen(false)}>
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <NavLink key={item.to} to={item.to} className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}
              onClick={() => setSidebarOpen(false)}>
              <item.icon size={18} />
              <span>{item.label}</span>
              <ChevronRight size={14} className="nav-arrow" />
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="user-avatar">{adminName.charAt(0).toUpperCase()}</div>
            <div className="user-info">
              <span className="user-name">{adminName}</span>
              <span className="user-role">Quản trị viên</span>
            </div>
          </div>
          <button className="btn btn-secondary btn-sm logout-btn" onClick={handleLogout}>
            <LogOut size={14} /> Đăng xuất
          </button>
        </div>
      </aside>

      {/* Overlay for mobile */}
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      {/* Main area */}
      <div className="admin-main">
        <header className="admin-topbar">
          <button className="topbar-menu" onClick={() => setSidebarOpen(true)}>
            <Menu size={20} />
          </button>
          <NavLink to="/" className="btn btn-secondary btn-sm">
            Về trang chấm công
          </NavLink>
        </header>
        <div className="admin-content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
