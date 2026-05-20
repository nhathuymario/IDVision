import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Lock, ShieldCheck, Eye, EyeOff, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'
import { passwordCheckin } from '../api'
import './CheckinPage.css'

export default function CheckinPage() {
  const [mode, setMode] = useState('password') // 'face' | 'password'
  const [time, setTime] = useState(new Date())
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  // Password mode state
  const [empCode, setEmpCode] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  // Camera state
  const videoRef = useRef(null)
  const [cameraReady, setCameraReady] = useState(false)

  const navigate = useNavigate()

  // Live clock
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  // Camera setup
  useEffect(() => {
    if (mode === 'face') {
      startCamera()
    } else {
      stopCamera()
    }
    return () => stopCamera()
  }, [mode])

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        setCameraReady(true)
      }
    } catch {
      setCameraReady(false)
    }
  }

  function stopCamera() {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(t => t.stop())
      videoRef.current.srcObject = null
    }
    setCameraReady(false)
  }

  // Password check-in
  async function handlePasswordSubmit(e) {
    e.preventDefault()
    if (loading) return
    setLoading(true)
    setResult(null)
    try {
      const res = await passwordCheckin(empCode, password)
      setResult(res)
      if (res.recognized) {
        setEmpCode('')
        setPassword('')
      }
    } catch {
      setResult({ recognized: false, message: '❌ Lỗi kết nối server.' })
    }
    setLoading(false)
    setTimeout(() => setResult(null), 8000)
  }

  // Face capture — sends frame to backend
  async function handleCapture() {
    if (!cameraReady || !videoRef.current) return
    setLoading(true)
    setResult(null)

    try {
      const canvas = document.createElement('canvas')
      canvas.width = videoRef.current.videoWidth
      canvas.height = videoRef.current.videoHeight
      canvas.getContext('2d').drawImage(videoRef.current, 0, 0)
      const base64 = canvas.toDataURL('image/jpeg', 0.85).split(',')[1]

      // In production, AI service handles this.
      // Here we send the snapshot for recognition.
      // The AI service running alongside will handle actual embedding extraction.
      setResult({
        recognized: false,
        message: '⚠️ Nhận diện khuôn mặt đang được xử lý bởi AI Service. Vui lòng dùng phương thức mật khẩu nếu AI Service chưa chạy.'
      })
    } catch {
      setResult({ recognized: false, message: '❌ Lỗi xử lý ảnh.' })
    }
    setLoading(false)
    setTimeout(() => setResult(null), 8000)
  }

  const timeStr = time.toLocaleTimeString('vi-VN', { hour12: false })
  const dateStr = time.toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })

  return (
    <div className="checkin-page">
      {/* Animated background */}
      <div className="checkin-bg">
        <div className="checkin-bg-orb orb-1" />
        <div className="checkin-bg-orb orb-2" />
        <div className="checkin-bg-orb orb-3" />
      </div>

      <div className="checkin-container">
        {/* Header */}
        <header className="checkin-header">
          <div className="checkin-logo">
            <ShieldCheck size={28} />
            <span>IDVision</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/admin/login')}>
            Admin
          </button>
        </header>

        {/* Clock */}
        <div className="checkin-clock">
          <div className="clock-time">{timeStr}</div>
          <div className="clock-date">{dateStr}</div>
        </div>

        {/* Mode tabs */}
        <div className="checkin-tabs">
          <button className={`tab-btn ${mode === 'face' ? 'active' : ''}`} onClick={() => setMode('face')}>
            <Camera size={18} /> Nhận diện khuôn mặt
          </button>
          <button className={`tab-btn ${mode === 'password' ? 'active' : ''}`} onClick={() => setMode('password')}>
            <Lock size={18} /> Mật khẩu
          </button>
        </div>

        {/* Content */}
        <div className="checkin-content">
          {/* Face mode */}
          {mode === 'face' && (
            <div className="face-mode">
              <div className="camera-box">
                <video ref={videoRef} autoPlay playsInline muted className="camera-video" />
                {cameraReady && (
                  <div className="camera-overlay">
                    <div className="face-guide">
                      <span className="corner tl" /><span className="corner tr" />
                      <span className="corner bl" /><span className="corner br" />
                    </div>
                    <div className="scan-line" />
                  </div>
                )}
                {!cameraReady && (
                  <div className="camera-placeholder">
                    <Camera size={48} strokeWidth={1} />
                    <p>Đang khởi động camera...</p>
                  </div>
                )}
              </div>
              <button className="btn btn-primary btn-lg capture-btn" onClick={handleCapture} disabled={!cameraReady || loading}>
                {loading ? <div className="spinner" /> : <Camera size={20} />}
                {loading ? 'Đang xử lý...' : 'Chấm Công'}
              </button>
              <p className="checkin-hint">Đặt khuôn mặt vào khung hình và nhấn <strong>Chấm Công</strong></p>
            </div>
          )}

          {/* Password mode */}
          {mode === 'password' && (
            <div className="password-mode">
              <div className="password-card glass">
                <div className="password-card-icon">
                  <Lock size={36} strokeWidth={1.5} />
                </div>
                <h2>Chấm công bằng mật khẩu</h2>
                <p className="text-muted">Nhập mã nhân viên và mật khẩu để chấm công</p>

                <form onSubmit={handlePasswordSubmit} className="password-form">
                  <div className="input-group">
                    <label htmlFor="empCode">Mã nhân viên</label>
                    <div className="input-with-icon">
                      <span className="input-icon"><Camera size={16} /></span>
                      <input id="empCode" className="input-field" type="text" placeholder="VD: NV001"
                        value={empCode} onChange={e => setEmpCode(e.target.value)} required autoComplete="off" />
                    </div>
                  </div>
                  <div className="input-group">
                    <label htmlFor="empPass">Mật khẩu</label>
                    <div className="input-with-icon">
                      <span className="input-icon"><Lock size={16} /></span>
                      <input id="empPass" className="input-field" type={showPassword ? 'text' : 'password'} placeholder="Nhập mật khẩu"
                        value={password} onChange={e => setPassword(e.target.value)} required />
                      <button type="button" className="pass-toggle" onClick={() => setShowPassword(!showPassword)}>
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                  <button type="submit" className="btn btn-primary btn-lg submit-btn" disabled={loading}>
                    {loading ? <div className="spinner" /> : <CheckCircle size={20} />}
                    {loading ? 'Đang xử lý...' : 'Chấm Công'}
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>

        {/* Result toast */}
        {result && (
          <div className={`checkin-result ${result.recognized ? 'result-success' : 'result-error'}`}>
            <div className="result-icon-wrapper">
              {result.recognized
                ? (result.status === 'LATE' ? <AlertTriangle size={32} /> : <CheckCircle size={32} />)
                : <XCircle size={32} />}
            </div>
            <div className="result-body">
              <h3>{result.recognized ? (result.employee_name || 'Thành công') : 'Thất bại'}</h3>
              <p>{result.message}</p>
              {result.check_in_time && (
                <span className="result-time">
                  <Clock size={14} /> {new Date(result.check_in_time).toLocaleTimeString('vi-VN')}
                </span>
              )}
            </div>
          </div>
        )}

        <footer className="checkin-footer">
          IDVision v1.0 — Powered by AI Face Recognition
        </footer>
      </div>
    </div>
  )
}
