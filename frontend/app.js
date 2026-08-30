/* SomTech SchoolSystem — Private School Management & State Compliance Monitoring
 * Multi-tenant SaaS frontend: State portal (read-only academics + red alarms)
 * and tenant ERP (students, attendance, marks, private billing).
 */
// The API also maintains an HttpOnly session cookie.  Local storage is a
// convenience, not a requirement: some phone/private browsers deny writes to
// it, and the portal must still enter after a successful sign-in.
const storage = {
  get(key) {
    try { return window.localStorage.getItem(key); } catch { return null; }
  },
  set(key, value) {
    try { window.localStorage.setItem(key, value); return true; } catch { return false; }
  },
  clear() {
    try { window.localStorage.clear(); } catch { /* cookie session remains */ }
  },
};

function storedUser() {
  try {
    const value = storage.get("user");
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

const API = {
  token: storage.get("token"),
  user: storedUser(),
  view: null,
  ws: null,
  classCache: [],
  yearCache: [],
};

/* ---------------- helpers ---------------- */
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    // `include` guarantees the HttpOnly session cookie is sent, which is the
    // only auth mechanism that survives reverse proxies and embedded frames
    // that strip the Authorization header.
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(API.token ? { Authorization: `Bearer ${API.token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch { /* empty */ }
  if (!res.ok) {
    if (res.status === 401 && API.token) {
      // Session expired / revoked — return to the sign-in screen cleanly.
      storage.clear();
      API.token = null; API.user = null;
      toast("Session expired", "Please sign in again.", "warn");
      setTimeout(() => location.reload(), 1200);
    }
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    const err = new Error(detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function toast(title, msg, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<strong>${esc(title)}</strong>${esc(msg)}`;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), kind === "alarm" ? 12000 : 6000);
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : iso + "T00:00:00");
  return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
const todayISO = () => new Date().toISOString().slice(0, 10);

/* ---------------- auth ---------------- */
$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#loginError").classList.add("hidden");
  $("#loginBtn").disabled = true;
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: { email: $("#loginEmail").value.trim(), password: $("#loginPassword").value },
    });
    API.token = data.access_token;
    API.user = data.user;
    // The cookie sent by the API is enough for the portal if this browser
    // disallows persistent local storage (common in privacy modes on mobile).
    storage.set("token", API.token);
    storage.set("user", JSON.stringify(API.user));
    enterApp();
  } catch (err) {
    $("#loginError").textContent = err.message;
    $("#loginError").classList.remove("hidden");
  } finally {
    $("#loginBtn").disabled = false;
  }
});

document.querySelectorAll(".demo-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    $("#loginEmail").value = chip.dataset.email;
    $("#loginPassword").value = chip.dataset.pass;
    $("#loginForm").requestSubmit();
  });
});

$("#logoutBtn").addEventListener("click", async () => {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* best effort */ }
  storage.clear();
  API.token = null; API.user = null;
  if (API.ws) { try { API.ws.close(); } catch { /* noop */ } }
  location.reload();
});

/* ---------------- websocket live stream ---------------- */
function connectWS() {
  if (!API.token) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(API.token)}`);
  API.ws = ws;
  ws.onopen = () => {
    const pill = $("#wsPill");
    pill.classList.add("live");
    pill.innerHTML = '<span class="dot"></span> live';
  };
  ws.onclose = () => {
    $("#wsPill").classList.remove("live");
    $("#wsPill").innerHTML = '<span class="dot"></span> offline';
    setTimeout(connectWS, 3000);
  };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    handleLiveEvent(msg);
  };
}

function handleLiveEvent(msg) {
  const { type, payload } = msg;
  if (type === "connected") return;
  if (type === "red_alarm") {
    showAlarmBanner(`🚨 RED ALARM — ${payload.school_name ?? "A school"} missed the 12:00 PM attendance deadline. Escalated at 15:00.`);
    toast("🚨 RED ALARM TRIGGERED", payload.message || "Compliance breach detected.", "alarm");
    if (API.view === "state-map") loadStateMap();
    if (API.view === "alarms") loadAlarmFeed();
  } else if (type === "attendance_submitted") {
    toast("✅ Attendance roster submitted", `School #${payload.school_id} submitted ${payload.date}${payload.late ? " (LATE)" : ""}`, "success");
    if (API.view === "state-map") loadStateMap();
    if (API.view === "overview") renderOverview();
  } else if (type === "exam_published") {
    toast("📤 Exam marks published to State", `${payload.class_label} · ${payload.subject} · ${payload.exam_name} (${payload.records_released} records)`, "success");
    if (API.view === "state-analytics") loadAnalytics();
  } else if (type === "audit_completed") {
    toast("⏱️ 15:00 audit completed", `${payload.alarm_count} red alarm(s) raised.`, payload.alarm_count ? "alarm" : "success");
    if (API.view === "state-map") loadStateMap();
  } else if (type === "attendance_recorded") {
    if (API.view === "state-attendance") loadLiveAttendance();
  }
}

function showAlarmBanner(text) {
  $("#alarmBannerText").textContent = text;
  $("#alarmBanner").classList.remove("hidden");
}

/* ---------------- navigation ---------------- */
const NAV = {
  state_inspector: [
    { id: "state-map", label: "🚨 Command Map & Alarms" },
    { id: "lookup", label: "🔎 Student ID Lookup" },
    { id: "state-analytics", label: "📊 Grade Analytics" },
    { id: "state-attendance", label: "📋 Live Attendance" },
    { id: "alarms", label: "📡 Communication Feed" },
    { id: "exam-events", label: "📤 Publication Ledger" },
  ],
  school_manager: [
    { section: "Compliance" },
    { id: "overview", label: "🏫 Overview" },
    { section: "Academics" },
    { id: "students", label: "🎓 Students" },
    { id: "classes", label: "🏛️ Classes & Subjects" },
    { id: "attendance", label: "📋 Attendance" },
    { id: "marks", label: "📝 Exam Marks" },
    { section: "Private ERP 🔒" },
    { id: "billing", label: "💰 Billing & Finance" },
  ],
  teacher: [
    { id: "overview", label: "🏫 Overview" },
    { id: "attendance", label: "📋 Attendance" },
    { id: "marks", label: "📝 Exam Marks" },
  ],
};

