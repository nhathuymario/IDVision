import { useState, useEffect } from 'react'
import { Plus, Search, Edit2, Trash2, Camera, KeyRound } from 'lucide-react'
import { getEmployees, createEmployee, updateEmployee, deleteEmployee, enrollFace } from '../../api'
import './Employees.css'

export default function Employees() {
  const [employees, setEmployees] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingEmp, setEditingEmp] = useState(null)
  
  // Form state
  const [formData, setFormData] = useState({ name: '', employee_code: '', department: '', telegram_chat_id: '', password: '' })

  // Enroll modal
  const [isEnrollOpen, setIsEnrollOpen] = useState(false)
  const [enrollEmp, setEnrollEmp] = useState(null)
  const [enrollFiles, setEnrollFiles] = useState([])
  const [enrollLoading, setEnrollLoading] = useState(false)

  useEffect(() => { loadData() }, [page, search])

  async function loadData() {
    setLoading(true)
    try {
      const res = await getEmployees({ skip: page * 20, limit: 20, search })
      setEmployees(res.employees)
      setTotal(res.total)
    } catch(e) { console.error(e) }
    setLoading(false)
  }

  function openModal(emp = null) {
    setEditingEmp(emp)
    if (emp) {
      setFormData({
        name: emp.name, employee_code: emp.employee_code,
        department: emp.department || '', telegram_chat_id: emp.telegram_chat_id || '',
        password: '' // Don't show existing password
      })
    } else {
      setFormData({ name: '', employee_code: '', department: '', telegram_chat_id: '', password: '' })
    }
    setIsModalOpen(true)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      if (editingEmp) {
        // Remove empty password so it doesn't update if untouched
        const dataToUpdate = { ...formData }
        if (!dataToUpdate.password) delete dataToUpdate.password
        await updateEmployee(editingEmp.id, dataToUpdate)
      } else {
        await createEmployee(formData)
      }
      setIsModalOpen(false)
      loadData()
    } catch { alert('Lỗi khi lưu nhân viên!') }
  }

  async function handleDelete(id) {
    if (!confirm('Bạn có chắc muốn xóa nhân viên này?')) return
    try {
      await deleteEmployee(id)
      loadData()
    } catch { alert('Lỗi!') }
  }

  function openEnroll(emp) {
    setEnrollEmp(emp)
    setEnrollFiles([])
    setIsEnrollOpen(true)
  }

  async function handleEnrollSubmit(e) {
    e.preventDefault()
    if (enrollFiles.length === 0) return alert('Vui lòng chọn ảnh')
    setEnrollLoading(true)
    try {
      await enrollFace(enrollEmp.id, Array.from(enrollFiles))
      alert('Đăng ký khuôn mặt thành công!')
      setIsEnrollOpen(false)
      loadData()
    } catch { alert('Lỗi khi đăng ký khuôn mặt!') }
    setEnrollLoading(false)
  }

  return (
    <div className="employees-page">
      <div className="page-header">
        <div>
          <h1>Quản lý Nhân viên</h1>
          <p className="text-muted">Tổng số: {total} nhân viên đang hoạt động</p>
        </div>
        <button className="btn btn-primary" onClick={() => openModal()}>
          <Plus size={16} /> Thêm nhân viên
        </button>
      </div>

      <div className="card">
        <div className="table-toolbar">
          <div className="search-box input-with-icon">
            <span className="input-icon"><Search size={16} /></span>
            <input type="text" className="input-field" placeholder="Tìm tên hoặc mã..."
              value={search} onChange={e => {setSearch(e.target.value); setPage(0)}} />
          </div>
        </div>

        {loading ? (
          <div className="loading-state"><div className="spinner" /></div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Mã NV</th>
                  <th>Họ Tên</th>
                  <th>Phòng ban</th>
                  <th>Face ID</th>
                  <th>Mật khẩu</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {employees.map(emp => (
                  <tr key={emp.id}>
                    <td><strong>{emp.employee_code}</strong></td>
                    <td>{emp.name}</td>
                    <td>{emp.department || '—'}</td>
                    <td>
                      {emp.is_enrolled 
                        ? <span className="badge badge-success">Đã ĐK</span>
                        : <span className="badge badge-warning">Chưa ĐK</span>}
                    </td>
                    <td>
                      {emp.has_password
                        ? <span className="badge badge-success">Có</span>
                        : <span className="badge badge-warning">Không</span>}
                    </td>
                    <td>
                      <div className="action-btns">
                        <button className="btn btn-icon btn-secondary" title="Đăng ký Face ID" onClick={() => openEnroll(emp)}>
                          <Camera size={14} />
                        </button>
                        <button className="btn btn-icon btn-secondary" title="Sửa" onClick={() => openModal(emp)}>
                          <Edit2 size={14} />
                        </button>
                        <button className="btn btn-icon btn-danger" title="Xóa" onClick={() => handleDelete(emp.id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add/Edit Modal */}
      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>{editingEmp ? 'Sửa nhân viên' : 'Thêm nhân viên'}</h2>
              <button className="modal-close" onClick={() => setIsModalOpen(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              <div className="input-group">
                <label>Họ tên *</label>
                <input required className="input-field" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
              </div>
              <div className="input-group">
                <label>Mã NV *</label>
                <input required disabled={!!editingEmp} className="input-field" value={formData.employee_code} onChange={e => setFormData({...formData, employee_code: e.target.value})} />
              </div>
              <div className="input-group">
                <label>Phòng ban</label>
                <input className="input-field" value={formData.department} onChange={e => setFormData({...formData, department: e.target.value})} />
              </div>
              <div className="input-group">
                <label>Telegram Chat ID (nhận thông báo riêng)</label>
                <input className="input-field" value={formData.telegram_chat_id} onChange={e => setFormData({...formData, telegram_chat_id: e.target.value})} />
              </div>
              <div className="input-group">
                <label>Mật khẩu chấm công {editingEmp ? '(Để trống nếu không đổi)' : ''}</label>
                <div className="input-with-icon">
                  <span className="input-icon"><KeyRound size={16} /></span>
                  <input type="password" className="input-field" value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} />
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>Hủy</button>
                <button type="submit" className="btn btn-primary">Lưu</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Enroll Modal */}
      {isEnrollOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Cập nhật Face ID</h2>
              <button className="modal-close" onClick={() => setIsEnrollOpen(false)}>×</button>
            </div>
            <div className="enroll-info">
              <p>Nhân viên: <strong>{enrollEmp?.name}</strong></p>
              <p className="text-muted">Tải lên 1-5 ảnh rõ mặt (không đeo khẩu trang) để hệ thống học.</p>
            </div>
            <form onSubmit={handleEnrollSubmit} className="modal-form">
              <div className="input-group">
                <label>Chọn ảnh (.jpg, .png)</label>
                <input type="file" multiple accept="image/*" className="input-field file-input"
                  onChange={e => setEnrollFiles(e.target.files)} />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setIsEnrollOpen(false)}>Hủy</button>
                <button type="submit" className="btn btn-primary" disabled={enrollLoading}>
                  {enrollLoading ? 'Đang xử lý...' : 'Upload & Đăng ký'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
