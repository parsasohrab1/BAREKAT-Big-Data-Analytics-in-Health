const API_BASE = window.BAREKAT_API || `${window.location.protocol}//${window.location.hostname}:8000`;
const TOKEN_KEY = "barekat_mobile_token";

const $ = (id) => document.getElementById(id);

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (resp.status === 401) {
    logout();
    throw new Error("نشست منقضی شده");
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `خطا ${resp.status}`);
  }
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) return resp.json();
  return resp;
}

function showDashboard() {
  $("login-screen").classList.add("hidden");
  $("dashboard-screen").classList.remove("hidden");
  $("bottom-nav").classList.remove("hidden");
  $("btn-logout").classList.remove("hidden");
}

function logout() {
  setToken(null);
  $("login-screen").classList.remove("hidden");
  $("dashboard-screen").classList.add("hidden");
  $("bottom-nav").classList.add("hidden");
  $("btn-logout").classList.add("hidden");
}

async function login() {
  const username = $("username").value.trim();
  const password = $("password").value;
  $("login-error").classList.add("hidden");
  try {
    const data = await api("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    setToken(data.access_token);
    $("user-role").textContent = data.role || "کاربر";
    if (data.tenant_slug) $("tenant-name").textContent = data.tenant_slug;
    showDashboard();
    await refreshAll();
  } catch (e) {
    $("login-error").textContent = e.message;
    $("login-error").classList.remove("hidden");
  }
}

function severityClass(sev) {
  return sev === "critical" ? "critical" : sev === "high" ? "high" : "";
}

async function loadAlerts() {
  const data = await api("/api/v1/analytics/alerts");
  const alerts = data.alerts || [];
  $("alert-badge").textContent = alerts.length;
  const list = $("alert-list");
  list.innerHTML = "";
  if (!alerts.length) {
    list.innerHTML = '<li class="muted" style="padding:1rem;text-align:center">هشدار فعالی نیست</li>';
    return;
  }
  alerts.slice(0, 20).forEach((a) => {
    const li = document.createElement("li");
    li.className = `alert-item ${severityClass(a.severity)}`;
    li.innerHTML = `
      <div class="type">${a.severity?.toUpperCase()} — ${a.alert_type || ""}</div>
      <div class="msg">${a.message || ""}</div>
      <div class="type">بیمار: ${a.patient_id || "—"}</div>`;
    list.appendChild(li);
  });
  const critical = alerts.filter((a) => a.severity === "critical").length;
  $("kpi-critical").textContent = critical;
}

async function loadWeekly() {
  const data = await api("/api/v1/reports/weekly/summary");
  $("kpi-admissions").textContent = data.admissions_total ?? "—";
  $("kpi-readmit").textContent = data.readmission_rate_pct ?? "—";
  $("report-period").textContent = `${data.period_start} — ${data.period_end}`;
  const token = getToken();
  $("btn-excel").href = `${API_BASE}/api/v1/reports/weekly/export/excel`;
  $("btn-pdf").href = `${API_BASE}/api/v1/reports/weekly/export/pdf`;
  $("btn-excel").onclick = (e) => downloadAuth(e, "/api/v1/reports/weekly/export/excel", "weekly.xlsx");
  $("btn-pdf").onclick = (e) => downloadAuth(e, "/api/v1/reports/weekly/export/pdf", "weekly.pdf");
}

async function downloadAuth(e, path, filename) {
  e.preventDefault();
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!resp.ok) return;
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function refreshAll() {
  try {
    await Promise.all([loadAlerts(), loadWeekly()]);
  } catch (e) {
    console.warn(e);
  }
}

function connectWebSocket() {
  const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = API_BASE.replace(/^https?:\/\//, "");
  const ws = new WebSocket(`${wsProto}://${host}/api/v1/stream/alerts`);
  ws.onmessage = () => loadAlerts();
  ws.onclose = () => setTimeout(connectWebSocket, 5000);
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/mobile/sw.js").catch(() => {});
}

$("btn-login").addEventListener("click", login);
$("btn-logout").addEventListener("click", logout);

if (getToken()) {
  showDashboard();
  refreshAll();
  connectWebSocket();
  setInterval(refreshAll, 60000);
}