const VIEWS = {
  "state-map": { title: "State Supervisor Command Map", render: renderStateMap },
  lookup: { title: "Statewide Student ID Lookup Engine", render: renderLookup },
  "state-analytics": { title: "Class 1-12 Grade Analytics (Published Exams Only)", render: renderAnalytics },
  "state-attendance": { title: "Live Attendance Visibility", render: renderStateAttendance },
  alarms: { title: "Communication Gateway — Red Alarm Feed", render: renderAlarms },
  "exam-events": { title: "Exam Submission Events (Immutable Ledger)", render: renderExamEvents },
  overview: { title: "School Overview", render: renderOverview },
  students: { title: "Student Registry", render: renderStudents },
  classes: { title: "Classes & Subjects", render: renderClasses },
  attendance: { title: "Daily Attendance & 12:00 PM Deadline", render: renderAttendance },
  marks: { title: "Exam Marks & Publish Valve", render: renderMarks },
  billing: { title: "Private Billing & Finance 🔒", render: renderBilling },
};

function enterApp() {
  $("#loginView").classList.add("hidden");
  $("#appView").classList.remove("hidden");
  const u = API.user;
  $("#whoami").textContent = `${u.first_name ?? ""} ${u.last_name ?? ""} · ${u.role}${u.school_name ? " · " + u.school_name : ""}`.trim();
  $("#topSub").textContent = (u.role === "state_inspector" ? "State Government Super-Admin Portal" : `${u.school_name} — Tenant ERP`) + (API.version ? ` · v${API.version}` : "");
  const nav = NAV[u.role] ?? [];
  $("#sidenav").innerHTML = nav.map((item) =>
    item.section
      ? `<div class="nav-section">${esc(item.section)}</div>`
      : `<button class="nav-item" data-view="${item.id}">${esc(item.label)}</button>`
  ).join("");
  document.querySelectorAll(".nav-item").forEach((btn) =>
    btn.addEventListener("click", () => setView(btn.dataset.view))
  );
  const first = nav.find((n) => n.id);
  // Render the workspace before opening the optional real-time channel. Some
  // mobile browsers reject local ws:// connections; that must never prevent a
  // successfully authenticated user from entering the portal.
  setView(resolveLandingView(first ? first.id : "overview", nav));
  try {
    connectWS();
  } catch (error) {
    console.warn("Live alert channel unavailable; continuing without WebSocket.", error);
  }
}

/* STEP 4 routing: /admin/state and /admin/school arm the matching workspace. */
function resolveLandingView(defaultView, nav) {
  const path = location.pathname;
  const ids = new Set(nav.map((n) => n.id).filter(Boolean));
  if (path.startsWith("/admin/state")) {
    if (API.user.role === "state_inspector") return "state-map";
    toast("Access denied", "The State Admin Panel requires the state_inspector role.", "warn");
    return defaultView;
  }
  if (path.startsWith("/admin/school")) {
    if (API.user.role !== "state_inspector") return "overview";
    toast("Access denied", "The School ERP Portal is for school_manager / teacher roles.", "warn");
    return defaultView;
  }
  return defaultView;
}

function setView(id) {
  API.view = id;
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === id));
  const view = VIEWS[id];
  $("#topTitle").textContent = view.title;
  $("#content").innerHTML = `<div class="empty">Loading…</div>`;
  view.render().catch((err) => {
    $("#content").innerHTML = `<div class="panel"><p class="empty">⚠️ ${esc(err.message)}</p></div>`;
  });
}

/* ---------------- STATE: command map ---------------- */
async function renderStateMap() {
  $("#content").innerHTML = `
    <div class="toolbar">
      <button class="btn btn-danger" id="runAudit">▶ Run 15:00 Red Alarm Audit now</button>
      <select id="mapFilter" aria-label="Filter schools">
        <option value="all">All active schools</option>
        <option value="alarms">🚨 Alarms only</option>
        <option value="compliant">✅ Compliant only</option>
      </select>
      <button class="btn" id="mapCsv">⬇ Export CSV</button>
      <span class="note" style="margin:0">Worker cron fires automatically at 15:00 daily (3h past the 12:00 PM deadline).</span>
    </div>
    <div class="stat-grid" id="mapStats"></div>
    <div class="panel">
      <h3>Active Private Schools — Attendance Compliance</h3>
      <p class="sub">View A: State Supervisor Core Command Map &amp; Alarm Portal · generated live</p>
      <div class="tbl-wrap"><table class="tbl" id="mapTable"></table></div>
    </div>`;
  $("#runAudit").addEventListener("click", async () => {
    $("#runAudit").disabled = true;
    try {
      const r = await api("/api/v1/state/audit/run", { method: "POST" });
      toast("Audit executed", `${r.red_alarms_raised} red alarm(s) raised this run.`, r.red_alarms_raised ? "alarm" : "success");
      loadStateMap();
    } catch (err) { toast("Audit failed", err.message, "alarm"); }
    finally { $("#runAudit").disabled = false; }
  });
  $("#mapFilter").addEventListener("change", () => renderMapRows());
  $("#mapCsv").addEventListener("click", exportMapCsv);
  await loadStateMap();
}

function mapFilteredRows() {
  const rows = API.mapData?.schools ?? [];
  const mode = $("#mapFilter")?.value ?? "all";
  if (mode === "alarms") return rows.filter((r) => r.is_red_alarm_active);
  if (mode === "compliant") return rows.filter((r) => r.daily_attendance_logged && !r.is_red_alarm_active);
  return rows;
}

