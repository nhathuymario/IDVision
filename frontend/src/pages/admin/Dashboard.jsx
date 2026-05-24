import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, CheckCircle, Clock, AlertTriangle, RefreshCw, TrendingUp, ClipboardList, Settings } from 'lucide-react'
import { getTodayStats, getTodayAttendance, getEmployees, refreshCache, getAdminPolicy } from '../../api'
import './Dashboard.css'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [recentLogs, setRecentLogs] = useState([])
  const [empCount, setEmpCount] = useState(0)
  const [policy, setPolicy] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [s, logs, emps, policyData] = await Promise.all([
        getTodayStats(),
        getTodayAttendance(),
        getEmployees({ limit: 1 }),
        getAdminPolicy(),
      ])
      setStats(s)
      setRecentLogs(logs.slice(0, 10))
      setEmpCount(emps.total)
      setPolicy(policyData)
    } catch(e) {
      console.error('Dashboard load error:', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const handleRefreshCache = useCallback(async () => {
    try {
      await refreshCache()
      alert('Cache đã được làm mới!')
    } catch { alert('Lỗi!') }
  }, [])

  const statCards = stats ? [
    { label: 'Tổng nhân viên', value: empCount, icon: Users, color: 'var(--accent)', bg: 'var(--accent-surface)' },
    { label: 'Đúng giờ hôm nay', value: stats.on_time, icon: CheckCircle, color: 'var(--success)', bg: 'var(--success-bg)' },
    { label: 'Đi trễ hôm nay', value: stats.late, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
    { label: 'Nhận diện kém', value: stats.low_confidence, icon: AlertTriangle, color: 'var(--danger)', bg: 'var(--danger-bg)' },
  ] : []

  function statusBadge(status) {
    const map = {
      'SUCCESS': { cls: 'badge-success', text: 'Đúng giờ' },
      'LATE': { cls: 'badge-warning', text: 'Trễ' },
      'LOW_CONFIDENCE': { cls: 'badge-danger', text: 'Kém' },
    }
    const s = map[status] || { cls: 'badge-info', text: status }
    return <span className={`badge ${s.cls}`}>{s.text}</span>
  }

  function methodBadge(method) {
    return method === 'PASSWORD'
      ? <span className="badge badge-info">Mật khẩu</span>
      : <span className="badge badge-success">Face ID</span>
  }

  if (loading) {
    return (
      <div className="dash-loading">
        <div className="spinner spinner-lg" />
        <p>Đang tải dữ liệu...</p>
      </div>
    )
  }

  return (
    <div className="dashboard">
      <div className="dash-header">
        <div>
          <h1>Dashboard</h1>
          <p className="text-muted">Tổng quan hệ thống chấm công hôm nay</p>
        </div>
        <div className="dash-actions">
          <button className="btn btn-secondary btn-sm" onClick={handleRefreshCache}>
            <RefreshCw size={14} /> Refresh Cache
          </button>
          <button className="btn btn-primary btn-sm" onClick={loadData}>
            <TrendingUp size={14} /> Cập nhật
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stat-grid">
        {statCards.map((c) => (
          <div className="stat-card card" key={c.label}>
            <div className="stat-icon" style={{ background: c.bg, color: c.color }}>
              <c.icon size={22} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{c.value}</span>
              <span className="stat-label">{c.label}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Logs */}
      {policy && (
        <div className="card policy-summary-card">
          <div className="policy-summary-header">
            <div>
              <h2>Cấu hình chấm công</h2>
              <p className="text-muted">Đang áp dụng cho tính trễ và tính lương</p>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/admin/policy')}>
              <Settings size={14} /> Chỉnh cấu hình
            </button>
          </div>
          <div className="policy-grid">
            <div><span>Giờ làm</span><strong>{policy.work_start_time} → {policy.work_end_time}</strong></div>
            <div><span>Nghỉ trưa</span><strong>{policy.break_start_time} → {policy.break_end_time}</strong></div>
            <div><span>Phút trễ cho phép</span><strong>{policy.late_grace_minutes} phút</strong></div>
            <div><span>Lương / giờ</span><strong>{policy.hourly_wage.toLocaleString('vi-VN')}</strong></div>
            <div><span>Timezone</span><strong>{policy.timezone}</strong></div>
          </div>
        </div>
      )}

      <div className="card recent-logs-card">
        <h2>Chấm công gần đây</h2>
        {recentLogs.length === 0 ? (
          <div className="empty-state">
            <ClipboardList size={48} strokeWidth={1} />
            <p>Chưa có bản ghi chấm công hôm nay</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nhân viên</th>
                  <th>Giờ vào</th>
                  <th>Phương thức</th>
                  <th>Trạng thái</th>
                  <th>Độ chính xác</th>
                </tr>
              </thead>
              <tbody>
                {recentLogs.map(log => (
                  <tr key={log.id}>
                    <td className="td-name">{log.employee_name}</td>
                    <td>{new Date(log.check_in_time).toLocaleTimeString('vi-VN')}</td>
                    <td>{methodBadge(log.check_method)}</td>
                    <td>{statusBadge(log.status)}</td>
                    <td>{log.confidence ? `${(log.confidence * 100).toFixed(1)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
