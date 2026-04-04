/**
 * api.js — AttendX Shared Utilities
 * Invertis University, Bareilly — Attendance Management System
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
  getAccess()   { return localStorage.getItem('access'); },
  getRefresh()  { return localStorage.getItem('refresh'); },
  getRole()     { return localStorage.getItem('role'); },
  getName()     { return localStorage.getItem('name'); },
  getUsername() { return localStorage.getItem('username'); },
  isLoggedIn() {
    const token = localStorage.getItem('access');
    if (!token) return false;
    // JWT expiry check — bina server call ke
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      if (payload.exp && payload.exp * 1000 < Date.now()) {
        // Token expired — clear auth data
        this.clear();
        return false;
      }
    } catch(e) {
      // Token malformed — clear auth data
      this.clear();
      return false;
    }
    return true;
  },
  clear() {
    ['access','refresh','role','name','username','student_id','employee_id']
      .forEach(k => localStorage.removeItem(k));
  },
  redirectByRole() {
    const r = this.getRole();
    if (r === 'admin')   { window.location.href = 'admin.html';   return; }
    if (r === 'teacher') { window.location.href = 'teacher.html'; return; }
    if (r === 'student') { window.location.href = 'student.html'; return; }
    this.clear();
  }
};

async function _fetch(url, opts = {}) {
  opts.headers = opts.headers || {};
  if (!(opts.body instanceof FormData)) opts.headers['Content-Type'] = 'application/json';
  if (Auth.getAccess()) opts.headers['Authorization'] = 'Bearer ' + Auth.getAccess();

  let res;
  try {
    res = await fetch(API_BASE + url, opts);
  } catch (networkErr) {
    // Network error (server down, connection reset, CORS, etc.)
    console.error('[_fetch] Network error:', url, networkErr.message);
    return { ok: false, status: 0, data: { error: 'Network error. Please check your connection and try again.' } };
  }

  if (res.status === 401 && Auth.getRefresh()) {
    try {
      const rr = await fetch(API_BASE + 'auth/token/refresh/', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ refresh: Auth.getRefresh() })
      });
      if (rr.ok) {
        const rd = await rr.json();
        localStorage.setItem('access', rd.access);
        opts.headers['Authorization'] = 'Bearer ' + rd.access;
        try {
          res = await fetch(API_BASE + url, opts);
        } catch (retryErr) {
          return { ok: false, status: 0, data: { error: 'Network error on retry.' } };
        }
      } else {
        Auth.clear();
        if (!window.location.pathname.endsWith('login.html')) window.location.href = 'login.html';
        return { ok: false, status: 401, data: { error: 'Session expired. Please login again.' } };
      }
    } catch (refreshErr) {
      Auth.clear();
      return { ok: false, status: 401, data: { error: 'Session expired. Please login again.' } };
    }
  }

  let data;
  try { data = await res.json(); } catch(e) { data = {}; }
  return { ok: res.ok, status: res.status, data };
}

const GET  = url       => _fetch(url, {method:'GET'});
const POST = (url,b)   => _fetch(url, {method:'POST',  body:JSON.stringify(b)});
const PATCH= (url,b)   => _fetch(url, {method:'PATCH', body:JSON.stringify(b)});
const PUT  = (url,b)   => _fetch(url, {method:'PUT',   body:JSON.stringify(b)});
const DEL  = url       => _fetch(url, {method:'DELETE'});
const FORM = (url,fd)  => _fetch(url, {method:'POST',  body:fd});

// Public POST — does not send Authorization header
// Forgot-password aur reset-password ke liye — expired token se 401 avoid karta hai
async function POST_PUBLIC(url, body) {
  try {
    const res = await fetch(API_BASE + url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    let data;
    try { data = await res.json(); } catch(e) { data = {}; }
    return { ok: res.ok, status: res.status, data };
  } catch(e) {
    return { ok: false, status: 0, data: { error: 'Network error. Please check your connection.' } };
  }
}

async function DOWNLOAD(url) {
  const res = await fetch(API_BASE + url, { headers: {'Authorization':'Bearer '+Auth.getAccess()} });
  if (!res.ok) { const d = await res.json().catch(()=>({})); return {ok:false,data:d}; }
  const blob = await res.blob();
  const m = (res.headers.get('Content-Disposition')||'').match(/filename="?([^"]+)"?/);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = m?m[1]:'download'; a.click();
  URL.revokeObjectURL(a.href);
  return {ok:true, data:{message:'Downloaded'}};
}

function toast(msg, type='success') {
  const icons = {success:'✓',error:'✗',info:'ℹ',warning:'⚠'};
  const c = document.getElementById('toast-container');
  if (!c) return;
  const t = document.createElement('div');
  t.className = 'toast toast-'+type;
  t.innerHTML = `<span>${icons[type]||'•'}</span> ${msg}`;
  c.appendChild(t);
  requestAnimationFrame(()=>t.classList.add('show'));
  setTimeout(()=>{ t.classList.remove('show'); setTimeout(()=>t.remove(),400); }, 3500);
}

function getDeviceId() {
  let id = localStorage.getItem('_device_id');
  if (!id) {
    const fp = [navigator.userAgent,navigator.language,screen.width+'x'+screen.height].join('|');
    let hash=0; for(let i=0;i<fp.length;i++){hash=((hash<<5)-hash)+fp.charCodeAt(i);hash|=0;}
    id='dev_'+Math.abs(hash).toString(16)+'_'+Date.now().toString(36);
    localStorage.setItem('_device_id',id);
  }
  return id;
}
function getDeviceLabel() { return navigator.userAgent.substring(0,200); }

async function loginWithDeviceCheck(username, password) {
  const r = await POST('auth/login/',{username,password,device_id:getDeviceId(),device_label:getDeviceLabel()});
  if (!r.ok) return r;
  if (r.data.requires_device_otp) {
    sessionStorage.setItem('_pending_user_id', r.data.user_id);
    sessionStorage.setItem('_pending_device_id', getDeviceId());
    sessionStorage.setItem('_pending_device_label', getDeviceLabel());
    return {ok:'otp_required', data:r.data};
  }
  Auth.save(r.data); return r;
}

async function verifyDeviceOTP(otp) {
  const user_id=sessionStorage.getItem('_pending_user_id');
  const device_id=sessionStorage.getItem('_pending_device_id');
  const device_label=sessionStorage.getItem('_pending_device_label');
  if (!user_id||!device_id) return {ok:false,data:{error:'Session expired.'}};
  const r = await POST('auth/verify-device-otp/',{user_id,otp,device_id,device_label});
  if (r.ok) {
    Auth.save(r.data);
    ['_pending_user_id','_pending_device_id','_pending_device_label'].forEach(k=>sessionStorage.removeItem(k));
  }
  return r;
}

async function logout() {
  try { await POST('auth/logout/',{refresh:Auth.getRefresh()}); } catch(e){}
  Auth.clear(); window.location.href='login.html';
}

function formatDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'});
}
function pctClass(p) { return p>=75?'safe':p>=60?'warn':'crit'; }
function pctBadge(p) {
  const cls=pctClass(p);
  return `<span class="pct-badge pct-${cls}">${typeof p==='number'?p.toFixed(1):p}%</span>`;
}
function apiTag(method,endpoint) {
  const mc={GET:'#2563eb',POST:'#16a34a',PATCH:'#d97706',DELETE:'#dc2626'};
  return `<div class="api-tag"><span class="api-method" style="background:${mc[method]||'#6b7280'}">${method}</span><code class="api-ep">/api/${endpoint}</code></div>`;
}