function exportMapCsv() {
  const rows = mapFilteredRows();
  const header = ["School", "License", "Roster submitted", "Time received", "Red alarm", "Compliance status"];
  const body = rows.map((r) => [
    r.school_name, r.state_license_number,
    r.daily_attendance_logged ? "YES" : "NO", r.time_received ?? "",
    r.is_red_alarm_active ? "YES" : "NO", r.state_compliance_status.replace(/[^\x20-\x7E]/g, "").trim(),
  ]);
  const csv = [header, ...body].map((line) => line.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `state-compliance-map-${todayISO()}.csv` });
  a.click();
  URL.revokeObjectURL(url);
  toast("Export ready", `${rows.length} school row(s) exported to CSV.`, "success");
}

async function loadStateMap() {
  const data = await api("/api/v1/state/compliance-map");
  API.mapData = data;
  const s = data.summary;
  $("#mapStats").innerHTML = `
    <div class="stat-card"><div class="k">Active schools</div><div class="v">${s.active_schools}</div></div>
    <div class="stat-card green"><div class="k">Compliant</div><div class="v">${s.compliant}</div></div>
    <div class="stat-card amber"><div class="k">Pending</div><div class="v">${s.pending}</div></div>
    <div class="stat-card red"><div class="k">🚨 Red alarms</div><div class="v">${s.red_alarms}</div></div>`;
  renderMapRows();
  if (data.schools.some((r) => r.is_red_alarm_active)) {
    showAlarmBanner(`🚨 ${data.schools.filter((r) => r.is_red_alarm_active).map((r) => r.school_name).join(", ")} — RED ALARM: attendance overdue by 3+ hours.`);
  }
}

function renderMapRows() {
  const rows = mapFilteredRows();
  $("#mapTable").innerHTML = `
    <thead><tr><th>School</th><th>Today's roster</th><th>Alarm</th><th>Compliance status</th></tr></thead>
    <tbody>${rows.map((r) => `
      <tr>
        <td><strong>${esc(r.school_name)}</strong><div class="mono">${esc(r.state_license_number)}</div></td>
        <td>${r.daily_attendance_logged ? `<span class="pill ok">SUBMITTED</span><div class="note">${fmtTime(r.time_received)}</div>` : `<span class="pill warn">NOT SUBMITTED</span>`}</td>
        <td>${r.is_red_alarm_active ? '<span class="pill alarm">RED ALARM</span>' : '<span class="pill dim">—</span>'}</td>
        <td>${esc(r.state_compliance_status)}</td>
      </tr>`).join("") || '<tr><td colspan="4" class="empty">No schools match this filter.</td></tr>'}</tbody>`;
}

/* ---------------- STATE: student lookup ---------------- */
async function renderLookup() {
  $("#content").innerHTML = `
    <div class="panel">
      <h3>Statewide Student ID National Lookup Engine</h3>
      <p class="sub">View B — deep search across Class 1-12 by national tracking ID (STU-…), guardian surname or guardian phone number</p>
      <div class="toolbar">
        <div class="field" style="flex:1">Query
          <input id="lookupQ" placeholder='e.g. "STU-2026-KX482" or "Farah"' style="width:100%" />
        </div>
        <button class="btn btn-primary" id="lookupBtn">Search</button>
      </div>
      <div style="overflow-x:auto"><table class="tbl" id="lookupTable"></table></div>
    </div>`;
  $("#lookupBtn").addEventListener("click", doLookup);
  $("#lookupQ").addEventListener("keydown", (e) => e.key === "Enter" && doLookup());
  $("#lookupTable").innerHTML = '<tbody><tr><td class="empty">Enter a query to search the national registry.</td></tr></tbody>';
}

async function doLookup() {
  const q = $("#lookupQ").value.trim();
  if (!q) return;
  $("#lookupTable").innerHTML = '<tbody><tr><td class="empty">Searching…</td></tr></tbody>';
  try {
    const data = await api(`/api/v1/state/students/search?q=${encodeURIComponent(q)}`);
    const rows = data.results.map((r) => `
      <tr>
        <td class="mono">${esc(r.national_student_id)}</td>
        <td><strong>${esc(r.first_name)} ${esc(r.last_name)}</strong></td>
        <td>${esc(r.class_level ?? "—")} ${esc(r.class_stream ?? "")}</td>
        <td>${esc(r.school_name)}</td>
        <td>${esc(r.guardian_name ?? "—")}<div class="note">${esc(r.guardian_relationship ?? "")}</div></td>
        <td>${esc(r.guardian_phone ?? "—")}<div class="note">SOS: ${esc(r.emergency_contact_phone ?? "—")}</div></td>
      </tr>`).join("");
    $("#lookupTable").innerHTML = `
      <thead><tr><th>National ID</th><th>Student</th><th>Class</th><th>School</th><th>Guardian</th><th>Contacts</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="6" class="empty">No matches for “${esc(q)}”</td></tr></tbody>`}</tbody>`;
  } catch (err) {
    $("#lookupTable").innerHTML = `<tbody><tr><td class="empty">⚠️ ${esc(err.message)}</td></tr></tbody>`;
  }
}

/* ---------------- STATE: analytics ---------------- */
async function renderAnalytics() {
  const schools = await api("/api/v1/state/schools");
  $("#content").innerHTML = `
    <div class="firewall-note">🔒 Exam Data Release Valve — this portal aggregates <strong>published exams only</strong>. Private school drafts are structurally invisible here.</div>
    <div class="toolbar">
      <div class="field">School
        <select id="anSchool"><option value="">All schools</option>${schools.schools.map((s) => `<option value="${s.id}">${esc(s.school_name)}</option>`).join("")}</select>
      </div>
      <div class="field">Class level
        <select id="anLevel"><option value="">All levels</option>${Array.from({ length: 12 }, (_, i) => `<option>Class ${i + 1}</option>`).join("")}</select>
      </div>
      <button class="btn btn-primary" id="anRun">Benchmark</button>
    </div>
    <div class="panel"><h3>View C — Grade Analytics &amp; Benchmarking</h3>
      <div style="overflow-x:auto"><table class="tbl" id="anTable"></table></div></div>`;
  $("#anRun").addEventListener("click", loadAnalytics);
  await loadAnalytics();
}

async function loadAnalytics() {
  const params = new URLSearchParams();
  const school = $("#anSchool")?.value; const level = $("#anLevel")?.value;
  if (school) params.set("school_id", school);
  if (level) params.set("class_level", level);
  const data = await api(`/api/v1/state/analytics/grades?${params}`);
  const rows = data.rows.map((r) => `
    <tr>
      <td><strong>${esc(r.school_name)}</strong></td><td>${esc(r.class_level)}</td><td>${esc(r.subject_name)}</td>
      <td>${r.total_marked_records}</td>
      <td><div class="bar" title="Average ${r.structural_average_mark}"><span style="width:${Math.min(100, r.structural_average_mark ?? 0)}%"></span></div></td>
      <td><strong>${r.structural_average_mark?.toFixed(2)}</strong></td>
      <td>${r.peak_score?.toFixed(2)}</td>
    </tr>`).join("");
  $("#anTable").innerHTML = `
    <thead><tr><th>School</th><th>Class</th><th>Subject</th><th>Records</th><th>Distribution</th><th>Average mark</th><th>Peak</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="7" class="empty">No published exam data for this filter yet.</td></tr>'}</tbody>`;
}

