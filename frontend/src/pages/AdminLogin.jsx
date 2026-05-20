import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, User, Lock, LogIn, ArrowLeft } from 'lucide-react'
import { adminLogin } from '../api'
import './AdminLogin.css'

export default function AdminLogin() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await adminLogin(username, password)
      localStorage.setItem('admin_token', data.token)
      localStorage.setItem('admin_name', data.full_name || data.username)
      navigate('/admin/dashboard')
    } catch {
      setError('Tên đăng nhập hoặc mật khẩu không đúng.')
    }
    setLoading(false)
  }

  return (
    <div className="login-page">
      <div className="login-bg">
        <div className="login-orb orb-a" />
        <div className="login-orb orb-b" />
      </div>

      <div className="login-container">
        <button className="btn btn-secondary btn-sm back-btn" onClick={() => navigate('/')}>
          <ArrowLeft size={16} /> Về trang chấm công
        </button>

        <div className="login-card glass">
          <div className="login-logo">
            <ShieldCheck size={36} />
            <h1>IDVision</h1>
            <p>Admin Dashboard</p>
          </div>

          {error && <div className="login-error">{error}</div>}

          <form onSubmit={handleSubmit} className="login-form">
            <div className="input-group">
              <label htmlFor="adminUser">Tên đăng nhập</label>
              <div className="input-with-icon">
                <span className="input-icon"><User size={16} /></span>
                <input id="adminUser" className="input-field" type="text" placeholder="admin"
                  value={username} onChange={e => setUsername(e.target.value)} required autoComplete="username" />
              </div>
            </div>
            <div className="input-group">
              <label htmlFor="adminPass">Mật khẩu</label>
              <div className="input-with-icon">
                <span className="input-icon"><Lock size={16} /></span>
                <input id="adminPass" className="input-field" type="password" placeholder="Nhập mật khẩu"
                  value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password" />
              </div>
            </div>
            <button type="submit" className="btn btn-primary btn-lg login-submit" disabled={loading}>
              {loading ? <div className="spinner" /> : <LogIn size={18} />}
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>

          <p className="login-hint">Mặc định: admin / admin123</p>
        </div>
      </div>
    </div>
  )
}
