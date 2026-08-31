# SchoolSystem — Multi-tenant School Management

A FastAPI + React system for private schools in the North-East education
network. It provides a separate tenant workspace for each school and a
state-side academic oversight portal, while keeping every school's financial
records out of State Admin and Inspector views.

## What is included

- **Five initial school tenants only**: Ilays Educational Academy (`IL`), Muse
  Yusuf Secondary School (`MY`), Nugaal High School (`NG`), ALQALAM SCHOOLS
  (`AQ`), and Las Anod Boarding Secondary School (LBSS) (`LB`).
- **Class 1 through Class 12** with multiple stream support.
- The mandatory core curriculum in every class: Somali (Af-Somali), Arabic,
  English, Mathematics, Islamic Studies, Physics, Chemistry, Biology, History,
  and Geography.
- At least eight named teachers per seeded school and an **authoritative
  class + subject + teacher assignment** for every subject in every stream.
- Automatic immutable student roll numbers such as `NG-10023`. Each school has
  a unique two-letter code and a State Admin-controlled next sequence.
- School Manager CRUD for teachers, class streams, subjects, student profiles,
  schedules, school identity, tuition rates, invoices, and payments.
- State Admin tenant provisioning: one request builds a new Class 1–12 tenant
  template, curriculum catalog, eight editable setup faculty profiles,
  assignments, roll allocator, and termly billing scaffold.
- Inspector read-only cross-school academic visibility: school directory,
  teacher profiles, class rosters, roll numbers, and class-specific subject
  assignments.
- Attendance deadline/red-alarm workflow, published-exam release valve, and
  live academic-structure refresh notifications.
- **Teacher Absence & Substitution Engine** — logging an absence instantly
  ranks available colleagues per affected timetable period using department
  qualifications, subject specialization, and free (unassigned) period slots,
  with one-click confirm and auto-cover.
- **Syllabus Completion Tracker (Classes 1-12)** — per class/subject pacing
  plans with midterm and final exam benchmark gates, audited progress
  checkpoints, and automatic `On Track` / `Ahead` / `Behind Schedule` flags.
- **Low-bandwidth Data Saver mode** — a global toggle (off / auto / on) that
  follows the device's Network Information API; when active it strips
  animations, gradients and shadows, switches to high-contrast typography,
  and replaces every graphic chart with raw text metrics.
- **Automated encrypted midnight backups** — a 00:00 worker produces SQLite
  snapshots plus trigger-captured JSON deltas, seals both with AES-256-GCM,
  records SHA-256/MD5 digests, and exposes a State-Admin console with
  verification, downloads, and a full audit trail.
- **Biometric hardware management** — WebAuthn enrollment and verification
  (fingerprint readers, smartcards, platform authenticators) for students and
  staff, with exam-hall-entry and staff-attendance registers and hardware
  re-scan/re-enroll support.

## Roles and boundaries

| Role | Can do | Cannot do |
|---|---|---|
| **State Admin** | Add/configure school tenants; view academic structure across schools; control next roll sequence | Open a tenant billing profile, invoices, payments, balances, or tuition configuration |
| **Inspector** | Read-only academic oversight across schools; open a teacher, class, subject, or student roll-number view | Change schools, students, staff, schedules, marks, or financial records |
| **School Manager** | Manage own school's students, teachers, subjects, class streams, assignments, schedules, and all private billing records | See another school's tenant records or state-wide data |
| **Teacher** | View own school's academic workspace; record attendance and assessment data | Manage staff, private billing, or another school |

The financial firewall is enforced in the API guard layer and in the
PostgreSQL RLS/grants script. State-facing serializers never return billing
fields, tuition, invoices, transactions, or balances.

## Run locally

### React production interface (recommended)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

cd web
npm ci
npm run build
cd ..