/* ---------------- STATE: live attendance ---------------- */
async function renderStateAttendance() {
  const schools = await api("/api/v1/state/schools");
  $("#content").innerHTML = `
    <div class="toolbar">
      <div class="field">School
        <select id="laSchool"><option value="">All schools</option>${schools.schools.map((s) => `<option value="${s.id}">${esc(s.school_name)}</option>`).join("")}</select>
      </div>
      <button class="btn btn-primary" id="laRun">Load today</button>
    </div>
    <div class="panel"><h3>Live Attendance (today)</h3>
      <div style="overflow-x:auto"><table class="tbl" id="laTable"></table></div></div>`;
  $("#laRun").addEventListener("click", loadLiveAttendance);
  await loadLiveAttendance();
}

async function loadLiveAttendance() {
  const school = $("#laSchool")?.value;
  const data = await api(`/api/v1/state/attendance/live${school ? `?school_id=${school}` : ""}`);
  const badge = { Present: "ok", Absent: "alarm", Late: "warn", Excused: "info" };
  const rows = data.records.map((r) => `
    <tr><td>${esc(r.school_name)}</td><td>${esc(r.class)}</td><td class="mono">${esc(r.national_student_id)}</td>
    <td>${esc(r.student)}</td><td><span class="pill ${badge[r.status] ?? "dim"}">${esc(r.status).toUpperCase()}</span></td></tr>`).join("");
  $("#laTable").innerHTML = `
    <thead><tr><th>School</th><th>Class</th><th>National ID</th><th>Student</th><th>Status</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="5" class="empty">No attendance records today yet.</td></tr>'}</tbody>`;
}

/* ---------------- STATE: alarm feed / exam events ---------------- */
async function renderAlarms() {
  $("#content").innerHTML = `<div class="panel"><h3>Red Alarm Communication Gateway</h3>
    <p class="sub">Critical failure notifications queued by the 15:00 compliance worker</p>
    <table class="tbl" id="alarmTable"></table></div>`;
  await loadAlarmFeed();
}
async function loadAlarmFeed() {
  const data = await api("/api/v1/state/alarms");
  const rows = data.alarms.map((a) => `
    <tr><td style="white-space:nowrap">${fmtTime(a.timestamp_sent)}</td>
    <td>${esc(a.message)}</td>
    <td><span class="pill ${a.delivery_status === "Delivered" ? "ok" : "warn"}">${esc(a.delivery_status)}</span></td></tr>`).join("");
  $("#alarmTable").innerHTML = `<thead><tr><th>Sent</th><th>Message</th><th>Delivery</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="3" class="empty">No alarms on record — all schools compliant.</td></tr>'}</tbody>`;
}

async function renderExamEvents() {
  const data = await api("/api/v1/state/exam-events");
  const rows = data.events.map((e) => `
    <tr><td style="white-space:nowrap">${fmtTime(e.published_at)}</td><td>School #${e.school_id}</td>
    <td>Class #${e.class_id} · Subject #${e.subject_id}</td><td>${esc(e.exam_name)}</td>
    <td>${e.records_released}</td><td><span class="pill info">IMMUTABLE</span></td></tr>`).join("");
  $("#content").innerHTML = `<div class="panel"><h3>Exam Submission Events</h3>
    <p class="sub">Every "Publish Exam Marks to State" action — append-only, cannot be edited or deleted</p>
    <table class="tbl"><thead><tr><th>Published at</th><th>School</th><th>Scope</th><th>Exam</th><th>Records</th><th>Integrity</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="6" class="empty">No publications yet.</td></tr>'}</tbody></table></div>`;
}

