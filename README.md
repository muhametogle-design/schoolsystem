# SchoolSystem

[![CI](https://github.com/muhametogle-design/schoolsystem/actions/badge.svg)](https://github.com/muhametogle-design/schoolsystem/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-4f8cff.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-38%20green-2ecc8f.svg)](tests)

**Private School Management & State Compliance Monitoring Software System** — a
centralized SaaS platform provided by a State Government for licensed private
schools (Class 1 → Class 12).

| Documentation | |
|---|---|
| [Deployment guide](DEPLOYMENT.md) | Production topology, TLS, backups, go-live checklist |
| [API reference](API_REFERENCE.md) | `/api/v1/*` route contract |
| [Security model](SECURITY_AND_RLS.md) | The financial firewall & RLS |
| [Database design](DATABASE_DESIGN.md) | Schema, constraints, analytics views |
| [Architecture](ARCHITECTURE.md) | Topology & data flows |
| [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [License](LICENSE) | Project hygiene |

The repo contains the full implementation of the three-phase technical
specification:

| Phase | Deliverable | Location |
|---|---|---|
| **1** | Monolithic PostgreSQL v14+ schema (tables, constraints, performance indexes) | `sql/001_schema.sql` |
| **1** | Tenant isolation RLS + 🔒 financial firewall + immutability triggers | `sql/002_security_firewall.sql` |
| **2** | 3:00 PM Red Alarm compliance worker + secure ID generator | `app/services/compliance.py`, `app/services/scheduler.py`, `app/services/student_id.py` |
| **3** | Interactive Query Analytics (Views A / B / C) | `sql/003_analytics_views.sql`, `app/services/analytics.py` |
| ✚ | FastAPI multi-tenant API + WebSocket alarm stream | `app/` |
| ✚ | Role-aware dashboard (State portal + tenant ERP) | `frontend/` |
| ✚ | Production hardening: login throttling, security headers, structured logging | `app/main.py`, `app/core/ratelimit.py` |
| ✚ | Test suite incl. firewall & release-valve proofs (38 tests) | `tests/` |
| ✚ | CI: pytest + PostgreSQL DDL grammar validation + image build | `ci/github-actions.yml` → copy to `.github/workflows/ci.yml` |

---

## 1. Quick start

### Zero-infra demo (SQLite demo tier)

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — the platform auto-creates its schema and seeds
demo data via the STEP 5 pipeline (3 schools × Class 1–12 tracks, ~300 students
with generated STU-IDs, 10 days of attendance history, published + draft exams,
billing ledgers). Portals: **/admin/state** (State Admin Panel) and
**/admin/school** (Private School ERP Portal).

### Production stack (real PostgreSQL 16)

```bash
docker compose up --build
```

The `db` container applies `sql/001_schema.sql`, `sql/002_security_firewall.sql`
and `sql/003_analytics_views.sql` automatically on first boot; the seeder then
loads the demo estate. API at http://localhost:8000, interactive docs at
`/docs`.

### Demo accounts

| Role | Email | Password | Sees |
|---|---|---|---|
| State Inspector | `inspector@education.gov` | `State@2026` | Command map, red alarms, student lookup, published analytics — **zero financial data** |
| School Manager (Greenfield) | `manager@greenfield.edu` | `School@2026` | Full ERP incl. private billing + the Publish valve |
| Teacher (Greenfield) | `teacher@greenfield.edu` | `Teach@2026` | Attendance + marks entry |
| School Manager (Horizon) | `manager@horizon.edu` | `School@2026` | Deliberately non-compliant tenant — triggers the RED ALARM |

---

## 2. The four operational workflow rules

1. **The Attendance Deadline** — schools must submit daily rosters by **12:00 PM**
   (`POST /api/v1/school/attendance/submit` writes `daily_submission_logs`).
2. **The 3-Hour Red Alarm Engine** — at exactly **15:00** the worker cron
   (`app/services/scheduler.py` → `process_daily_attendance_deadlines`) scans
   today's submissions, UPSERTs `alarm_triggered = true` for every failing
   active school, queues a `Red_Alarm` record in the communication gateway and
   streams a live banner to every state-inspector browser over **WebSockets**
   (`/ws`). It can also be fired manually from the State dashboard.
3. **The Exam Data Release Valve** — `student_grades.is_published` defaults to
   `FALSE`; drafts are invisible to every State query. Hitting **Publish Exam
   Marks to State** (`POST /api/v1/school/grades/publish`, managers only) flips the
   scope to published **and** appends an immutable
   `exam_submission_events` row. Publication is irreversible (DB trigger +
   API guard).
4. **Auto-Generated Student Tracking ID** — every registration is issued a
   unique, immutable `STU-2026-XY123` code with a collision-checked secure RNG
   (`generate_unique_national_student_id`).

---

## 3. The Critical Firewall Rule 🔒

> Under no circumstances can a State Government user access, query, or view any
> school's private financial data — base tuition rates, billing configurations,
> student ledgers, outstanding balances, or transaction payment logs.

Enforced in three independent layers:

1. **API layer** — no state route can express financial data; `require_school()`
   rejects state tokens on every tenant route with 403 **and writes the blocked
   attempt to `security_audit_log`**.
2. **Database layer** — `sql/002_security_firewall.sql` grants `state_readonly`
   SELECT on academic tables *only*, and installs explicit **DENY-ALL RLS
   policies** on `tuition_rates`, `student_invoices`, `payment_transactions`
   that evaluate FALSE for state roles even if a grant were added later.
3. **Test layer** — `tests/test_firewall.py` proves every financial route
   returns 403 for state tokens and that violations are audited.

## 4. Tenant isolation

All tenant tables carry `school_id`; every ERP query is forcibly scoped by the
authenticated user's `school_id` (cross-tenant ids resolve to 404). On
PostgreSQL this is doubled by row-level security using per-request session
variables (`app.school_id`, `app.role`).

## 5. Layout

```
sql/        Phase 1 DDL + firewall + analytics views (PostgreSQL 14+)
app/
  api/      auth, state portal, school ERP, billing (private), /ws stream
  core/     config, db, security (Argon2 + JWT), WebSocket bus
  models/   SQLAlchemy ORM (mirrors the DDL)
  schemas/  Pydantic contracts
  services/ Phase 2 worker + scheduler, ID generator, publish valve, Views A/B/C
frontend/   Role-aware dashboard (vanilla JS + WebSockets)
scripts/    Demo seeder
tests/      pytest suite (30 tests)
```

## 6. Commands

```bash
make dev      # run locally (SQLite demo tier)
make test     # pytest suite
make seed     # seed demo data only
make docker   # full PostgreSQL stack
make psql     # psql into the compose database
```

## 7. Notes

* The analytics services mirror `sql/003_analytics_views.sql` in portable
  SQLAlchemy so the same API runs unchanged on PostgreSQL (production) and
  SQLite (demo/tests).
* All timestamps are stored naive-UTC; the compliance cron operates in
  `PLATFORM_TIMEZONE` (default `Africa/Nairobi`).
