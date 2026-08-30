# Security Model and Financial Firewall

## Security boundary

The system deliberately separates two views of the same education network:

- **State Admin / Inspector:** cross-school academic oversight, class rosters,
  teacher assignments, attendance, and *published* results.
- **School Manager / Teacher:** one school's operational workspace.
- **Finance:** a manager-only, tenant-private tier. State-facing routes do not
  import a finance model or serialize tuition, invoices, payments, balances, or
  billing contact fields.

`state_admin` may create/manage school tenants and roll sequence settings.
`inspector` and legacy `state_inspector` are read-only. A state role is always
rejected from every `/api/v1/school/*` endpoint, including non-financial tenant
routes, rather than being silently assigned to a school.

## Firewall layers

### 1. API guards

`app/api/deps.py` validates the signed JWT against the current `users` row on
each request, rejects inactive or role/tenant-stale sessions, and scopes school
requests to `user.school_id`.

- `require_state` permits only State Admin/Inspector academic routes.
- `require_state_admin` gates school provisioning and roll-sequence changes.
- `require_school` rejects state roles before a tenant query can execute.
- `school_manager` is required for billing and staff/curriculum administration.
- A rejected boundary attempt is appended to `security_audit_log` without
  leaking protected records in the response.

### 2. PostgreSQL RLS and grants

[`sql/002_security_firewall.sql`](sql/002_security_firewall.sql) enables and
**forces** RLS for every tenant academic and financial table. The force clause
matters: ordinary PostgreSQL table owners otherwise bypass RLS.

The API resets pooled connection context to deny-by-default, then derives
`app.school_id` and `app.role` from a verified JWT. PostgreSQL policies apply
these settings to every tenant table. The authenticated user record is checked
against its claims before an endpoint can query application data.

`students.fee_status` is treated as billing data as well: the State API never
serializes it and the `state_readonly` grant deliberately omits that column.

Financial policies are explicit deny-all for state roles:

```
USING (school_id = app_current_school_id() AND NOT app_is_state_role())
```

`state_readonly` receives only selected academic columns. It receives no grant
on `tuition_rates`, `student_invoices`, or `payment_transactions`; the RLS
financial denial remains a second protection if a future grant is made by
mistake. `school_app` can append audit entries but cannot browse the global
audit log.

> **Deployment requirement:** Never run the web application as a PostgreSQL
> superuser or a role with `BYPASSRLS`, because PostgreSQL itself permits those
> roles to ignore RLS. Apply `001_schema.sql`, seed, then apply
> `002_security_firewall.sql` as described in the README.

### 3. Regression tests

The test suite covers state-finance denial, teacher billing denial, cross-tenant
registry denial, Inspector mutation denial, State Admin provisioning,
sequential rolls, complete class curriculum assignment, and cookie/token
session behavior.

## Immutability and release controls

| Protected asset | Enforcement |
|---|---|
| School code after rolls exist | State Admin API returns `409`; issued roll prefix cannot be changed |
| Student `national_student_id` / `roll_number` | PostgreSQL trigger blocks rewrites |
| Roll allocation | Per-school `school_roll_sequences` row advances transactionally; no count-derived reuse |
| Exam publication event | Trigger blocks `UPDATE` and `DELETE` (append-only ledger) |
| Published marks | Trigger blocks a published record being returned to draft |
| Draft marks | State RLS only permits `is_published = TRUE` records |

## Authentication and live updates

- Password hashes use Argon2id.
- Signed HS256 JWTs expire after the configured session period (eight hours by
  default); set a unique `JWT_SECRET_KEY` in every real deployment.
- Login sets an HttpOnly same-origin cookie in addition to returning the bearer
  token. This permits phones or embedded browser contexts without localStorage
to restore sessions after a reload.
- `WS /ws` accepts the bearer query token or same-origin cookie and performs
the same active-account/claim check as HTTP before it joins the live event bus.
- Set `COOKIE_SECURE=true` and explicit `CORS_ORIGINS_RAW` values behind HTTPS
  in a real deployment. Use `COOKIE_SAMESITE=none` only for a necessary
  cross-site embed, which also requires Secure cookies.

## Seed credentials

Credentials exist only to make a new local estate testable. Rotate or replace
them before staff receive access.

| Role | Login |
|---|---|
| State Admin | `stateadmin@education.gov` / `StateAdmin@2026` |
| Inspector | `inspector@education.gov` / `State@2026` |
| School Manager | `manager@<seed-domain>` / `School@2026` |
| Teacher | `teacher@<seed-domain>` / `Teach@2026` |