/* ---------------- SCHOOL: overview ---------------- */
async function renderOverview() {
  const data = await api("/api/v1/school/overview");
  const d = data.daily_submission;
  const status = d.alarm_triggered
    ? '<span class="pill alarm">🚨 RED ALARM — audit breach</span>'
    : d.attendance_submitted
      ? `<span class="pill ok">✅ Submitted ${fmtTime(d.attendance_submitted_at)}</span>`
      : '<span class="pill warn">⚠️ Roster not submitted — deadline 12:00 PM</span>';
  $("#content").innerHTML = `
    <div class="stat-grid">
      <div class="stat-card"><div class="k">Academic year</div><div class="v" style="font-size:19px">${esc(data.academic_year?.label ?? "—")}</div></div>
      <div class="stat-card"><div class="k">Active students</div><div class="v">${data.counts.students}</div></div>
      <div class="stat-card"><div class="k">Classes</div><div class="v">${data.counts.classes}</div></div>
      <div class="stat-card"><div class="k">Subjects</div><div class="v">${data.counts.subjects}</div></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Today's compliance status — ${data.today}</h3>${status}</div>
      <p class="sub">State rule: daily attendance rosters must be submitted by 12:00 PM. The audit worker runs at 15:00 and raises a RED ALARM for missing rosters.</p>
      <button class="btn btn-success" id="submitRosterBtn">📤 Submit today's attendance roster</button>
      <p class="note" id="rosterNote"></p>
    </div>`;
  $("#submitRosterBtn").addEventListener("click", async () => {
    try {
      const r = await api("/api/v1/school/attendance/submit", { method: "POST", body: {} });
      toast("Roster submitted", r.message, r.submitted_after_deadline ? "warn" : "success");
      renderOverview();
    } catch (err) { toast("Cannot submit", err.message, "alarm"); }
  });
}

/* ---------------- SCHOOL: students ---------------- */
async function renderStudents() {
  const classes = await api("/api/v1/school/classes");
  API.classCache = classes.classes;
  const opts = classes.classes.map((c) => `<option value="${c.id}">${esc(c.class_label)} (${c.student_count})</option>`).join("");
  $("#content").innerHTML = `
    <div class="panel">
      <h3>Register new student</h3>
      <p class="sub">A unique immutable national tracking ID (STU-${new Date().getFullYear()}-XY123) is generated automatically.</p>
      <div class="form-grid">
        <div class="field">First name<input id="stFirst" /></div>
        <div class="field">Last name<input id="stLast" /></div>
        <div class="field">Class<select id="stClass">${opts}</select></div>
        <div class="field">Gender<select id="stGender"><option>Female</option><option>Male</option><option>Other</option></select></div>
        <div class="field">Date of birth<input type="date" id="stDob" /></div>
        <div class="field">Guardian name<input id="stGuardian" /></div>
        <div class="field">Relationship<select id="stRel"><option>Mother</option><option>Father</option><option>Uncle</option><option>Aunt</option><option>Grandmother</option><option>Grandfather</option></select></div>
        <div class="field">Guardian phone<input id="stPhone" placeholder="+252-63-…" /></div>
        <div class="field">Emergency phone<input id="stEmergency" placeholder="+252-63-…" /></div>
      </div>
      <button class="btn btn-primary" id="stCreate">🎓 Register student</button>
      <p class="note" id="stResult"></p>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Student registry <span class="count-badge" id="stCount"></span></h3>
        <div class="toolbar" style="margin:0">
          <select id="stFilterClass"><option value="">All classes</option>${opts}</select>
          <input id="stSearch" placeholder="Search name or STU-ID" />
          <button class="btn" id="stRefresh">Filter</button>
        </div>
      </div>
      <div style="overflow-x:auto"><table class="tbl" id="stTable"></table></div>
    </div>`;
  $("#stCreate").addEventListener("click", createStudent);
  $("#stRefresh").addEventListener("click", loadStudents);
  $("#stSearch").addEventListener("keydown", (e) => e.key === "Enter" && loadStudents());
  await loadStudents();
}

async function createStudent() {
  const body = {
    first_name: $("#stFirst").value, last_name: $("#stLast").value,
    current_class_id: +$("#stClass").value, gender: $("#stGender").value,
    date_of_birth: $("#stDob").value || null,
    guardian_name: $("#stGuardian").value || null, guardian_relationship: $("#stRel").value,
    guardian_phone: $("#stPhone").value || null, emergency_contact_phone: $("#stEmergency").value || null,
  };
  try {
    const r = await api("/api/v1/school/students", { method: "POST", body });
    $("#stResult").innerHTML = `✅ ${esc(r.message)} — <span class="mono-tag">${esc(r.national_student_id)}</span>`;
    toast("Student registered", `National ID ${r.national_student_id}`, "success");
    loadStudents();
  } catch (err) { $("#stResult").textContent = `⚠️ ${err.message}`; }
}

async function loadStudents() {
  const params = new URLSearchParams();
  if ($("#stFilterClass").value) params.set("class_id", $("#stFilterClass").value);
  if ($("#stSearch").value.trim()) params.set("q", $("#stSearch").value.trim());
  const data = await api(`/api/v1/school/students?${params}`);
  $("#stCount").textContent = `${data.students.length} shown`;
  const rows = data.students.map((s) => `
    <tr><td class="mono">${esc(s.national_student_id)}</td>
    <td><strong>${esc(s.first_name)} ${esc(s.last_name)}</strong><div class="note">${esc(s.guardian_name ?? "")} · ${esc(s.guardian_phone ?? "")}</div></td>
    <td>${esc(s.class_label ?? "—")}</td><td>${esc(s.gender ?? "—")}</td>
    <td>${s.is_active ? '<span class="pill ok">ACTIVE</span>' : '<span class="pill dim">INACTIVE</span>'}</td></tr>`).join("");
  $("#stTable").innerHTML = `<thead><tr><th>National ID</th><th>Student</th><th>Class</th><th>Gender</th><th>Status</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="5" class="empty">No students found.</td></tr>'}</tbody>`;
}

