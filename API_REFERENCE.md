# API Reference

Base URL: `/`. Interactive OpenAPI documentation is available at `/docs`.
Protected routes accept `Authorization: Bearer <jwt>` or the same-origin
HttpOnly session cookie returned by `POST /api/auth/login`.

## Authentication

| Method | Path | Access | Result |
|---|---|---|---|
| `POST` | `/api/auth/login` | Public | `{ email, password }` **or** `{ staff_identifier, pin }` → token plus role/school identity; also sets a secure same-origin cookie when applicable |
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

## Production modules

### Teacher Absence & Substitution Engine (`Module 1`)

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/school/timetable?day=` | Any school user | Weekly timetable grid (day 0 = Monday) |
| `GET` | `/api/v1/school/absences?date=` | Any school user | Recent absences with confirmed substitutions |
| `POST` | `/api/v1/school/absences` | Manager / Teacher | Log an absence; response carries the live coverage panel |
| `GET` | `/api/v1/school/absences/{id}/recommendations` | Any school user | Recompute ranked substitutes for every affected slot |
| `POST` | `/api/v1/school/absences/{id}/auto-assign` | Manager / Teacher | Confirm the best candidate for every open slot |
| `POST` | `/api/v1/school/substitutions` | Manager / Teacher | Confirm one recommended candidate for one slot |
| `DELETE` | `/api/v1/school/absences/{id}` | Manager / Teacher | Cancel an absence |

Candidates are scored on subject specialization (currently teaches the
subject), department/qualification keywords, department affinity, and free
period availability; unavailable teachers are filtered out entirely.

### Syllabus Completion Tracker (`Module 2`)

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/school/syllabus/summary?class_level=&term=` | Any school user | Classes 1-12 progress board with `On Track` / `Ahead` / `Behind Schedule` tags |
| `GET` | `/api/v1/school/syllabus/plans/{id}` | Any school user | Plan detail with the audited checkpoint history |
| `POST` | `/api/v1/school/syllabus/plans` | Manager | Create a pacing plan (units, midterm/final gates, term window) |
| `PUT` | `/api/v1/school/syllabus/plans/{id}/benchmarks` | Manager | Adjust midterm/final benchmark gates |
| `POST` | `/api/v1/school/syllabus/plans/{id}/progress` | Manager / Teacher | Record an audited progress checkpoint (cumulative units) |
| `PUT` | `/api/v1/school/syllabus/plans/{id}` | Manager | Edit plan — term, unit total, target percentages, term start/midterm/term-end deadlines |
| `DELETE` | `/api/v1/school/syllabus/plans/{id}` | Manager | Delete plan with its topics and checkpoint history |
| `DELETE` | `/api/v1/school/syllabus/plans/{id}/progress/{entry_id}` | Manager | Override stats: remove an erroneous checkpoint and re-derive progress |
| `GET` | `/api/v1/school/syllabus/plans/{id}/topics` | Any school user | Ordered national-curriculum topic list (`code`, `title`, `is_done`, …) |
| `POST` | `/api/v1/school/syllabus/plans/{id}/topics` | Manager / Dept Head | Append a curriculum topic (position auto-assigned) |
| `PUT` | `/api/v1/school/syllabus/plans/{id}/topics/{topic_id}` | Manager / Dept Head | Rename / re-code a topic |
| `DELETE` | `/api/v1/school/syllabus/plans/{id}/topics/{topic_id}` | Manager / Dept Head | Remove a topic |
| `POST` | `/api/v1/school/syllabus/plans/{id}/topics/log-covered` | Manager / Dept Head | **Log Topic Covered** — tick topic ids, write audited checkpoint, return refreshed plan+topics |
| `POST` | `/api/v1/school/syllabus/plans/{id}/topics/undo-covered` | Manager / Dept Head | Un-tick topic ids and re-derive the latest checkpoint |

Expected completion is interpolated between term start (0%), the midterm gate,
and the final gate; status is derived from the gap (±5 percentage points).

### Teacher Portal & Subject-Restricted Attendance (`Refinements 2–3`)

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/school/teachers/me/schedule?date=` | Teacher | Own slots for the date: period label, class, subject, roster/marked counts, active-period detection (8 periods, 08:00–16:50), pending-register total |
| `GET` | `/api/v1/school/teachers/me/roster?date=&class_id=&subject_id=&period_number=` | Teacher | Quick-roster payload (students + current marks) for an **own** timetable slot; `403` for any other teacher's slot |
| `POST` | `/api/v1/school/teachers/me/roster` | Teacher | Upsert `subject_attendance` marks (Present/Absent/Late/Excused) for an own slot; unique per student+date+subject+period |

### Encrypted Backups (`Module 4`, State Admin only)

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/admin/backups` | State Admin | Artefact list + pipeline configuration |
| `POST` | `/api/v1/admin/backups/run` | State Admin | Manual export (`full_snapshot` or `json_delta`) |
| `GET` | `/api/v1/admin/backups/{id}/verify` | State Admin | Recompute SHA-256/MD5 and audit the verdict |
| `GET` | `/api/v1/admin/backups/{id}/download?format=encrypted\|decrypted` | State Admin | Download the AES-256-GCM container or the decrypted payload (both audited) |
| `GET` | `/api/v1/admin/backups/audit` | State Admin | Audit trail (created/downloaded/verified/purged/…) |

Artefacts are `NESBK1` containers: magic header, JSON header (nonce, scrypt
KDF parameters), AES-256-GCM ciphertext + tag. The midnight scheduler exports
a full snapshot plus a trigger-captured JSON delta daily at
`BACKUP_TIME` (default 00:00 platform timezone).

### Biometric Hardware Management (`Module 5`)

| Method | Path | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/school/biometrics/overview` | Any school user | Registration status roster + KPI counts |
| `GET` | `/api/v1/school/biometrics/verifications?purpose=&result=` | Any school user | Timestamped exam-hall / staff-attendance register |
| `POST` | `/api/v1/school/biometrics/enroll/options` | Manager / Teacher | WebAuthn registration options (challenge, RP, exclude list) |
| `POST` | `/api/v1/school/biometrics/enroll/verify` | Manager / Teacher | Verify attestation and persist the credential |
| `POST` | `/api/v1/school/biometrics/verify/options` | Any school user | Resolve a person by roll number / staff ID; assertion options |
| `POST` | `/api/v1/school/biometrics/verify/complete` | Any school user | Verify the assertion; stamp the register; broadcast live event |
| `POST` | `/api/v1/school/biometrics/credentials/{id}/rescan` | Manager / Teacher | Hardware re-scan: revoke + fresh enrollment options |
| `DELETE` | `/api/v1/school/biometrics/credentials/{id}` | Manager / Teacher | Revoke a credential |

Server-side WebAuthn (ES256/RS256) is implemented in
`app/services/biometrics.py` with origin, RP-ID hash, user-verification and
signature-counter clone checks. `WEBAUTHN_RP_ID` / `WEBAUTHN_EXPECTED_ORIGINS`
default to `auto` (resolved from the request host); pin them in production.

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
