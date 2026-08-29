# Security Model & The Financial Firewall

## Threat model

The State Government super-admin must have **absolute read-only visibility into
academics** (student profiles, national IDs, guardian contacts, live
attendance, *published* exam marks) while having **zero access to tenant
financial data**. Tenants must be isolated from each other. Publication events
and student IDs must be immutable.

## The Critical Firewall Rule — three independent layers

### Layer 1 — API routing (`app/api/deps.py`)

* No `/api/state/*` route imports, serializes or queries any financial model —
  the code path does not exist.
* Every `/api/school/*` route is wrapped by `require_school(...)`: a
  `state_inspector` token receives **403 FIREWALL VIOLATION** and the attempt
  is appended to `security_audit_log` (user, role, endpoint, verdict).
* Billing routes additionally require `school_manager`.

### Layer 2 — PostgreSQL (`sql/002_security_firewall.sql`)

```sql
-- The state's dedicated role gets academics only:
GRANT SELECT ON students, live_attendance, daily_submission_logs, … TO state_readonly;
-- tuition_rates, student_invoices, payment_transactions: deliberately NO grant.

-- And even if a grant appeared, DENY-ALL row policies stop the read:
CREATE POLICY financial_firewall ON student_invoices
    USING (school_id = app_current_school_id() AND NOT app_is_state_role());
```

Because RLS has no permissive bypass for `state_readonly`, a state session
cannot even count the rows.

### Layer 3 — tests (`tests/test_firewall.py`)

Proves every financial endpoint answers 403 for state tokens, that teachers are
locked out of billing, that school roles cannot reach the state portal, and
that tenant registries never leak across schools.

## Tenant isolation

* JWT carries `school_id` (NULL ⇒ state). Handlers inject it into every query.
* PostgreSQL RLS policies (`tenant_isolation`) scope all tenant tables via
  per-request session variables:
  `SELECT set_config('app.school_id', :school_id, true)`.
* `student_grades` RLS exposes only `is_published = TRUE` rows to state roles —
  the release valve enforced inside the database itself.

## Immutability

| Asset | Guard |
|---|---|
| `students.national_student_id` | trigger blocks rewrite |
| `exam_submission_events` | trigger blocks UPDATE/DELETE (append-only ledger) |
| Published grades | trigger blocks recall to draft; API returns 409 on re-publish |

## Authentication & sessions

* Argon2id password hashing (`argon2-cffi`).
* HS256 JWTs (rotate `JWT_SECRET_KEY`; 8h default expiry).
* WebSocket `/ws?token=` authenticates the same JWT, closing with 4401 on
  invalid credentials.
* All firewall decisions are auditable in `security_audit_log`.

## Demo credentials

Seeded for evaluation only — rotate before any real deployment:

| Role | Login |
|---|---|
| State inspector | `inspector@education.gov` / `State@2026` |
| School manager | `manager@<school-domain>` / `School@2026` |
| Teacher | `teacher@<school-domain>` / `Teach@2026` |