/* ---------------- SCHOOL: classes & subjects ---------------- */
async function renderClasses() {
  const classes = await api("/api/v1/school/classes");
  const subjects = await api("/api/v1/school/subjects");
  $("#content").innerHTML = `
    <div class="panel">
      <h3>Create class (Class 1 → Class 12)</h3>
      <div class="toolbar">
        <div class="field">Level<select id="clLevel">${Array.from({ length: 12 }, (_, i) => `<option>Class ${i + 1}</option>`).join("")}</select></div>
        <div class="field">Stream<input id="clStream" placeholder="A / Blue / Gold" value="A" /></div>
        <div class="field">Room<input id="clRoom" placeholder="R-7A" /></div>
        <button class="btn btn-primary" id="clCreate">Add class</button>
      </div>
      <div style="overflow-x:auto"><table class="tbl" id="clTable"></table></div>
    </div>
    <div class="panel">
      <h3>Subjects offered</h3>
      <div class="toolbar">
        <div class="field">Code<input id="suCode" placeholder="MATH-9" /></div>
        <div class="field">Name<input id="suName" placeholder="Mathematics" /></div>
        <div class="field">Level<select id="suLevel">${Array.from({ length: 12 }, (_, i) => `<option>Class ${i + 1}</option>`).join("")}</select></div>
        <button class="btn btn-primary" id="suCreate">Add subject</button>
      </div>
      <div style="overflow-x:auto"><table class="tbl" id="suTable"></table></div>
    </div>`;
  $("#clCreate").addEventListener("click", async () => {
    try {
      await api("/api/v1/school/classes", { method: "POST", body: { class_level: $("#clLevel").value, class_stream: $("#clStream").value, room_number: $("#clRoom").value || null } });
      toast("Class created", "", "success"); renderClasses();
    } catch (err) { toast("Failed", err.message, "alarm"); }
  });
  $("#suCreate").addEventListener("click", async () => {
    try {
      await api("/api/v1/school/subjects", { method: "POST", body: { subject_code: $("#suCode").value, subject_name: $("#suName").value, class_level: $("#suLevel").value } });
      toast("Subject created", "", "success"); renderClasses();
    } catch (err) { toast("Failed", err.message, "alarm"); }
  });
  $("#clTable").innerHTML = `<thead><tr><th>Class</th><th>Stream</th><th>Room</th><th>Students</th></tr></thead><tbody>${
    classes.classes.map((c) => `<tr><td><strong>${esc(c.class_level)}</strong></td><td>${esc(c.class_stream)}</td><td>${esc(c.room_number ?? "—")}</td><td>${c.student_count}</td></tr>`).join("")}</tbody>`;
  $("#suTable").innerHTML = `<thead><tr><th>Code</th><th>Subject</th><th>Level</th></tr></thead><tbody>${
    subjects.subjects.slice(0, 80).map((s) => `<tr><td class="mono">${esc(s.subject_code)}</td><td>${esc(s.subject_name)}</td><td>${esc(s.class_level)}</td></tr>`).join("")}</tbody>`;
}

/* ---------------- SCHOOL: attendance ---------------- */
async function renderAttendance() {
  const classes = await api("/api/v1/school/classes");
  API.classCache = classes.classes;
  $("#content").innerHTML = `
    <div class="panel">
      <h3>Daily attendance roster</h3>
      <p class="sub">Record statuses, then submit the sealed roster before 12:00 PM. The 15:00 audit flags missing submissions with a RED ALARM.</p>
      <div class="toolbar">
        <div class="field">Class<select id="attClass">${classes.classes.map((c) => `<option value="${c.id}">${esc(c.class_label)}</option>`).join("")}</select></div>
        <div class="field">Date<input type="date" id="attDate" value="${todayISO()}" /></div>
        <button class="btn btn-primary" id="attLoad">Load roster</button>
        <button class="btn" id="attAllPresent">Mark all present</button>
        <button class="btn btn-success" id="attSave">💾 Save entries</button>
        <button class="btn btn-success" id="attSubmit">📤 Submit roster</button>
      </div>
      <div class="roster-grid" id="attGrid"><div class="empty">Load a class to begin.</div></div>
    </div>`;
  $("#attLoad").addEventListener("click", loadRoster);
  $("#attAllPresent").addEventListener("click", () => {
    document.querySelectorAll("#attGrid select").forEach((s) => (s.value = "Present"));
  });
  $("#attSave").addEventListener("click", saveAttendance);
  $("#attSubmit").addEventListener("click", submitRoster);
  await loadRoster();
}

async function loadRoster() {
  const classId = +$("#attClass").value;
  const date = $("#attDate").value || todayISO();
  $("#attGrid").innerHTML = '<div class="empty">Loading…</div>';
  const [students, attendance] = await Promise.all([
    api(`/api/v1/school/students?class_id=${classId}`),
    api(`/api/v1/school/attendance?class_id=${classId}&date=${date}`),
  ]);
  if (!students.students.length) { $("#attGrid").innerHTML = '<div class="empty">No active students in this class.</div>'; return; }
  $("#attGrid").innerHTML = students.students.map((s) => `
    <div class="roster-row">
      <span class="who" title="${esc(s.national_student_id)}">${esc(s.first_name)} ${esc(s.last_name)}</span>
      <select data-student="${s.id}">
        ${["Present", "Absent", "Late", "Excused"].map((st) =>
          `<option ${attendance.statuses[s.id] === st ? "selected" : ""}>${st}</option>`).join("")}
      </select>
    </div>`).join("");
}

async function saveAttendance() {
  const entries = [...document.querySelectorAll("#attGrid select")].map((sel) => ({
    student_id: +sel.dataset.student, status: sel.value,
  }));
  if (!entries.length) return;
  try {
    const r = await api("/api/v1/school/attendance", {
      method: "POST",
      body: { date: $("#attDate").value || todayISO(), class_id: +$("#attClass").value, entries },
    });
    toast("Attendance saved", `${r.saved} entries for ${r.class_label}`, "success");
  } catch (err) { toast("Save failed", err.message, "alarm"); }
}

