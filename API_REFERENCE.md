# API Reference

Base URL: `/` — interactive OpenAPI docs at `/docs`.

All protected routes require `Authorization: Bearer <jwt>` from
`POST /api/auth/login`.

---

## Auth

| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/api/auth/login` | — | `{email, password}` → `{access_token, user}` |
| GET | `/api/auth/me` | any | Current identity + tenant binding |

## State portal (state_inspector only)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/state/compliance-map` | **View A** — command map + alarm summary for every active school |
| GET | `/api/v1/state/students/search?q=` | **View B** — statewide lookup by national ID (`STU-…`) or surname |
| GET | `/api/v1/state/analytics/grades?school_id=&class_level=` | **Query C** — subject benchmarking index; only scores carrying a matching token event in `exam_submission_events` |
| GET | `/api/v1/state/attendance/live?school_id=&date=` | Read-only live attendance feed |
| GET | `/api/v1/state/alarms` | Red_Alarm communication-gateway feed |
| GET | `/api/v1/state/exam-events` | Immutable publication ledger |
| GET | `/api/v1/state/schools` | Licensed schools + accreditation status |
| POST | `/api/v1/state/audit/run` | Fire the 15:00 Red Alarm worker immediately |

Financial data: **no route exists**, by design (see `SECURITY_AND_RLS.md`).

## Tenant ERP (`school_id` auto-scoped)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/api/v1/school/overview` | school | Counts + today's submission/alarm status |
| GET/POST | `/api/v1/school/classes` | mgr, tch | Class 1–12 + streams |
| GET/POST | `/api/v1/school/subjects` | mgr, tch | Subjects per class level |
| GET | `/api/v1/school/academic-years` | school | Year registry |
| GET/POST | `/api/v1/school/students` | school | Registry; registration auto-issues `STU-YYYY-XY123` |
| GET/POST | `/api/v1/school/attendance` | mgr, tch | Bulk upsert per-student daily statuses |
| POST | `/api/v1/school/attendance/submit` | mgr, tch | Seal today's roster (12:00 PM deadline) |
| GET/POST | `/api/v1/school/grades` | school | Private mark sheets (drafts) |
| POST | `/api/v1/school/grades/publish` | **school_manager** | 📤 Publish Exam Marks to State (immutable) |
| GET | `/api/v1/school/exam-events` | school | Own publication history |

## 🔒 Private finance group (`/api/v1/school/finance/` — school_manager only)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/school/finance/summary` | Billed / collected / outstanding revenue totals |
| GET/POST | `/api/v1/school/finance/tuition-rates` | Base tuition per class level |
| GET/POST | `/api/v1/school/finance/invoices` | Student ledger |
| POST | `/api/v1/school/finance/invoices/{id}/payments` | Record a payment transaction |
| GET | `/api/v1/school/finance/student-profiles` | Per-student transaction profiles (billed, collected, balance, last payment) |

State tokens receive `403 🚨 FIREWALL VIOLATION …` and the attempt is logged.

## Interface portals (STEP 4)

| Path | Workspace |
|---|---|
| `/admin/state` | State Admin Panel — alert map (green/red), global student/guardian search, Class 1–12 benchmarking |
| `/admin/school` | Private School ERP — attendance roster, exam manager + publish valve, class setup, private billing |

## Realtime

| Path | Description |
|---|---|
| `WS /ws?token=` | Live event bus: `red_alarm`, `attendance_submitted`, `attendance_recorded`, `exam_published`, `audit_completed` |

## Misc

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness + platform configuration |

### Example: trigger the Red Alarm demo

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"inspector@education.gov","password":"State@2026"}' | jq -r .access_token)

curl -s -X POST localhost:8000/api/v1/state/audit/run -H "Authorization: Bearer $TOKEN"
```
