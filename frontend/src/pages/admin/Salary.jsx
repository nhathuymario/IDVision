import { useEffect, useState, useCallback } from 'react'
import { Coins, Calendar, UserRound, Send, Download, FileText, Settings2, Plus, Trash2, Check, X, SendHorizonal } from 'lucide-react'
import { getSalaryOverview, getEmployeeSalary, getSlipConfig, updateSlipConfig, downloadSalaryPdf, sendSalarySlip, sendAllSalarySlips } from '../../api'
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

  // Slip config state
  const [showConfig, setShowConfig] = useState(false)
  const [slipConfig, setSlipConfig] = useState(null)
  const [configForm, setConfigForm] = useState(null)
  const [configLoading, setConfigLoading] = useState(false)

  // Send states
  const [sendingId, setSendingId] = useState(null)
  const [sendingAll, setSendingAll] = useState(false)
  const [sendResults, setSendResults] = useState(null)

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

  // Load slip config
  useEffect(() => {
    if (showConfig && !slipConfig) {
      loadSlipConfig()
    }
  }, [showConfig])

  async function loadSlipConfig() {
    setConfigLoading(true)
    try {
      const data = await getSlipConfig()
      setSlipConfig(data)
      setConfigForm({ ...data })
    } catch (e) {
      console.error(e)
    }
    setConfigLoading(false)
  }

  async function handleSaveConfig() {
    setConfigLoading(true)
    try {
      const saved = await updateSlipConfig(configForm)
      setSlipConfig(saved)
      setConfigForm({ ...saved })
      alert('Đã lưu cấu hình phiếu lương!')
    } catch (e) {
      alert('Lỗi khi lưu cấu hình!')
      console.error(e)
    }
    setConfigLoading(false)
  }

  function handleSelectEmployee(employeeId) {
    setSelectedEmployeeId(employeeId)
    void loadEmployeeDetail(employeeId)
  }

  async function handleDownloadPdf(employeeId, empCode) {
    try {
      const blob = await downloadSalaryPdf(employeeId, month)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `phieu_luong_${empCode}_${month}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('Lỗi khi tải PDF!')
      console.error(e)
    }
  }

  async function handleSendOne(employeeId) {
    setSendingId(employeeId)
    try {
      const result = await sendSalarySlip(employeeId, month)
      if (result.success) {
        alert(`✅ ${result.message}`)
      } else {
        alert(`❌ ${result.message}`)
      }
    } catch (e) {
      alert('Lỗi khi gửi!')
      console.error(e)
    }
    setSendingId(null)
  }

  async function handleSendAll() {
    if (!confirm('Gửi phiếu lương cho TẤT CẢ nhân viên đã liên kết Telegram?')) return
    setSendingAll(true)
    try {
      const results = await sendAllSalarySlips(month)
      setSendResults(results)
    } catch (e) {
      alert('Lỗi khi gửi!')
      console.error(e)
    }
    setSendingAll(false)
  }

  // Config form helpers
  function addConfigItem(type) {
    const key = type === 'earning' ? 'extra_earnings' : 'extra_deductions'
    setConfigForm(prev => ({
      ...prev,
      [key]: [...prev[key], { label: '', default_amount: 0 }]
    }))
  }

  function removeConfigItem(type, index) {
    const key = type === 'earning' ? 'extra_earnings' : 'extra_deductions'
    setConfigForm(prev => ({
      ...prev,
      [key]: prev[key].filter((_, i) => i !== index)
    }))
  }

  function updateConfigItem(type, index, field, value) {
    const key = type === 'earning' ? 'extra_earnings' : 'extra_deductions'
    setConfigForm(prev => ({
      ...prev,
      [key]: prev[key].map((item, i) => i === index ? { ...item, [field]: value } : item)
    }))
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
              <th>Telegram</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {overview.employees.map((item) => (
              <tr key={item.employee_id}>
                <td><strong>{item.employee_name}</strong> ({item.employee_code})</td>
                <td>{item.worked_days}</td>
                <td>{item.worked_hours.toFixed(2)}</td>
                <td>{item.hourly_wage.toLocaleString('vi-VN')}</td>
                <td className="salary-amount">{item.estimated_salary.toLocaleString('vi-VN')}</td>
                <td>
                  {item.telegram_linked
                    ? <span className="badge badge-success" title="Đã liên kết Telegram">✅ Linked</span>
                    : <span className="badge badge-warning" title="Chưa liên kết">❌</span>}
                </td>
                <td>
                  <div className="action-btns">
                    <button
                      className="btn btn-icon btn-secondary"
                      title="Xem chi tiết"
                      onClick={() => handleSelectEmployee(item.employee_id)}
                    >
                      <FileText size={14} />
                    </button>
                    <button
                      className="btn btn-icon btn-secondary"
                      title="Tải PDF"
                      onClick={() => handleDownloadPdf(item.employee_id, item.employee_code)}
                    >
                      <Download size={14} />
                    </button>
                    <button
                      className="btn btn-icon btn-primary"
                      title={item.telegram_linked ? 'Gửi qua Telegram' : 'Chưa liên kết Telegram'}
                      disabled={!item.telegram_linked || sendingId === item.employee_id}
                      onClick={() => handleSendOne(item.employee_id)}
                    >
                      {sendingId === item.employee_id ? <div className="spinner-sm" /> : <Send size={14} />}
                    </button>
                  </div>
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
          <button className="btn btn-secondary" onClick={() => setShowConfig(true)} title="Cấu hình phiếu lương">
            <Settings2 size={16} /> Cấu hình
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSendAll}
            disabled={sendingAll}
            title="Gửi phiếu lương cho tất cả nhân viên đã liên kết Telegram"
          >
            {sendingAll ? <><div className="spinner-sm" /> Đang gửi...</> : <><SendHorizonal size={16} /> Gửi tất cả</>}
          </button>
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
          <div className="detail-header">
            <h2>Chi tiết nhân viên</h2>
            <div className="detail-actions">
              <button className="btn btn-secondary btn-sm" onClick={() => handleDownloadPdf(employeeDetail.employee.employee_id, employeeDetail.employee.employee_code)}>
                <Download size={14} /> Tải PDF
              </button>
              {employeeDetail.employee.telegram_linked && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleSendOne(employeeDetail.employee.employee_id)}
                  disabled={sendingId === employeeDetail.employee.employee_id}
                >
                  <Send size={14} /> Gửi Telegram
                </button>
              )}
            </div>
          </div>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Họ tên</span>
              <span className="detail-value">{employeeDetail.employee.employee_name}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Mã NV</span>
              <span className="detail-value">{employeeDetail.employee.employee_code}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Tháng</span>
              <span className="detail-value">{employeeDetail.month}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Ngày công</span>
              <span className="detail-value">{employeeDetail.employee.worked_days}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Giờ công</span>
              <span className="detail-value">{employeeDetail.employee.worked_hours.toFixed(2)}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Lương/giờ</span>
              <span className="detail-value">{employeeDetail.employee.hourly_wage.toLocaleString('vi-VN')}</span>
            </div>
            <div className="detail-item highlight">
              <span className="detail-label">Lương ước tính</span>
              <span className="detail-value">{employeeDetail.employee.estimated_salary.toLocaleString('vi-VN')} VND</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Telegram</span>
              <span className="detail-value">
                {employeeDetail.employee.telegram_linked
                  ? <span className="badge badge-success">Đã liên kết</span>
                  : <span className="badge badge-warning">Chưa liên kết</span>}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Send Results Modal */}
      {sendResults && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Kết quả gửi phiếu lương</h2>
              <button className="modal-close" onClick={() => setSendResults(null)}>×</button>
            </div>
            <div className="send-results">
              {sendResults.map((r, i) => (
                <div key={i} className={`send-result-item ${r.success ? 'success' : 'failed'}`}>
                  <span className="result-icon">{r.success ? <Check size={16} /> : <X size={16} />}</span>
                  <span className="result-name">{r.employee_name}</span>
                  <span className="result-msg">{r.message}</span>
                </div>
              ))}
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => setSendResults(null)}>Đóng</button>
            </div>
          </div>
        </div>
      )}

      {/* Slip Config Modal */}
      {showConfig && (
        <div className="modal-overlay">
          <div className="modal-content modal-lg">
            <div className="modal-header">
              <h2>Cấu hình phiếu lương</h2>
              <button className="modal-close" onClick={() => setShowConfig(false)}>×</button>
            </div>
            {configLoading && !configForm ? (
              <div className="loading-state"><div className="spinner" /></div>
            ) : configForm && (
              <div className="modal-form config-form">
                <div className="config-section">
                  <h3>Thông tin công ty</h3>
                  <div className="input-group">
                    <label>Tên công ty</label>
                    <input className="input-field" value={configForm.company_name}
                      onChange={e => setConfigForm({ ...configForm, company_name: e.target.value })} />
                  </div>
                  <div className="input-group">
                    <label>Địa chỉ</label>
                    <input className="input-field" value={configForm.company_address}
                      onChange={e => setConfigForm({ ...configForm, company_address: e.target.value })} />
                  </div>
                  <div className="input-group">
                    <label>Số điện thoại</label>
                    <input className="input-field" value={configForm.company_phone}
                      onChange={e => setConfigForm({ ...configForm, company_phone: e.target.value })} />
                  </div>
                </div>

                <div className="config-section">
                  <div className="config-section-header">
                    <h3>Khoản thu nhập thêm (+)</h3>
                    <button className="btn btn-secondary btn-sm" onClick={() => addConfigItem('earning')}>
                      <Plus size={14} /> Thêm
                    </button>
                  </div>
                  {configForm.extra_earnings.map((item, i) => (
                    <div key={i} className="config-item-row">
                      <input className="input-field" placeholder="Tên khoản (VD: Phụ cấp)" value={item.label}
                        onChange={e => updateConfigItem('earning', i, 'label', e.target.value)} />
                      <input className="input-field input-amount" type="number" placeholder="Số tiền" value={item.default_amount}
                        onChange={e => updateConfigItem('earning', i, 'default_amount', parseFloat(e.target.value) || 0)} />
                      <button className="btn btn-icon btn-danger" onClick={() => removeConfigItem('earning', i)}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                  {configForm.extra_earnings.length === 0 && <p className="text-muted">Chưa có khoản thu nhập thêm</p>}
                </div>

                <div className="config-section">
                  <div className="config-section-header">
                    <h3>Khoản khấu trừ (−)</h3>
                    <button className="btn btn-secondary btn-sm" onClick={() => addConfigItem('deduction')}>
                      <Plus size={14} /> Thêm
                    </button>
                  </div>
                  {configForm.extra_deductions.map((item, i) => (
                    <div key={i} className="config-item-row">
                      <input className="input-field" placeholder="Tên khoản (VD: BHXH)" value={item.label}
                        onChange={e => updateConfigItem('deduction', i, 'label', e.target.value)} />
                      <input className="input-field input-amount" type="number" placeholder="Số tiền" value={item.default_amount}
                        onChange={e => updateConfigItem('deduction', i, 'default_amount', parseFloat(e.target.value) || 0)} />
                      <button className="btn btn-icon btn-danger" onClick={() => removeConfigItem('deduction', i)}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                  {configForm.extra_deductions.length === 0 && <p className="text-muted">Chưa có khoản khấu trừ</p>}
                </div>

                <div className="config-section">
                  <h3>Ghi chú cuối phiếu</h3>
                  <div className="input-group">
                    <textarea className="input-field" rows={3} value={configForm.footer_note}
                      onChange={e => setConfigForm({ ...configForm, footer_note: e.target.value })} />
                  </div>
                </div>

                <div className="modal-actions">
                  <button className="btn btn-secondary" onClick={() => setShowConfig(false)}>Hủy</button>
                  <button className="btn btn-primary" onClick={handleSaveConfig} disabled={configLoading}>
                    {configLoading ? 'Đang lưu...' : 'Lưu cấu hình'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