async function submitRoster() {
  await saveAttendance();
  try {
    const r = await api("/api/v1/school/attendance/submit", { method: "POST", body: { date: $("#attDate").value || todayISO() } });
    toast("Roster submitted", r.message, r.submitted_after_deadline ? "warn" : "success");
  } catch (err) { toast("Cannot submit", err.message, "alarm"); }
}

/* ---------------- SCHOOL: marks & publish valve ---------------- */
async function renderMarks() {
  const classes = await api("/api/v1/school/classes");
  const years = await api("/api/v1/school/academic-years");
  API.classCache = classes.classes; API.yearCache = years.academic_years;
  const year = years.academic_years.find((y) => y.is_current) ?? years.academic_years[0];
  $("#content").innerHTML = `
    <div class="panel">
      <h3>Continuous assessment marks</h3>
      <p class="sub">Drafts are 100% private. Nothing reaches the State until an administrator publishes the exam scope.</p>
      <div class="toolbar">
        <div class="field">Class<select id="grClass">${classes.classes.map((c) => `<option value="${c.id}" data-level="${esc(c.class_level)}">${esc(c.class_label)}</option>`).join("")}</select></div>
        <div class="field">Subject<select id="grSubject"></select></div>
        <div class="field">Exam name<input id="grExam" value="End of Term 1" /></div>
        <div class="field">Academic year<select id="grYear">${years.academic_years.map((y) => `<option value="${y.id}" ${y.id === year?.id ? "selected" : ""}>${esc(y.label)}</option>`).join("")}</select></div>
        <button class="btn btn-primary" id="grLoad">Load mark sheet</button>
        <button class="btn" id="grSave">💾 Save draft</button>
        ${API.user.role === "school_manager" ? '<button class="btn btn-danger" id="grPublish">📤 Publish Exam Marks to State</button>' : ""}
      </div>
      <div class="roster-grid" id="grGrid"><div class="empty">Load a mark sheet to begin.</div></div>
      <p class="note" id="grStatus"></p>
    </div>`;
  $("#grClass").addEventListener("change", loadSubjectOptions);
  $("#grLoad").addEventListener("click", loadMarkSheet);
  $("#grSave").addEventListener("click", saveMarks);
  const pub = $("#grPublish");
  if (pub) pub.addEventListener("click", publishMarks);
  await loadSubjectOptions();
  await loadMarkSheet();
}

async function loadSubjectOptions() {
  const level = $("#grClass").selectedOptions[0]?.dataset.level;
  if (!level) return;
  const data = await api(`/api/v1/school/subjects?class_level=${encodeURIComponent(level)}`);
  $("#grSubject").innerHTML = data.subjects.map((s) => `<option value="${s.id}">${esc(s.subject_name)}</option>`).join("");
}

async function loadMarkSheet() {
  if (!$("#grSubject").value) { $("#grGrid").innerHTML = '<div class="empty">No subject for this class level.</div>'; return; }
  const params = new URLSearchParams({
    class_id: $("#grClass").value, subject_id: $("#grSubject").value, exam_name: $("#grExam").value || "End of Term 1",
  });
  const [sheet, students] = await Promise.all([
    api(`/api/v1/school/grades?${params}`),
    api(`/api/v1/school/students?class_id=${$("#grClass").value}`),
  ]);
  const existing = Object.fromEntries(sheet.grades.map((g) => [g.student_id, g.numeric_score]));
  $("#grStatus").innerHTML = sheet.is_published
    ? `🔒 <strong>Published ${fmtTime(sheet.publish_event?.published_at)}</strong> — these marks are frozen (immutable release).`
    : "🟡 Private draft — hidden from the State Government portal.";
  if (!students.students.length) { $("#grGrid").innerHTML = '<div class="empty">No students in this class.</div>'; return; }
  $("#grGrid").innerHTML = students.students.map((s) => `
    <div class="roster-row">
      <span class="who">${esc(s.first_name)} ${esc(s.last_name)}</span>
      <input type="number" min="0" max="100" step="0.5" data-student="${s.id}" value="${existing[s.id] ?? ""}" placeholder="—" />
    </div>`).join("");
}

async function saveMarks() {
  const entries = [...document.querySelectorAll("#grGrid input")].filter((i) => i.value !== "").map((i) => ({
    student_id: +i.dataset.student, numeric_score: +i.value,
  }));
  if (!entries.length) { toast("Nothing to save", "Enter at least one score.", "warn"); return; }
  try {
    const r = await api("/api/v1/school/grades", {
      method: "POST",
      body: {
        class_id: +$("#grClass").value, subject_id: +$("#grSubject").value,
        academic_year_id: +$("#grYear").value, exam_name: $("#grExam").value || "End of Term 1", entries,
      },
    });
    toast("Draft saved", `${r.saved} marks · ${r.visibility}`, "success");
    loadMarkSheet();
  } catch (err) { toast("Save failed", err.message, "alarm"); }
}

async function publishMarks() {
  const examName = $("#grExam").value || "End of Term 1";
  if (!confirm(`Publish "${examName}" marks for this class + subject to the State?\n\nThis registers an IMMUTABLE exam_submission_event and cannot be undone.`)) return;
  try {
    const r = await api("/api/v1/school/grades/publish", {
      method: "POST",
      body: {
        class_id: +$("#grClass").value, subject_id: +$("#grSubject").value,
        academic_year_id: +$("#grYear").value, exam_name: examName,
      },
    });
    toast("Published to State", r.message, "success");
    loadMarkSheet();
  } catch (err) { toast("Publish failed", err.message, "alarm"); }
}

