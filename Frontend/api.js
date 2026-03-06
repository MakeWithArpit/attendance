/**
 * api.js — Shared utilities
 * Backend PK mapping:
 *  Branch  PK = branch_code  (e.g. "CSE")
 *  Student PK = student_id   (e.g. "BCS2024001")
 *  Teacher PK = employee_id  (e.g. "T001")
 *  Subject PK = subject_code (e.g. "CS301")
 */
const API_BASE = 'http://127.0.0.1:8000/api/';

const Auth = {
  save(d) {
    localStorage.setItem('access', d.access);
    localStorage.setItem('refresh', d.refresh);
    localStorage.setItem('role', d.role);
    localStorage.setItem('name', d.name || d.username || '');
    localStorage.setItem('username', d.username || '');
    if (d.role === 'student') localStorage.setItem('student_id', d.username || '');
    if (d.role === 'teacher') localStorage.setItem('employee_id', d.employee_id || d.username || '');
  },
  getAccess() { return localStorage.getItem('access'); },
  getRefresh() { return localStorage.getItem('refresh'); },
  getRole() { return localStorage.getItem('role'); },
  getName() { return localStorage.getItem('name'); },
  getUsername() { return localStorage.getItem('username'); },
  isLoggedIn() { return !!localStorage.getItem('access'); },
  clear() {
    ['access', 'refresh', 'role', 'name', 'username', 'student_id', 'employee_id']
      .forEach(k => localStorage.removeItem(k));
  },
  redirectByRole() {
    const r = this.getRole();
    if (r === 'admin')   { window.location.href = 'admin.html';   return; }
    if (r === 'teacher') { window.location.href = 'teacher.html'; return; }
    if (r === 'student') { window.location.href = 'student.html'; return; }
    // Role missing or unknown — clear corrupted auth and stay on login
    this.clear();
  }
};

async function _fetch(url, opts = {}) {
  opts.headers = opts.headers || {};
  if (!(opts.body instanceof FormData))
    opts.headers['Content-Type'] = 'application/json';
  if (Auth.getAccess())
    opts.headers['Authorization'] = 'Bearer ' + Auth.getAccess();

  let res = await fetch(API_BASE + url, opts);

  if (res.status === 401 && Auth.getRefresh()) {
    const rr = await fetch(API_BASE + 'auth/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: Auth.getRefresh() })
    });
    if (rr.ok) {
      const rd = await rr.json();
      localStorage.setItem('access', rd.access);
      opts.headers['Authorization'] = 'Bearer ' + rd.access;
      res = await fetch(API_BASE + url, opts);
    } else {
      Auth.clear();
      // Sirf tab redirect karo jab already login page pe na hon
      if (!window.location.pathname.endsWith('login.html') &&
          !window.location.pathname.endsWith('/') &&
          window.location.pathname !== '') {
        window.location.href = 'login.html';
      }
      return;
    }
  }

  let data;
  try { data = await res.json(); } catch (e) { data = {}; }
  return { ok: res.ok, status: res.status, data };
}

const GET = (url) => _fetch(url, { method: 'GET' });
const POST = (url, body) => _fetch(url, { method: 'POST', body: JSON.stringify(body) });
const PATCH = (url, body) => _fetch(url, { method: 'PATCH', body: JSON.stringify(body) });
const PUT = (url, body) => _fetch(url, { method: 'PUT', body: JSON.stringify(body) });
const DEL = (url) => _fetch(url, { method: 'DELETE' });
const FORM = (url, fd) => _fetch(url, { method: 'POST', body: fd });

function toast(msg, type) {
  type = type || 'success';
  var icons = { success: '✓', error: '✗', info: 'ℹ' };
  var c = document.getElementById('toast-container');
  if (!c) return;
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.innerHTML = '<span>' + (icons[type] || '•') + '</span> ' + msg;
  c.appendChild(t);
  requestAnimationFrame(function () { t.classList.add('show'); });
  setTimeout(function () {
    t.classList.remove('show');
    setTimeout(function () { t.remove(); }, 400);
  }, 3500);
}

function renderResponse(boxId, r) {
  var box = document.getElementById(boxId);
  if (!box) return;
  box.classList.add('show');
  var color = r.ok ? '#10b981' : '#ef4444';
  var label = r.ok ? ('✓ ' + r.status + ' OK') : ('✗ ' + r.status + ' Error');
  box.innerHTML = '<div class="res-header" style="color:' + color + '">' + label + '</div><pre>' + JSON.stringify(r.data, null, 2) + '</pre>';
}

async function DOWNLOAD(url) {
  const res = await fetch(API_BASE + url, {
    headers: { 'Authorization': 'Bearer ' + Auth.getAccess() }
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { ok: false, status: res.status, data };
  }
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : 'download';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
  return { ok: true, status: res.status, data: { message: 'Downloaded: ' + filename } };
}

// ─────────────────────────────────────────────
// Device fingerprint helper
// Generates a stable browser fingerprint used as device_id
// ─────────────────────────────────────────────
function getDeviceId() {
  let id = localStorage.getItem('_device_id');
  if (!id) {
    // Build a fingerprint from stable browser properties
    const fp = [
      navigator.userAgent,
      navigator.language,
      screen.width + 'x' + screen.height,
      Intl.DateTimeFormat().resolvedOptions().timeZone,
    ].join('|');
    // Simple hash
    let hash = 0;
    for (let i = 0; i < fp.length; i++) {
      hash = ((hash << 5) - hash) + fp.charCodeAt(i);
      hash |= 0;
    }
    id = 'dev_' + Math.abs(hash).toString(16) + '_' + Date.now().toString(36);
    localStorage.setItem('_device_id', id);
  }
  return id;
}

function getDeviceLabel() {
  return navigator.userAgent.substring(0, 200);
}

// ─────────────────────────────────────────────
// Device OTP login flow
// Call this instead of raw POST to login when
// the server returns { requires_device_otp: true }
// ─────────────────────────────────────────────
async function loginWithDeviceCheck(username, password) {
  const r = await POST('auth/login/', {
    username,
    password,
    device_id:    getDeviceId(),
    device_label: getDeviceLabel(),
  });

  if (!r.ok) return r;   // wrong credentials or other error

  if (r.data.requires_device_otp) {
    // New device detected — store pending state and show OTP screen
    sessionStorage.setItem('_pending_user_id',  r.data.user_id);
    sessionStorage.setItem('_pending_device_id', getDeviceId());
    sessionStorage.setItem('_pending_device_label', getDeviceLabel());
    return { ok: 'otp_required', data: r.data };
  }

  // Normal login — save tokens
  Auth.save(r.data);
  return r;
}

async function verifyDeviceOTP(otp) {
  const user_id      = sessionStorage.getItem('_pending_user_id');
  const device_id    = sessionStorage.getItem('_pending_device_id');
  const device_label = sessionStorage.getItem('_pending_device_label');

  if (!user_id || !device_id) {
    return { ok: false, data: { error: 'Session expired. Please log in again.' } };
  }

  const r = await POST('auth/verify-device-otp/', {
    user_id, otp, device_id, device_label
  });

  if (r.ok) {
    Auth.save(r.data);
    // Clear pending state
    sessionStorage.removeItem('_pending_user_id');
    sessionStorage.removeItem('_pending_device_id');
    sessionStorage.removeItem('_pending_device_label');
  }

  return r;
}