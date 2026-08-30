# API Reference

Base URL: `/`. Interactive OpenAPI documentation is available at `/docs`.
Protected routes accept `Authorization: Bearer <jwt>` or the same-origin
HttpOnly session cookie returned by `POST /api/auth/login`.

## Authentication

| Method | Path | Access | Result |
|---|---|---|---|
| `POST` | `/api/auth/login` | Public | `{ email, password }` → token plus role/school identity; also sets a secure same-origin cookie when applicable |
| `POST` | `/api/auth/logout` | Any signed-in user | Clears the session cookie |
| `GET` | `/api/auth/me` | Any signed-in user | Current identity and tenant binding |

## State academic oversight

All routes below are available to **State Admin**, **Inspector**, and the
legacy `state_inspector` migration role unless stated otherwise. They return
academic visibility only—never tuition, invoices, payments, balances, or
billing contacts.

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/state/compliance-map` | State roles | Live school attendance/compliance overview |
| `GET` | `/api/v1/state/students/search?q=` | State roles | Search students by roll number, legacy identifier, or name |
| `GET` | `/api/v1/state/analytics/grades` | State roles | Published academic analytics only |
| `GET` | `/api/v1/state/attendance/live` | State roles | Cross-school attendance feed |
| `GET` | `/api/v1/state/alarms` | State roles | Red-alarm feed |
| `GET` | `/api/v1/state/exam-events` | State roles | Immutable exam-release ledger |
| `GET` | `/api/v1/state/schools` | State roles | Academic school directory |
| `GET` | `/api/v1/state/institutions` | State roles | Institution directory with academic counts |
| `GET` | `/api/v1/state/institutions/{school_id}` | State roles | School public identity, faculty roster, and academic summary |
| `GET` | `/api/v1/state/institutions/{school_id}/classes` | State roles | Class 1–12 streams and enrolment counts |
| `GET` | `/api/v1/state/institutions/{school_id}/classes/{class_id}/breakdown` | State roles | Roster with rolls, ten subjects, and assigned teacher links |
| `GET` | `/api/v1/state/teachers/{teacher_id}` | State roles | Full academic teacher profile and class/subject assignments |
| `GET` | `/api/v1/state/students/lookup?ne_sid=` | State roles | One cross-school student profile with published marks only |
| `GET` | `/api/v1/state/school-code-suggestion?school_name=` | State Admin | Available unique two-letter code suggestion |
| `POST` | `/api/v1/state/schools` | State Admin | Create a fully provisioned Class 1–12 school tenant |
| `PATCH` | `/api/v1/state/schools/{school_id}` | State Admin | Change public school identity/configuration only; billing fields are rejected |
| `GET/PATCH` | `/api/v1/state/schools/{school_id}/roll-sequence` | State Admin | View/control the next `XX-number` roll allocation |
| `POST` | `/api/v1/state/audit/run` | State Admin | Run the attendance compliance audit immediately |

## School academic workspace

These routes are automatically scoped to the signed-in school. `school_manager`
and `teacher` may read their workspace; manager-only and teacher-write rules are
shown explicitly.

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/school/overview` | Manager, Teacher | Own-school live KPIs |
| `GET` | `/api/v1/school/classes` | Manager, Teacher | Classes and streams |
| `POST` | `/api/v1/school/classes` | Manager | Add class stream |
| `GET` | `/api/v1/school/subjects` | Manager, Teacher | Class-level subject catalog |
| `POST` | `/api/v1/school/subjects` | Manager | Add subject catalog item |
| `GET` | `/api/v1/school/students` | Manager, Teacher | Own student registry |
| `POST` | `/api/v1/school/students` | Manager | Register student; server allocates immutable `IL-10000`-style roll |
| `GET/PATCH` | `/api/v1/school/students/{roll_or_legacy_id}` | Manager (GET also Teacher) | Full student profile and manager update functions |
| `GET/POST` | `/api/v1/school/attendance` | Manager, Teacher | Read or bulk record attendance |
| `POST` | `/api/v1/school/attendance/submit` | Manager, Teacher | Submit daily class roster |
| `GET/POST` | `/api/v1/school/grades` | Manager, Teacher write | Read/record own academic marks |
| `POST` | `/api/v1/school/grades/publish` | Manager | Publish scoped marks to State and append immutable event |
| `GET` | `/api/v1/school/exam-events` | Manager, Teacher | Own publication history |

## School management

| Method | Path | Access | Description |
|---|---|---|---|
| `GET/PATCH` | `/api/v1/school/profile` | Manager | Own identity, contacts, and tenant-private billing contact profile |
| `GET/POST` | `/api/v1/school/teachers` | Manager (GET also Teacher) | List/add school faculty |
| `GET/PATCH/DELETE` | `/api/v1/school/teachers/{teacher_id}` | Manager (GET also Teacher) | Full teacher profile, update, or remove; removal reassigns class/subject work to active faculty |
| `PUT` | `/api/v1/school/classes/{class_id}/subjects/{subject_id}/assignment` | Manager | Assign/reassign the subject teacher in one class stream |
| `GET` | `/api/v1/school/classes/{class_id}/breakdown` | Manager, Teacher | Own class roster, rolls, subjects, teacher assignments |

## Tenant-private finance

Every endpoint under `/api/v1/school/finance` requires `school_manager` and is
scoped to that manager’s tenant. State Admin and Inspector calls are rejected
with `403` and logged by the firewall.

| Method | Path | Description |
|---|---|---|
| `GET` | `/summary` | Billed, collected, outstanding totals |
| `GET/POST` | `/tuition-rates` | Base tuition configuration per class level |
| `GET/POST` | `/invoices` | Student ledger entries |
| `POST` | `/invoices/{invoice_id}/payments` | Record a payment transaction |
| `GET` | `/student-profiles` | Per-student billed/collected/balance view |

## React routes

After `cd web && npm run build`, FastAPI serves the primary React application.

| URL | Audience |
|---|---|
| `/` | Sign-in |
| `/school` | School workspace dashboard |
| `/school/students`, `/school/classes`, `/school/teachers`, `/school/billing` | Tenant management screens |
| `/state` | State command dashboard |
| `/state/directory`, `/state/institutions/{schoolId}` | State academic directory and school drill-down |
| `/students/{rollNumber}` | Full student profile/report card |

## Realtime

`WS /ws` is a same-origin, authenticated event bus. It uses the session cookie
when localStorage is unavailable, or accepts `?token=<jwt>` for compatible
clients. Academic-structure events refresh State Admin and Inspector directory
views without a page reload.

## Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness and runtime configuration summary |