/* ---------------- SCHOOL: private billing ---------------- */
async function renderBilling() {
  $("#content").innerHTML = `
    <div class="firewall-note">🔒 PRIVATE TIER — base tuition rates, ledgers, outstanding balances and payment logs are firewalled from every State Government role at the API and database layers.</div>
    <div class="stat-grid" id="billStats"></div>
    <div class="panel">
      <h3>Tuition rates</h3>
      <div style="overflow-x:auto"><table class="tbl" id="rateTable"></table></div>
    </div>
    <div class="panel">
      <h3>Student ledger &amp; payments</h3>
      <div style="overflow-x:auto"><table class="tbl" id="invTable"></table></div>
    </div>
    <div class="panel">
      <h3>Student transaction profiles</h3>
      <p class="sub">Per-learner tuition metrics, collected revenue and last payment instrument</p>
      <div style="overflow-x:auto"><table class="tbl" id="profTable"></table></div>
    </div>
    <div class="panel">
      <h3>Record a payment</h3>
      <div class="toolbar">
        <div class="field">Invoice #<input type="number" id="payInv" style="width:110px" /></div>
        <div class="field">Amount<input type="number" id="payAmount" step="0.01" style="width:120px" /></div>
        <div class="field">Method<select id="payMethod"><option>Mobile_Money</option><option>Cash</option><option>Bank_Transfer</option><option>Card</option></select></div>
        <button class="btn btn-primary" id="payBtn">💰 Apply payment</button>
      </div>
    </div>`;
  $("#payBtn").addEventListener("click", applyPayment);
  await loadBilling();
}

async function loadBilling() {
  const [summary, rates, invoices, profiles] = await Promise.all([
    api("/api/v1/school/finance/summary"),
    api("/api/v1/school/finance/tuition-rates"),
    api("/api/v1/school/finance/invoices"),
    api("/api/v1/school/finance/student-profiles"),
  ]);
  $("#billStats").innerHTML = `
    <div class="stat-card"><div class="k">Total billed</div><div class="v">$${summary.total_billed.toLocaleString()}</div></div>
    <div class="stat-card green"><div class="k">Collected</div><div class="v">$${summary.total_collected.toLocaleString()}</div></div>
    <div class="stat-card amber"><div class="k">Outstanding</div><div class="v">$${summary.outstanding_balance.toLocaleString()}</div></div>
    <div class="stat-card red"><div class="k">Open invoices</div><div class="v">${summary.invoice_counts.outstanding + summary.invoice_counts.partially_paid}</div></div>`;
  $("#rateTable").innerHTML = `<thead><tr><th>Class level</th><th>Base tuition</th><th>Cycle</th></tr></thead><tbody>${
    rates.tuition_rates.map((r) => `<tr><td>${esc(r.class_level)}</td><td><strong>$${r.base_tuition_amount.toFixed(2)}</strong></td><td>${esc(r.billing_cycle)}</td></tr>`).join("")}</tbody>`;
  const badge = { Settled: "ok", Partially_Paid: "warn", Outstanding: "dim", Overdue: "alarm" };
  $("#invTable").innerHTML = `<thead><tr><th>#</th><th>Student</th><th>Description</th><th>Due</th><th>Paid</th><th>Balance</th><th>Status</th></tr></thead><tbody>${
    invoices.invoices.map((i) => `
      <tr><td class="mono">${i.id}</td><td>${esc(i.student ?? "—")}</td><td>${esc(i.description)}</td>
      <td>$${i.amount_due.toFixed(2)}</td><td>$${i.amount_paid.toFixed(2)}</td><td><strong>$${i.balance.toFixed(2)}</strong></td>
      <td><span class="pill ${badge[i.status] ?? "dim"}">${esc(i.status).replace("_", " ").toUpperCase()}</span></td></tr>`).join("")
    || '<tr><td colspan="7" class="empty">No invoices yet.</td></tr>'}</tbody>`;

  const profBadge = (b) => (b <= 0.001 ? "ok" : b > 100 ? "alarm" : "warn");
  $("#profTable").innerHTML = `<thead><tr><th>Student</th><th>National ID</th><th>Class</th><th>Invoices</th><th>Billed</th><th>Collected</th><th>Balance</th><th>Last payment</th></tr></thead><tbody>${
    profiles.student_profiles.map((p) => `
      <tr><td><strong>${esc(p.student)}</strong></td><td class="mono">${esc(p.national_student_id)}</td>
      <td>${esc(p.class_label ?? "—")}</td><td>${p.invoices}</td>
      <td>$${p.total_billed.toFixed(2)}</td><td>$${p.total_paid.toFixed(2)}</td>
      <td><span class="pill ${profBadge(p.balance)}">$${p.balance.toFixed(2)}</span></td>
      <td>${p.last_payment_at ? `${fmtTime(p.last_payment_at)} · ${esc(p.last_payment_method).replace("_", " ")}` : "—"}</td></tr>`).join("")
    || '<tr><td colspan="8" class="empty">No student profiles.</td></tr>'}</tbody>`;
}

async function applyPayment() {
  try {
    const r = await api(`/api/v1/school/finance/invoices/${+$("#payInv").value}/payments`, {
      method: "POST",
      body: { amount: +$("#payAmount").value, payment_method: $("#payMethod").value },
    });
    toast("Payment applied", `Invoice now ${r.invoice_status} · balance $${r.balance}`, "success");
    loadBilling();
  } catch (err) { toast("Payment failed", err.message, "alarm"); }
}

/* ---------------- boot ---------------- */
(async () => {
  try {
    const h = await api("/api/health");
    API.version = h.version;
    const hero = document.querySelector("#heroVersion");
    if (hero) hero.textContent = `v${h.version}`;
  } catch { /* offline — keep default version label */ }
})();

if (API.token && API.user) {
  enterApp();
} else {
  // A successful login always sets an HttpOnly cookie.  Recover from it when
  // persistent browser storage is unavailable instead of leaving mobile users
  // on the sign-in screen.
  api("/api/auth/me")
    .then((user) => {
      API.user = user;
      enterApp();
    })
    .catch(() => {
      $("#loginView").classList.remove("hidden");
    });
}
