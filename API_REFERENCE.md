# NE-EMIS API Reference

Base URL: `http://localhost:8000`
All endpoints except `/auth/login` require `Authorization: Bearer <jwt>` with
a role and (for campus tenants) a `campus_id`.

## Phase 1 — Ingestion

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/auth/login` | none | Obtain JWT |
| `GET` | `/auth/me` | any | Token introspection |
| `POST` | `/ingestion/validate` | clerk/dean | Real-time format validation only |
| `POST` | `/ingestion` | clerk/dean | Validate + persist a batch |
| `POST` | `/ingestion/attendance` | clerk/dean | Store single attendance row |
| `POST` | `/ingestion/grades` | clerk/dean | Upsert exam/grade row |

## Phase 2 — Audit & Lock

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/locks` | dean | Sign + freeze a record (Ed25519) |
| `GET` | `/locks` | dean | List campus locks |
| `POST` | `/locks/{lock_id}/unlock` | state_admin/system | State counter-signature unlock |

## Phase 2/3 — Student & Teacher Data

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/students` | clerk/dean | Register student (NE-SID generated) |
| `GET` | `/students` | clerk/dean | List campus students |
| `GET` | `/students/{id}` | clerk/dean | Get student |
| `GET` | `/students/{id}/mobility` | clerk/dean | Browsing history tree |
| `POST` | `/students/{id}/mobility` | dean/state | Record transfer/clearance wish |
| `POST` | `/teachers` | clerk/dean | Register teacher (NE-TID generated) |
| `GET` | `/teachers` | clerk/dean | List campus teachers |
| `POST` | `/teachers/{id}/certifications` | clerk/dean | Add certification |
| `POST` | `/teachers/{id}/payroll-profile` | clerk/dean | Link to Civil Service tier |
| `GET` | `/teachers/{id}/background-log` | clerk/dean | Background audit log |
| `POST` | `/teachers/{id}/exit` | dean | Exit/transfer record |
| `POST` | `/teachers/payroll` | clerk/dean | Submit payroll hours |

## Phase 3 — Aggregation

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/aggregation/run` | system/aggregator | Run overnight batch |
| `GET` | `/aggregation/batches` | system/state | Batch audit list |
| `GET` | `/aggregation/student-registry` | system/state | Central student registry |
| `GET` | `/aggregation/teacher-registry` | system/state | Central teacher registry |

## Phase 4 — State Control

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/state/kpis` | state_admin/system | Regional KPI rollup |
| `POST` | `/state/vacancies` | state_admin/system | Staffing vacancy tracker |
| `POST` | `/state/payouts/payroll` | state_admin/system | Generate payroll funding payouts |
| `POST` | `/state/payouts/capitation` | state_admin/system | Generate capitation payouts |
| `POST` | `/state/payouts/{id}/approve` | state_admin/system | Approve payout |
| `POST` | `/state/payouts/{id}/settle` | state_admin/system | Settle paid payout |
| `GET` | `/state/payroll-tiers` | state_admin/system | Civil Service grade tiers |

## Example: Locking a payroll record

```jsonc
POST /locks
{
  "entity_type": "payroll_entry",
  "entity_id": "50f7f2b4-...",
  "payload": {"teacher_id": "c4...", "pay_period": "2026-08", "net": 50000},
  "signature": "<base64 Ed25519 signature>",
  "signature_scheme": "ed25519",
  "key_version": 1
}
```

The signature is over `canonical(LockEnvelope{entity_type, entity_id,
campus_id, payload_hash, signature_scheme, key_version, locked_by, locked_at})`
where `payload_hash = SHA256(canonical(pruned_payload))`.
