import { useEffect, useState, useCallback } from 'react'
import { Save, Clock3, TimerReset, Wallet } from 'lucide-react'
import { getAdminPolicy, updateAdminPolicy } from '../../api'
import './Policy.css'

const DEFAULT_POLICY = {
  timezone: 'Asia/Ho_Chi_Minh',
  work_start_time: '08:00',
  break_start_time: '12:00',
  break_end_time: '13:00',
  work_end_time: '17:30',
  late_grace_minutes: 0,
  hourly_wage: 0,
}

export default function Policy() {
  const [form, setForm] = useState(DEFAULT_POLICY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const loadPolicy = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getAdminPolicy()
      setForm(data)
    } catch (e) {
      console.error(e)
      setMessage('Không tải được cấu hình, đang dùng giá trị mặc định.')
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    void loadPolicy()
  }, [loadPolicy])

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const payload = {
        ...form,
        late_grace_minutes: Number(form.late_grace_minutes),
        hourly_wage: Number(form.hourly_wage),
      }
      const updated = await updateAdminPolicy(payload)
      setForm(updated)
      setMessage('Đã lưu cấu hình chấm công.')
    } catch (e) {
      console.error(e)
      setMessage('Lưu thất bại. Kiểm tra lại dữ liệu nhập vào.')
    }
    setSaving(false)
  }

  if (loading) {
    return (
      <div className="policy-page">
        <div className="loading-state"><div className="spinner" /></div>
      </div>
    )
  }

  return (
    <div className="policy-page">
      <div className="page-header">
        <div>
          <h1>Cấu hình chấm công</h1>
          <p className="text-muted">Chỉnh giờ làm, giờ nghỉ, số phút trễ và lương theo giờ</p>
        </div>
      </div>

      <div className="card policy-help-card">
        <div className="policy-help-item">
          <Clock3 size={18} />
          <span>Giờ vào ca và giờ ra ca sẽ quyết định chấm công đúng giờ hay đi trễ.</span>
        </div>
        <div className="policy-help-item">
          <TimerReset size={18} />
          <span>Số phút trễ cho phép sẽ được dùng trước khi trừ lương.</span>
        </div>
        <div className="policy-help-item">
          <Wallet size={18} />
          <span>Lương/giờ là cơ sở tính tổng lương của từng nhân viên trong trang quản lý lương.</span>
        </div>
      </div>

      <form className="card policy-form" onSubmit={handleSubmit}>
        <div className="policy-grid-form">
          <div className="input-group">
            <label htmlFor="policy-timezone">Timezone</label>
            <input id="policy-timezone" className="input-field" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          </div>
          <div className="input-group">
            <label htmlFor="policy-work-start">Giờ vào ca</label>
            <input id="policy-work-start" type="time" className="input-field" value={form.work_start_time} onChange={(e) => setForm({ ...form, work_start_time: e.target.value })} />
          </div>
          <div className="input-group">
            <label htmlFor="policy-break-start">Giờ nghỉ bắt đầu</label>
            <input id="policy-break-start" type="time" className="input-field" value={form.break_start_time} onChange={(e) => setForm({ ...form, break_start_time: e.target.value })} />
          </div>
          <div className="input-group">
            <label htmlFor="policy-break-end">Giờ nghỉ kết thúc</label>
            <input id="policy-break-end" type="time" className="input-field" value={form.break_end_time} onChange={(e) => setForm({ ...form, break_end_time: e.target.value })} />
          </div>
          <div className="input-group">
            <label htmlFor="policy-work-end">Giờ về</label>
            <input id="policy-work-end" type="time" className="input-field" value={form.work_end_time} onChange={(e) => setForm({ ...form, work_end_time: e.target.value })} />
          </div>
          <div className="input-group">
            <label htmlFor="policy-late-grace">Số phút vào trễ cho phép</label>
            <input id="policy-late-grace" type="number" min="0" className="input-field" value={form.late_grace_minutes} onChange={(e) => setForm({ ...form, late_grace_minutes: e.target.value })} />
          </div>
          <div className="input-group">
            <label htmlFor="policy-hourly-wage">Lương 1 giờ</label>
            <input id="policy-hourly-wage" type="number" min="0" step="0.01" className="input-field" value={form.hourly_wage} onChange={(e) => setForm({ ...form, hourly_wage: e.target.value })} />
          </div>
        </div>

        {message && <div className="policy-message">{message}</div>}

        <div className="policy-actions">
          <button className="btn btn-primary" type="submit" disabled={saving}>
            <Save size={16} /> {saving ? 'Đang lưu...' : 'Lưu cấu hình'}
          </button>
        </div>
      </form>
    </div>
  )
}

