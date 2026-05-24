import { useEffect, useState, useCallback } from 'react'
import { Coins, Calendar, UserRound } from 'lucide-react'
import { getSalaryOverview, getEmployeeSalary } from '../../api'
import './Salary.css'

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export default function Salary() {
  const [month, setMonth] = useState(currentMonth())
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('')
  const [employeeDetail, setEmployeeDetail] = useState(null)

  const loadEmployeeDetail = useCallback(async (employeeId, targetMonth = month) => {
    if (!employeeId) {
      setEmployeeDetail(null)
      return
    }
    try {
      const detail = await getEmployeeSalary(employeeId, targetMonth)
      setEmployeeDetail(detail)
    } catch (e) {
      console.error(e)
      setEmployeeDetail(null)
    }
  }, [month])

  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getSalaryOverview(month)
      setOverview(data)
      if (selectedEmployeeId) {
        await loadEmployeeDetail(selectedEmployeeId, month)
      }
    } catch (e) {
      console.error(e)
      setOverview(null)
    }
    setLoading(false)
  }, [month, selectedEmployeeId, loadEmployeeDetail])

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadOverview()
    }, 0)
    return () => clearTimeout(timer)
  }, [loadOverview])

  function handleSelectEmployee(employeeId) {
    setSelectedEmployeeId(employeeId)
    void loadEmployeeDetail(employeeId)
  }

  function renderSalaryTable() {
    if (loading) {
      return <div className="loading-state"><div className="spinner" /></div>
    }

    if (!overview || overview.employees.length === 0) {
      return <div className="empty-state"><p>Chưa có dữ liệu lương trong tháng này</p></div>
    }

    return (
      <div className="table-responsive">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nhân viên</th>
              <th>Ngày công</th>
              <th>Giờ công</th>
              <th>Lương/giờ</th>
              <th>Lương ước tính</th>
              <th>Chi tiết</th>
            </tr>
          </thead>
          <tbody>
            {overview.employees.map((item) => (
              <tr key={item.employee_id}>
                <td><strong>{item.employee_name}</strong> ({item.employee_code})</td>
                <td>{item.worked_days}</td>
                <td>{item.worked_hours.toFixed(2)}</td>
                <td>{item.hourly_wage.toLocaleString('vi-VN')}</td>
                <td>{item.estimated_salary.toLocaleString('vi-VN')}</td>
                <td>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleSelectEmployee(item.employee_id)}
                  >
                    Xem
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="salary-page">
      <div className="page-header">
        <div>
          <h1>Quản lý lương</h1>
          <p className="text-muted">Theo dõi ngày công, giờ công và lương theo tháng</p>
        </div>
        <div className="salary-controls">
          <div className="input-with-icon month-input-wrap">
            <span className="input-icon"><Calendar size={16} /></span>
            <input
              className="input-field"
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            />
          </div>
        </div>
      </div>

      {overview && (
        <div className="stat-grid">
          <div className="stat-card card">
            <div className="stat-icon" style={{ background: 'var(--accent-surface)', color: 'var(--accent)' }}>
              <UserRound size={22} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{overview.total_employees}</span>
              <span className="stat-label">Nhân viên có thống kê</span>
            </div>
          </div>
          <div className="stat-card card">
            <div className="stat-icon" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>
              <Calendar size={22} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{overview.total_worked_days}</span>
              <span className="stat-label">Tổng ngày công</span>
            </div>
          </div>
          <div className="stat-card card">
            <div className="stat-icon" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>
              <Coins size={22} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{overview.total_estimated_salary.toLocaleString('vi-VN')}</span>
              <span className="stat-label">Tổng lương ước tính (VND)</span>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        {renderSalaryTable()}
      </div>

      {employeeDetail && (
        <div className="card detail-card">
          <h2>Chi tiết nhân viên</h2>
          <p><strong>{employeeDetail.employee.employee_name}</strong> ({employeeDetail.employee.employee_code})</p>
          <p>Tháng: <strong>{employeeDetail.month}</strong></p>
          <p>Ngày công: <strong>{employeeDetail.employee.worked_days}</strong></p>
          <p>Giờ công: <strong>{employeeDetail.employee.worked_hours.toFixed(2)}</strong></p>
          <p>Lương/giờ: <strong>{employeeDetail.employee.hourly_wage.toLocaleString('vi-VN')}</strong></p>
          <p>Lương ước tính: <strong>{employeeDetail.employee.estimated_salary.toLocaleString('vi-VN')}</strong></p>
        </div>
      )}
    </div>
  )
}

