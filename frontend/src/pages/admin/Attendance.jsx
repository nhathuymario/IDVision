import { useState, useEffect } from 'react'
import { Search, Download, Calendar, ImageIcon } from 'lucide-react'
import { getAttendanceReport, getEmployees } from '../../api'
import './Attendance.css'

export default function Attendance() {
  const [logs, setLogs] = useState([])
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(false)

  // Filters
  const todayStr = new Date().toISOString().split('T')[0]
  const [dateFrom, setDateFrom] = useState(todayStr)
  const [dateTo, setDateTo] = useState(todayStr)
  const [empId, setEmpId] = useState('')

  // Snapshot Modal
  const [snapshotUrl, setSnapshotUrl] = useState(null)

  useEffect(() => {
    // Load employee list for filter dropdown
    getEmployees({ limit: 200 }).then(res => setEmployees(res.employees)).catch(() => {})
  }, [])

  useEffect(() => {
    loadData()
  }, [dateFrom, dateTo, empId])

  async function loadData() {
    setLoading(true)
    try {
      const res = await getAttendanceReport(dateFrom, dateTo, empId || null)
      setLogs(res.logs)
    } catch(e) { console.error(e) }
    setLoading(false)
  }

  function handleExport() {
    // Simple CSV export
    let csv = 'ID,Nhan Vien,Gio Vao,Phuong Thuc,Trang Thai,Do Chinh Xac\n'
    logs.forEach(l => {
      const time = new Date(l.check_in_time).toLocaleString('vi-VN')
      const conf = l.confidence ? (l.confidence * 100).toFixed(1) + '%' : ''
      csv += `${l.id},"${l.employee_name}","${time}",${l.check_method || 'FACE'},${l.status},${conf}\n`
    })
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `ChamCong_${dateFrom}_${dateTo}.csv`
    link.click()
  }

  function statusBadge(status) {
    const map = {
      'SUCCESS': { cls: 'badge-success', text: 'Đúng giờ' },
      'LATE': { cls: 'badge-warning', text: 'Trễ' },
      'LOW_CONFIDENCE': { cls: 'badge-danger', text: 'Kém' },
    }
    const s = map[status] || { cls: 'badge-info', text: status }
    return <span className={`badge ${s.cls}`}>{s.text}</span>
  }

  return (
    <div className="attendance-page">
      <div className="page-header">
        <div>
          <h1>Lịch sử Chấm công</h1>
          <p className="text-muted">Xem và xuất dữ liệu chấm công</p>
        </div>
        <button className="btn btn-secondary" onClick={handleExport} disabled={logs.length === 0}>
          <Download size={16} /> Xuất Excel (CSV)
        </button>
      </div>

      <div className="card filters-card">
        <div className="filters-grid">
          <div className="input-group">
            <label>Từ ngày</label>
            <div className="input-with-icon">
              <span className="input-icon"><Calendar size={16} /></span>
              <input type="date" className="input-field" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
            </div>
          </div>
          <div className="input-group">
            <label>Đến ngày</label>
            <div className="input-with-icon">
              <span className="input-icon"><Calendar size={16} /></span>
              <input type="date" className="input-field" value={dateTo} onChange={e => setDateTo(e.target.value)} />
            </div>
          </div>
          <div className="input-group">
            <label>Nhân viên</label>
            <select className="input-field" value={empId} onChange={e => setEmpId(e.target.value)}>
              <option value="">Tất cả nhân viên</option>
              {employees.map(e => <option key={e.id} value={e.id}>{e.name} ({e.employee_code})</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <div className="loading-state"><div className="spinner" /></div>
        ) : logs.length === 0 ? (
          <div className="empty-state">
            <Search size={48} />
            <p>Không có dữ liệu trong khoảng thời gian này</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nhân viên</th>
                  <th>Thời gian</th>
                  <th>Phương thức</th>
                  <th>Trạng thái</th>
                  <th>Độ chính xác</th>
                  <th>Ảnh check-in</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td><strong>{log.employee_name}</strong></td>
                    <td>{new Date(log.check_in_time).toLocaleString('vi-VN')}</td>
                    <td>
                      {log.check_method === 'PASSWORD' 
                        ? <span className="badge badge-info">Mật khẩu</span>
                        : <span className="badge badge-success">Face ID</span>}
                    </td>
                    <td>{statusBadge(log.status)}</td>
                    <td>{log.confidence ? `${(log.confidence * 100).toFixed(1)}%` : '—'}</td>
                    <td>
                      {log.snapshot_path ? (
                        <button className="btn btn-icon btn-secondary" title="Xem ảnh" 
                          onClick={() => setSnapshotUrl(`http://localhost:8000/snapshots/${log.snapshot_path.split(/\\|\//).pop()}`)}>
                          <ImageIcon size={14} />
                        </button>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Snapshot Modal */}
      {snapshotUrl && (
        <div className="modal-overlay" onClick={() => setSnapshotUrl(null)}>
          <div className="snapshot-modal" onClick={e => e.stopPropagation()}>
            <img src={snapshotUrl} alt="Check-in snapshot" />
            <button className="modal-close snapshot-close" onClick={() => setSnapshotUrl(null)}>×</button>
          </div>
        </div>
      )}
    </div>
  )
}
