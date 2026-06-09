import { useState, useEffect, useRef } from 'react'
import { Plus, Search, Edit2, Trash2, Camera, KeyRound, MessageCircle, Copy, Check, RotateCcw, X } from 'lucide-react'
import { getEmployees, createEmployee, updateEmployee, deleteEmployee, enrollFace, getTelegramLink } from '../../api'
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
  const [enrollMethod, setEnrollMethod] = useState('upload') // 'upload' | 'camera'
  const [capturedPhotos, setCapturedPhotos] = useState([]) // Array of dataURLs
  const [enrollCameraReady, setEnrollCameraReady] = useState(false)
  const enrollVideoRef = useRef(null)

  // Telegram link modal
  const [isTelegramOpen, setIsTelegramOpen] = useState(false)
  const [telegramData, setTelegramData] = useState(null)
  const [telegramLoading, setTelegramLoading] = useState(false)
  const [copied, setCopied] = useState(false)

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
        setIsModalOpen(false)
        loadData()
      } else {
        const newEmp = await createEmployee(formData)
        setIsModalOpen(false)
        loadData()
        if (newEmp && newEmp.id) {
          // Automatically open face enrollment for the newly created employee
          openEnroll(newEmp)
        }
      }
    } catch { alert('Lỗi khi lưu nhân viên!') }
  }

  async function handleDelete(id) {
    if (!confirm('Bạn có chắc muốn xóa nhân viên này?')) return
    try {
      await deleteEmployee(id)
      loadData()
    } catch { alert('Lỗi!') }
  }

  // Camera helpers for face enrollment
  async function startEnrollCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      })
      if (enrollVideoRef.current) {
        enrollVideoRef.current.srcObject = stream
        setEnrollCameraReady(true)
      }
    } catch (err) {
      console.error(err)
      setEnrollCameraReady(false)
      alert('Không thể mở camera. Vui lòng cấp quyền hoặc chuyển sang chế độ tải lên file.')
    }
  }

  function stopEnrollCamera() {
    if (enrollVideoRef.current?.srcObject) {
      enrollVideoRef.current.srcObject.getTracks().forEach(t => t.stop())
      enrollVideoRef.current.srcObject = null
    }
    setEnrollCameraReady(false)
  }

  useEffect(() => {
    if (isEnrollOpen && enrollMethod === 'camera') {
      startEnrollCamera()
    } else {
      stopEnrollCamera()
    }
    return () => stopEnrollCamera()
  }, [isEnrollOpen, enrollMethod])

  function captureEnrollPhoto() {
    if (!enrollCameraReady || !enrollVideoRef.current) return
    if (capturedPhotos.length >= 5) {
      alert('Đã đạt số lượng ảnh tối đa (5 ảnh).')
      return
    }
    const canvas = document.createElement('canvas')
    canvas.width = enrollVideoRef.current.videoWidth
    canvas.height = enrollVideoRef.current.videoHeight
    canvas.getContext('2d').drawImage(enrollVideoRef.current, 0, 0)
    const dataURL = canvas.toDataURL('image/jpeg', 0.95)
    setCapturedPhotos([...capturedPhotos, dataURL])
  }

  function removeCapturedPhoto(index) {
    setCapturedPhotos(capturedPhotos.filter((_, i) => i !== index))
  }

  function openEnroll(emp) {
    setEnrollEmp(emp)
    setEnrollFiles([])
    setCapturedPhotos([])
    setEnrollMethod('upload')
    setIsEnrollOpen(true)
  }

  async function handleEnrollSubmit(e) {
    e.preventDefault()
    setEnrollLoading(true)
    try {
      let filesToUpload = []
      if (enrollMethod === 'upload') {
        if (enrollFiles.length === 0) {
          alert('Vui lòng chọn ảnh!')
          setEnrollLoading(false)
          return
        }
        filesToUpload = Array.from(enrollFiles)
      } else {
        if (capturedPhotos.length === 0) {
          alert('Vui lòng chụp ít nhất 1 ảnh!')
          setEnrollLoading(false)
          return
        }
        const filesPromises = capturedPhotos.map(async (dataURL, index) => {
          const res = await fetch(dataURL)
          const blob = await res.blob()
          return new File([blob], `captured_face_${index + 1}.jpg`, { type: 'image/jpeg' })
        })
        filesToUpload = await Promise.all(filesPromises)
      }

      await enrollFace(enrollEmp.id, filesToUpload)
      alert('Đăng ký khuôn mặt thành công!')
      setIsEnrollOpen(false)
      loadData()
    } catch {
      alert('Lỗi khi đăng ký khuôn mặt!')
    }
    setEnrollLoading(false)
  }

  async function openTelegramLink(emp) {
    setTelegramLoading(true)
    setIsTelegramOpen(true)
    setCopied(false)
    try {
      const data = await getTelegramLink(emp.id)
      setTelegramData(data)
    } catch (e) {
      console.error(e)
      setTelegramData(null)
      alert('Không thể tạo link Telegram. Kiểm tra bot đã được cấu hình.')
      setIsTelegramOpen(false)
    }
    setTelegramLoading(false)
  }

  function copyLink() {
    if (telegramData?.deep_link) {
      navigator.clipboard.writeText(telegramData.deep_link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
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
                  <th>Telegram</th>
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
                      {emp.telegram_chat_id
                        ? <span className="badge badge-success" title={`Chat ID: ${emp.telegram_chat_id}`}>✅ Linked</span>
                        : <span className="badge badge-warning">Chưa</span>}
                    </td>
                    <td>
                      <div className="action-btns">
                        <button className="btn btn-icon btn-secondary" title="Đăng ký Face ID" onClick={() => openEnroll(emp)}>
                          <Camera size={14} />
                        </button>
                        <button className="btn btn-icon btn-secondary" title="Liên kết Telegram" onClick={() => openTelegramLink(emp)}>
                          <MessageCircle size={14} />
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
          <div className="modal-content" style={{ maxWidth: enrollMethod === 'camera' ? '500px' : '440px' }}>
            <div className="modal-header">
              <h2>Cập nhật Face ID</h2>
              <button className="modal-close" onClick={() => setIsEnrollOpen(false)}>×</button>
            </div>
            <div className="enroll-info">
              <p>Nhân viên: <strong>{enrollEmp?.name}</strong></p>
              <p className="text-muted">Đăng ký khuôn mặt rõ nét (không đeo khẩu trang, kính râm) để hệ thống học.</p>
            </div>

            {/* Toggle tabs for file upload or direct camera capture */}
            <div className="enroll-tabs">
              <button
                type="button"
                className={`enroll-tab-btn ${enrollMethod === 'upload' ? 'active' : ''}`}
                onClick={() => setEnrollMethod('upload')}
              >
                Tải ảnh lên
              </button>
              <button
                type="button"
                className={`enroll-tab-btn ${enrollMethod === 'camera' ? 'active' : ''}`}
                onClick={() => setEnrollMethod('camera')}
              >
                Chụp bằng Camera
              </button>
            </div>

            <form onSubmit={handleEnrollSubmit} className="modal-form">
              {enrollMethod === 'upload' ? (
                <div className="input-group" style={{ padding: '0 1rem' }}>
                  <label>Chọn ảnh (.jpg, .png)</label>
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    className="input-field file-input"
                    onChange={e => setEnrollFiles(e.target.files)}
                  />
                  <p className="text-muted" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                    Có thể chọn cùng lúc nhiều ảnh (khuyên dùng 3-5 ảnh với các góc mặt khác nhau).
                  </p>
                </div>
              ) : (
                <div className="enroll-camera-container">
                  <div className="enroll-camera-box">
                    <video ref={enrollVideoRef} autoPlay playsInline muted className="enroll-video" />
                    {enrollCameraReady ? (
                      <div className="camera-overlay">
                        <div className="face-guide">
                          <span className="corner tl" /><span className="corner tr" />
                          <span className="corner bl" /><span className="corner br" />
                        </div>
                      </div>
                    ) : (
                      <div className="enroll-camera-placeholder">
                        <Camera size={36} strokeWidth={1.5} />
                        <p>Đang tải Camera...</p>
                      </div>
                    )}
                  </div>
                  
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={captureEnrollPhoto}
                    disabled={!enrollCameraReady}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                  >
                    <Camera size={16} /> Chụp ảnh ({capturedPhotos.length}/5)
                  </button>

                  {capturedPhotos.length > 0 && (
                    <div className="captured-photos-section">
                      <div className="captured-photos-header">
                        <span>Ảnh đã chụp:</span>
                        <span onClick={() => setCapturedPhotos([])} style={{ cursor: 'pointer', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <RotateCcw size={12} /> Xóa hết
                        </span>
                      </div>
                      <div className="captured-photos-grid">
                        {capturedPhotos.map((photo, index) => (
                          <div key={index} className="captured-photo-card">
                            <img src={photo} alt={`Captured ${index}`} className="captured-photo-img" />
                            <button
                              type="button"
                              className="remove-photo-btn"
                              onClick={() => removeCapturedPhoto(index)}
                              title="Xóa ảnh này"
                            >
                              <X size={10} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsEnrollOpen(false)}>Hủy</button>
                <button type="submit" className="btn btn-primary" disabled={enrollLoading}>
                  {enrollLoading ? 'Đang xử lý...' : 'Đăng ký Face ID'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}


      {/* Telegram Deep Link Modal */}
      {isTelegramOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Liên kết Telegram</h2>
              <button className="modal-close" onClick={() => { setIsTelegramOpen(false); setTelegramData(null) }}>×</button>
            </div>
            {telegramLoading ? (
              <div className="loading-state"><div className="spinner" /></div>
            ) : telegramData && (
              <div className="telegram-link-body">
                <div className="telegram-info">
                  <p>Nhân viên: <strong>{telegramData.employee_name}</strong> ({telegramData.employee_code})</p>
                  <p className="telegram-status">
                    Trạng thái: {telegramData.is_linked
                      ? <span className="badge badge-success">Đã liên kết</span>
                      : <span className="badge badge-warning">Chưa liên kết</span>}
                  </p>
                </div>

                <div className="telegram-link-section">
                  <h3>🔗 Link liên kết</h3>
                  <p className="text-muted">Gửi link này cho nhân viên. Khi họ nhấn vào link và bấm "Start" trên Telegram, hệ thống sẽ tự động liên kết.</p>
                  <div className="link-copy-row">
                    <input className="input-field" readOnly value={telegramData.deep_link} />
                    <button className="btn btn-secondary" onClick={copyLink} title="Copy link">
                      {copied ? <Check size={16} /> : <Copy size={16} />}
                    </button>
                  </div>
                </div>

                <div className="telegram-qr-section">
                  <h3>📱 QR Code</h3>
                  <p className="text-muted">Hoặc cho nhân viên quét QR code này bằng điện thoại:</p>
                  <div className="qr-container">
                    <img
                      src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(telegramData.deep_link)}`}
                      alt="QR Code"
                      className="qr-image"
                    />
                  </div>
                </div>

                <div className="telegram-steps">
                  <h3>📋 Hướng dẫn</h3>
                  <ol>
                    <li>Gửi link hoặc QR code cho nhân viên</li>
                    <li>Nhân viên mở link → Telegram mở bot <strong>@{telegramData.bot_username}</strong></li>
                    <li>Nhân viên nhấn nút <strong>"Start"</strong></li>
                    <li>Hệ thống tự động liên kết → Hoàn tất! ✅</li>
                  </ol>
                </div>
              </div>
            )}
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => { setIsTelegramOpen(false); setTelegramData(null); loadData() }}>Đóng</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