.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000` on the same device. The FastAPI server serves the
built React application and all API calls use relative URLs.

### React development interface

Keep the backend running on port `8000`, then in a second terminal:

```bash
cd web
npm ci
npm run dev -- --host 0.0.0.0 --port 5174
```

Open `http://127.0.0.1:5174`. Vite proxies `/api` and `/ws` to the local
backend, so the mobile browser never has to call a different localhost host.

### Termux / Debian PRoot

Run the exact same commands inside the Debian PRoot where Python dependencies
are installed. If an older local demo database still contains Greenfield,
Horizon, or Crescent placeholder records, stop the server and reset it once:

```bash
cd ~/schoolsystem
.venv/bin/python -m scripts.seed_data --reset
```

`--reset` deliberately clears local **SQLite** records before loading the five
required schools. On a fresh database, normal startup auto-seeds the requested
estate.

### PostgreSQL 16 hardening order

For a dedicated PostgreSQL deployment, apply the baseline schema, seed the
initial estate, then install the RLS/firewall script as the database owner:

```bash
PG_URL='postgresql://school:password@host:5432/schoolsystem'
APP_DATABASE_URL='postgresql+psycopg2://school:password@host:5432/schoolsystem'
psql "$PG_URL" -v ON_ERROR_STOP=1 -f sql/001_schema.sql
DATABASE_URL="$APP_DATABASE_URL" .venv/bin/python scripts/seed_data.py
psql "$PG_URL" -v ON_ERROR_STOP=1 -f sql/002_security_firewall.sql
psql "$PG_URL" -v ON_ERROR_STOP=1 -f sql/003_analytics_views.sql
psql "$PG_URL" -v ON_ERROR_STOP=1 -f sql/004_ops_modules.sql
```

`sql/004_ops_modules.sql` creates the operations-module tables (substitution
engine, syllabus tracker, backups, biometrics) and installs the row-level
change-capture triggers that feed the JSON delta exports. Set
`BACKUP_ENCRYPTION_KEY` before production: when it is empty the backup key is
derived from `JWT_SECRET_KEY`, which is acceptable only for local demos.

`002_security_firewall.sql` uses `FORCE ROW LEVEL SECURITY`; do not run the
application as a PostgreSQL superuser or a role with `BYPASSRLS`. The API sets
the signed user’s tenant context on every authenticated request. The included
Docker Compose stack uses the same schema-first flow and its normal seed path.

## Initial local accounts

| Role | Email | Password |
|---|---|---|
| State Admin | `stateadmin@education.gov` | `StateAdmin@2026` |
| Inspector | `inspector@education.gov` | `State@2026` |
| Nugaal School Manager | `manager@nugaal.edu.so` | `School@2026` |
| Nugaal Teacher | `teacher@nugaal.edu.so` | `Teach@2026` |

All seeded school managers use `School@2026`; all first seeded teachers use
`Teach@2026`. Change credentials before real use.

## Data model highlights

- `private_schools.school_code` is globally unique, exactly two uppercase
  letters, and is used by `students.roll_number`.
- `school_roll_sequences` persists the next never-reused integer for each
  tenant. Registration advances it in the same transaction.
- `subjects` are catalogued per school/class level. `teaching_assignments`
  makes the teacher mapping explicit per class stream and subject.
- `users.role` supports `state_admin`, `inspector`, the legacy migration alias
  `state_inspector`, `school_manager`, and `teacher`.
- Billing contacts are tenant-private fields; tuition rates, invoices, and
  payments remain in the dedicated financial tier.

See [`sql/001_schema.sql`](sql/001_schema.sql) for the PostgreSQL baseline and
[`sql/002_security_firewall.sql`](sql/002_security_firewall.sql) for RLS,
role grants, immutability, and the financial firewall.

## Test and quality checks

```bash
.venv/bin/python -m pytest -q
cd web && npm run build
node --check ../frontend/app.js
```

The regression suite verifies the exact five-school seed, unique codes,
Class 1–12 core curriculum, eight-teacher minimum, full assignment coverage,
sequential roll numbers, State Admin provisioning, Inspector read-only access,
tenant isolation, the financial firewall, and the release valve.
