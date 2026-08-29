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
| GET | `/api/state/compliance-map` | **View A** — command map + alarm summary for every active school |
| GET | `/api/state/students/search?q=` | **View B** — statewide lookup by national ID (`STU-…`) or surname |
| GET | `/api/state/analytics/grades?school_id=&class_level=` | **View C** — published-only grade benchmarking |
| GET | `/api/state/attendance/live?school_id=&date=` | Read-only live attendance feed |
| GET | `/api/state/alarms` | Red_Alarm communication-gateway feed |
| GET | `/api/state/exam-events` | Immutable publication ledger |
| GET | `/api/state/schools` | Licensed schools + accreditation status |
| POST | `/api/state/audit/run` | Fire the 15:00 Red Alarm worker immediately |

Financial data: **no route exists**, by design (see `SECURITY_AND_RLS.md`).

## Tenant ERP (`school_id` auto-scoped)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/api/school/overview` | school | Counts + today's submission/alarm status |
| GET/POST | `/api/school/classes` | mgr, tch | Class 1–12 + streams |
| GET/POST | `/api/school/subjects` | mgr, tch | Subjects per class level |
| GET | `/api/school/academic-years` | school | Year registry |
| GET/POST | `/api/school/students` | school | Registry; registration auto-issues `STU-YYYY-XY123` |
| GET/POST | `/api/school/attendance` | mgr, tch | Bulk upsert per-student daily statuses |
| POST | `/api/school/attendance/submit` | mgr, tch | Seal today's roster (12:00 PM deadline) |
| GET/POST | `/api/school/grades` | school | Private mark sheets (drafts) |
| POST | `/api/school/grades/publish` | **school_manager** | 📤 Publish Exam Marks to State (immutable) |
| GET | `/api/school/exam-events` | school | Own publication history |

## 🔒 Private billing (school_manager only — firewalled)

| Method | Path | Description |
|---|---|---|
| GET | `/api/school/billing/summary` | Billed / collected / outstanding totals |
| GET/POST | `/api/school/billing/tuition-rates` | Base tuition per class level |
| GET/POST | `/api/school/billing/invoices` | Student ledger |
| POST | `/api/school/billing/invoices/{id}/payments` | Record a payment transaction |

State tokens receive `403 🚨 FIREWALL VIOLATION …` and the attempt is logged.

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

curl -s -X POST localhost:8000/api/state/audit/run -H "Authorization: Bearer $TOKEN"
```
