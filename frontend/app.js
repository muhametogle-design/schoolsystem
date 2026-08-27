/* NE-EMIS dashboard client — self-contained demo UI. */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const NGN = (n) =>
  "₦" + Number(n).toLocaleString("en-NG", { maximumFractionDigits: 0 });

const state = {
  overview: null,
  students: [],
  teachers: [],
  attendance: [],
  locks: [],
  batches: [],
  funding: [],
  payroll: [],
  campuses: [],
};

const TABS = {
  overview: ["Education Oversight Dashboard", "Overview"],
  students: ["Student Registry & Mobility Matrix", "Student Registry"],
  teachers: ["Teacher & Payroll Governance", "Teacher Governance"],
  attendance: ["Attendance & Grade Ingestion", "Attendance & Grades"],
  locks: ["Cryptographic Record Locking", "Audit & Lock"],
  aggregation: ["Overnight Aggregation Pipeline", "Aggregation"],
  funding: ["State Funding, Payroll & Payouts", "Funding & Payroll"],
};

function fmtMoney(n) {
  return "₦" + Number(n).toLocaleString("en-NG");
}

function statusPill(status) {
  const cls = (status || "").toLowerCase().replace(/\s+/g, "-");
  return `<span class="status-pill s-${cls}">${status}</span>`;
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

async function loadAll() {
  const [
    overview, students, teachers, attendance, locks, batches, funding, payroll, campuses,
  ] = await Promise.all([
    api("/api/demo/overview"),
    api("/api/demo/students"),
    api("/api/demo/teachers"),
    api("/api/demo/attendance"),
    api("/api/demo/locks"),
    api("/api/demo/batches"),
    api("/api/demo/funding"),
    api("/api/demo/payroll"),
    api("/api/demo/campuses"),
  ]);
  Object.assign(state, { overview, students, teachers, attendance, locks, batches, funding, payroll, campuses });
  render();
}

/* ---------------- renderers ---------------- */

function render() {
  renderKpis();
  renderAttendanceChart();
  renderCampusBars();
  renderPipeline();
  renderRecentLocks();
  renderStudents();
  renderTeachers();
  renderAttendance();
  renderLocks();
  renderBatches();
  renderFunding();
  renderPayroll();
  $("#last-run").textContent = state.overview.last_aggregation
    ? state.overview.last_aggregation.slice(0, 16).replace("T", " ")
    : "—";
}

function renderKpis() {
  const o = state.overview;
  $("#kpi-students").textContent = o.students_total.toLocaleString();
  $("#kpi-students-foot").innerHTML = `<span class="trend-up">▲ ${o.new_students_this_term} new this term</span>`;
  $("#kpi-teachers").textContent = o.teachers_total.toLocaleString();
  $("#kpi-teachers-foot").textContent = `${o.teachers_active} active · ${o.teachers_total - o.teachers_active} leave/vacant`;
  $("#kpi-attendance").textContent = o.attendance_rate_pct.toFixed(1) + "%";
  $("#kpi-attendance-foot").textContent = `${o.chronic_truancy} chronic truants`;
  $("#kpi-vacancies").textContent = o.open_vacancies;
  $("#kpi-vacancies-foot").textContent = "needs reallocation";
  $("#kpi-locks").textContent = o.record_locks;
  $("#kpi-locks-foot").textContent = `${state.locks.filter(l => l.status === "Locked").length} frozen payloads`;
  $("#kpi-funding").textContent = fmtMoney(o.funding_released);
  $("#kpi-funding-foot").textContent = `${fmtMoney(o.funding_pending)} pending`;
}

function renderAttendanceChart() {
  const rows = state.attendance;
  const max = Math.max(...rows.map(r => r.present + r.truant));
  $("#attendance-chart").innerHTML = `
    <div class="bars">
      ${rows.map(r => {
        const pct = ((r.present + r.late + r.truant) / max) * 100;
        return `<div class="bar-group">
          <div class="bar" style="height:${Math.max(18, pct)}%"><small>${r.present + r.late + r.truant}</small></div>
          <div class="bar-label">${r.date.slice(5)}</div>
        </div>`;
      }).join("")}
    </div>`;
}

function renderCampusBars() {
  const byCode = Object.fromEntries(state.campuses.map(c => [c.code, c]));
  const totals = state.campuses.map(c => {
    const students = state.students.filter(s => s.campus === c.code).length;
    return { code: c.code, name: c.name, students };
  });
  const max = Math.max(...totals.map(t => t.students), 1);
  $("#campus-bars").innerHTML = totals.map(t => `
    <div class="campus-row">
      <span><strong>${t.code}</strong><br><small>${byCode[t.code]?.region || ""}</small></span>
      <div class="campus-track"><div class="campus-fill" style="width:${(t.students / max) * 100}%"></div></div>
      <span>${t.students} shown</span>
    </div>`).join("");
}

function renderPipeline() {
  // sections already static; update last aggregation
  const last = $("#last-run");
  if (last) last.textContent = state.overview.last_aggregation ? state.overview.last_aggregation.slice(0, 16).replace("T", " ") : "—";
}

function renderRecentLocks() {
  const recent = state.locks.slice(0, 3);
  $("#recent-locks").innerHTML = recent.map(l => `
    <div class="recent-item">
      <div><b>${l.entity.replace(/_/g, " ")}</b><span>${l.campus} · ${l.period}</span></div>
      ${statusPill(l.status)}
    </div>`).join("");
}

function renderStudents() {
  $("#student-count").textContent = `${state.students.length} demo records`;
  $("#students-body").innerHTML = state.students.map(s => `
    <tr>
      <td class="mono">${s.ne_sid}</td>
      <td><strong>${s.name}</strong></td>
      <td>${s.gender}</td>
      <td>${s.grade}</td>
      <td>${s.campus}</td>
      <td>${s.gpa.toFixed(2)}</td>
      <td>${s.attendance_pct.toFixed(1)}%</td>
      <td>${s.truancy > 4 ? `<span class="status-pill s-chronic">${s.truancy}</span>` : s.truancy}</td>
      <td>${statusPill(s.status)}</td>
    </tr>`).join("");
}

function renderTeachers() {
  $("#teacher-count").textContent = `${state.teachers.length} demo records`;
  $("#teachers-body").innerHTML = state.teachers.map(t => `
    <tr>
      <td class="mono">${t.ne_tid}</td>
      <td><strong>${t.name}</strong></td>
      <td>${t.campus}</td>
      <td>${t.subject}</td>
      <td>GL-${t.tier}</td>
      <td>${t.weekly_hours}</td>
      <td>${t.police_clearance === "Valid" || t.police_clearance === "Pending Renewal" ? `<span class="status-pill s-valid">${t.police_clearance}</span>` : `<span class="status-pill s-expired">${t.police_clearance}</span>`}</td>
      <td>${t.certification}</td>
      <td>${statusPill(t.status)}</td>
    </tr>`).join("");
}

function renderAttendance() {
  $("#attendance-body").innerHTML = state.attendance.map(r => {
    const total = r.present + r.absent + r.late + r.truant;
    const rate = ((r.present + r.late) / total * 100).toFixed(1);
    return `<tr>
      <td>${r.date}</td><td>${r.present}</td><td>${r.absent}</td><td>${r.late}</td>
      <td>${r.truant}</td><td><strong>${rate}%</strong></td>
    </tr>`;
  }).join("");
}

function renderLocks() {
  $("#locks-body").innerHTML = state.locks.map(l => `
    <tr>
      <td><strong>${l.entity.replace(/_/g, " ")}</strong></td>
      <td>${l.campus}</td>
      <td>${l.period}</td>
      <td class="mono">${l.hash}</td>
      <td>${l.dean}</td>
      <td>${new Date(l.locked_at).toLocaleString()}</td>
      <td>${statusPill(l.status)}</td>
      <td>${l.status !== "Locked" ? `<button class="btn btn-sm btn-approve" data-lock="${l.id}">Lock</button>` : `<span class="badge badge-green">Frozen</span>`}</td>
    </tr>`).join("");
  $$("[data-lock]").forEach(b => b.addEventListener("click", () => lockAction(b.dataset.lock)));
}

function renderBatches() {
  $("#batches-body").innerHTML = state.batches.map(b => `
    <tr>
      <td class="mono">${b.id}</td><td>${b.batch_date}</td><td>${b.phase}</td>
      <td>${statusPill(b.state)}</td>
      <td>${b.stats?.students_upserted ?? 0}</td>
      <td>${b.stats?.teachers_upserted ?? 0}</td>
      <td>${b.finished_at ? new Date(b.finished_at).toLocaleString() : "—"}</td>
    </tr>`).join("");
}

function renderFunding() {
  $("#funding-body").innerHTML = state.funding.map(f => `
    <tr>
      <td>${f.campus}</td><td>${f.period}</td><td>${f.kind.replace(/_/g, " ")}</td>
      <td><strong>${NGN(f.amount)}</strong></td><td>${statusPill(f.status)}</td><td>${f.ref}</td>
      <td>
        ${f.status === "Pending" ? `<button class="btn btn-sm btn-approve" data-approve="${f.id}">Approve</button>` : ""}
        ${f.status === "Approved" ? `<button class="btn btn-sm btn-settle" data-settle="${f.id}">Settle</button>` : ""}
      </td>
    </tr>`).join("");
  $$("[data-approve]").forEach(b => b.addEventListener("click", () => fundApprove(b.dataset.approve, b)));
  $$("[data-settle]").forEach(b => b.addEventListener("click", () => fundSettle(b.dataset.settle)));
}

function renderPayroll() {
  $("#payroll-body").innerHTML = state.payroll.map(p => `
    <tr>
      <td><strong>${p.name}</strong><br><span class="mono">${p.ne_tid}</span></td>
      <td>${p.campus}</td><td>GL-${p.tier}</td><td>${p.hours}</td>
      <td>${NGN(p.gross)}</td><td>${NGN(p.net)}</td><td>${statusPill(p.status)}</td>
    </tr>`).join("");
}

/* ---------------- actions ---------------- */

async function runAggregation() {
  toast("Running overnight aggregation…");
  try {
    const res = await api("/api/demo/aggregation/run", { method: "POST", body: JSON.stringify({}) });
    toast(`Aggregation complete · ${res.batch_id}`);
    await loadAll();
  } catch (e) {
    toast("Aggregation failed: " + e.message);
  }
}

async function ingestSample() {
  const box = $("#ingest-result");
  box.textContent = "Validating 131 rows…";
  try {
    const res = await api("/api/demo/ingest", { method: "POST" });
    box.classList.add("ok");
    box.textContent = `Accepted ${res.accepted} · Rejected ${res.rejected} · ${res.message}`;
    toast("Phase-1 ingestion accepted");
    await loadAll();
  } catch (e) {
    box.textContent = "Failed: " + e.message;
  }
}

async function lockAction(id) {
  try {
    await api(`/api/demo/locks/${id}/lock`, { method: "POST", body: JSON.stringify({ entity_type: "demo" }) });
    toast("Dean signature accepted — record frozen.");
    await loadAll();
  } catch (e) {
    toast(e.message);
  }
}

async function fundApprove(id, btn) {
  try {
    await api(`/api/demo/funding/${id}/approve`, { method: "POST" });
    toast("Funding approved.");
    await loadAll();
  } catch (e) {
    toast(e.message);
  }
}

async function fundSettle(id) {
  try {
    await api(`/api/demo/funding/${id}/settle`, { method: "POST" });
    toast("Payout settled to ledger.");
    await loadAll();
  } catch (e) {
    toast(e.message);
  }
}

/* ---------------- nav ---------------- */

function showTab(name) {
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach(t => t.classList.toggle("active", t.id === `tab-${name}`));
  const [title, crumb] = TABS[name] || [name, name];
  $("#page-title").textContent = title;
  $("#crumb-current").textContent = crumb;
}

function wire() {
  $$(".nav-item").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $$("[data-goto]").forEach(b => b.addEventListener("click", () => showTab(b.dataset.goto)));
  $("#run-aggregation").addEventListener("click", runAggregation);
  $("#ingest-btn").addEventListener("click", ingestSample);
  $("#year").addEventListener("change", () => toast("Year view updated (demo)"));
}

wire();
loadAll().then(() => {
  showTab("overview");
}).catch((e) => {
  document.body.insertAdjacentHTML("beforeend", `<pre style="padding:20px;color:#b13a3a">${e.message}</pre>`);
});
