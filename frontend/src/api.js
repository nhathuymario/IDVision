/**
 * IDVision API client — centralized fetch wrapper for Backend communication.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = { ...options.headers };

  // Add auth token if present
  const token = localStorage.getItem('admin_token');
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Auto-set Content-Type for JSON bodies
  if (options.body && typeof options.body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem('admin_token');
    // Don't redirect on employee pages
    if (globalThis.location?.pathname.startsWith('/admin')) {
      globalThis.location.href = '/admin/login';
    }
  }

  return res;
}

// ── Employee / Checkin ──────────────────────────────────────
export async function passwordCheckin(employeeCode, password) {
  const res = await request('/api/attendance/password-checkin', {
    method: 'POST',
    body: JSON.stringify({ employee_code: employeeCode, password }),
  });
  return res.json();
}

export async function faceRecognize(embedding, snapshotBase64) {
  const res = await request('/api/attendance/recognize', {
    method: 'POST',
    body: JSON.stringify({
      embedding,
      is_live: true,
      liveness_score: 1,
      snapshot_base64: snapshotBase64,
    }),
  });
  return res.json();
}

// ── Admin Auth ──────────────────────────────────────────────
export async function adminLogin(username, password) {
  const res = await request('/api/admin/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error('Invalid credentials');
  return res.json();
}

export async function adminMe() {
  const res = await request('/api/admin/me');
  if (!res.ok) throw new Error('Unauthorized');
  return res.json();
}

// ── Employees CRUD ──────────────────────────────────────────
export async function getEmployees(params = {}) {
  const q = new URLSearchParams(params).toString();
  const res = await request(`/api/employees?${q}`);
  return res.json();
}

export async function getEmployee(id) {
  const res = await request(`/api/employees/${id}`);
  return res.json();
}

export async function createEmployee(data) {
  const res = await request('/api/employees', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateEmployee(id, data) {
  const res = await request(`/api/employees/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteEmployee(id) {
  const res = await request(`/api/employees/${id}`, { method: 'DELETE' });
  return res.json();
}

// ── Enrollment ──────────────────────────────────────────────
export async function enrollFace(employeeId, files) {
  const formData = new FormData();
  files.forEach(f => formData.append('images', f));
  const res = await request(`/api/enrollment/${employeeId}`, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type — browser will add multipart boundary
  });
  return res.json();
}

export async function removeEnrollment(employeeId) {
  const res = await request(`/api/enrollment/${employeeId}`, { method: 'DELETE' });
  return res.json();
}

// ── Attendance ──────────────────────────────────────────────
export async function getTodayAttendance() {
  const res = await request('/api/attendance/today');
  return res.json();
}

export async function getAttendanceReport(dateFrom, dateTo, employeeId) {
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (employeeId) params.append('employee_id', employeeId);
  const res = await request(`/api/attendance/report?${params}`);
  return res.json();
}

export async function getTodayStats() {
  const res = await request('/api/attendance/stats/today');
  return res.json();
}

export async function refreshCache() {
  const res = await request('/api/cache/refresh', { method: 'POST' });
  return res.json();
}

// ── Admin Policy & Salary ───────────────────────────────────
export async function getAdminPolicy() {
  const res = await request('/api/admin/policy');
  if (!res.ok) throw new Error('Failed to load policy');
  return res.json();
}

export async function updateAdminPolicy(data) {
  const res = await request('/api/admin/policy', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update policy');
  return res.json();
}

export async function getSalaryOverview(month) {
  const params = new URLSearchParams();
  if (month) params.append('month', month);
  const qs = params.toString();
  const query = qs ? `?${qs}` : '';
  const res = await request(`/api/admin/salary/overview${query}`);
  if (!res.ok) throw new Error('Failed to load salary overview');
  return res.json();
}

export async function getEmployeeSalary(employeeId, month) {
  const params = new URLSearchParams();
  if (month) params.append('month', month);
  const qs = params.toString();
  const query = qs ? `?${qs}` : '';
  const res = await request(`/api/admin/salary/employee/${employeeId}${query}`);
  if (!res.ok) throw new Error('Failed to load employee salary');
  return res.json();
}

