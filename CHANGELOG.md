# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] — 2026-09-01

### Added — Navigation history, role-gated media, design system & publishing controls

- **Global Navigation & History Back Button (Refinement 4)**: sticky
  `← Back` bar on every portal page — browser-history navigation
  (`navigate(-1)`) with an automatic fallback to the role's portal dashboard
  when the tab has no history stack (deep links), plus live route breadcrumbs
  (e.g. `Dashboard > Student Directory > Profile NG-10001`).
- **Role-Gated Photo & Media Engine (Refinement 5)**: `photo_data` columns on
  students and staff (additive migrations), integrated avatar cards on the
  Student details page and the Teacher profile modal. Uploads, replacements
  and deletions are **manager-only** (`/api/v1/school/media/…`, audited);
  teachers and students get a READ-ONLY badge with no path to the picker.
  The UI drives a hidden `accept="image/*"` file input, auto-downscales
  selections in-browser to ≤400px data URLs and previews them instantly;
  the API validates data-URL images (png/jpeg/webp/gif, ≤512 KiB decoded,
  `413` above) and the serialised profile carries the new media state.
- **Fluid Responsiveness (Refinement 6)**: page-level fluid grid utilities
  (`grid-fluid`), new 1280/920px breakpoints collapsing two-pane cards and
  detail grids, media overflow guards, and tablet/phone stacking for the
  timeline, roster marks, avatar card and publishing bar — no horizontal
  scrolling on any viewport class (verify with Test Mobile View).
- **Dynamic Design System & Sidebar Control Menu (Refinement 7)**: slide-out
  **Design & Layout Settings** drawer from the header — one-click global
  accent palette (`#2563eb`, `#059669`, `#d97706`, `#dc2626`, `#7c3aed`)
  applied instantly through root CSS variables across buttons, badges,
  progress bars and borders; typography presets (System Sans-Serif / Classic
  Serif / Monospace Technical); and real-time visibility toggles for the four
  dashboard blocks (Profile Card, Academic Overview, Attendance Summary,
  Biometrics Badge), two of which are new snapshot cards.
- **Publishing & Deployment Controls (Refinement 8)**: sticky Publishing
  Control Bar for School Managers — **Save Progress** persists the draft
  layout locally (localStorage) without touching live users; **Test Mobile
  View** opens a realistic 375×667 device-frame simulator rendering the
  genuinely responsive app via a same-origin iframe; **Push Live** raises a
  confirmation dialog that syncs theme variables and block configuration to
  the tenant record (`/api/v1/school/design-config`), audited and read back
  by every user in the school.

### Changed

- **Teacher RBAC tightened (Refinements 2-3)**: teachers are now confined to
  their portal by a route-level *teacher lane*; other school pages redirect
  to "My teaching day". Department Heads additionally receive the syllabus
  tracker nav entry and route. The staff API blocks teachers from opening
  **other** teachers' profiles (`403` + audit); self-reads and manager
  directory access are unchanged.
- The Vite dev server allowlists the sandboxed preview host (`.e2b.app`).

### Quality

- 8 new backend contracts (`tests/test_media_engine.py`): manager media gate,
  teacher/state write refusals, payload validation + size ceiling, staff
  cross-profile privacy, design-config defaults/validation/publish; the full
  pytest suite is 101 tests, all green.

### Added — Self-hosting (real, non-demo deployments)

- **`scripts/bootstrap_real.py`**: one-command provisioning of a production
  deployment with no demo records — a State Admin account, the current
  academic year, and a fully provisioned school tenant (Class 1–12, 120
  subjects, roll allocator, tuition rates, 8 template faculty, complete
  subject/staff mappings) with caller-chosen manager credentials.
- **`TERMUX.md`**: end-to-end guide for running the whole system realtime on
  a Termux phone at `http://127.0.0.1:8000` (one uvicorn process serving both
  API and built SPA), including a phone-safe dependency path (no
  `psycopg2-binary`, plain `uvicorn`) and every-day operations.
- **`schoolsystem-termux-realtime.zip`**: repo snapshot with a prebuilt
  `web/dist/`, so a phone deployment needs Python only — no Node build step.

## [2.1.0] — 2026-09-01

### Added — Manager syllabus administration & subject-restricted teacher portals

- **Editable Syllabus Tracker (School Manager)**: full plan CRUD — edit unit
  totals, midterm/final target percentages, term start/midterm/term-end
  deadlines; delete plans (cascades to topics and history); per-topic CRUD on
  the national-curriculum list (`syllabus_topics`); **Log Topic Covered**
  checklist for Managers and Department Heads that ticks exact units and
  writes the audited checkpoint; un-tick (undo) re-derives the checkpoint;
  managers can delete erroneous progress entries to override stats.
- **Teacher Authentication & RBAC**: dual-credential login —
  `{email,password}` **or** `{staff_identifier,pin}` (Argon2-hashed
  `staff_pin_hash`, uniform `401` on any failure). Teachers land on the
  restricted **My teaching day** dashboard (`/school/portal`); the sidebar for
  teachers exposes only that page. `is_department_head` flag shipped on user
  payloads.
- **Subject-Restricted Attendance Marking Engine**: `/teachers/me/schedule`
  returns the signed-in teacher's own slots for a date with active-period
  detection (08:00–16:50, eight periods) and pending-register counts;
  `/teachers/me/roster` GET/POST upserts `subject_attendance`
  (unique student+date+subject+period; Present/Absent/Late/Excused) but only
  when the timetable slot binds the same teacher+class+subject+period —
  otherwise `403`. Legacy attendance endpoints gained matching guards for
  teaching staff.

### Changed

- `POST /api/auth/login` accepts both credential styles; `/api/auth/me` and
  login payloads now include `is_department_head` and `staff_identifier`.
- Login screen offers an *Email & password* / *Staff ID & PIN* tab pair.

## [2.0.0] — 2026-08-31

### Added — Production modules

- **Module 1 — Teacher Absence & Substitution Engine**: weekly
  `timetable_slots` grid with class/teacher double-booking constraints,
  `teacher_absences` + `substitution_assignments` workflow, real-time ranked
  coverage recommendations (subject specialization, department
  qualifications, free period slots), one-click auto-cover, and
  `absence_logged` / `substitution_assigned` WebSocket events.
- **Module 2 — Syllabus Completion Tracker (Classes 1-12)**:
  `syllabus_plans` with midterm/final benchmark gates per class and subject,
  audited `syllabus_progress_entries` checkpoints, pace engine
  (start/midterm/end interpolation) driving `On Track` / `Ahead` /
  `Behind Schedule` status tags, and a Classes 1-12 tracking board.
- **Module 3 — Low-bandwidth Data Saver mode**: global off/auto/on toggle
  following the Network Information API (Save-Data, 2G/3G), `data-saver` CSS
  layer that strips animations/gradients/shadows and raises typographic
  contrast, chart primitives replaced by raw text metric tables, and
  `X-Data-Saver` request signalling.
- **Module 4 — Automated encrypted midnight backups**: SQLite change-capture
  triggers feeding `data_change_log` (PostgreSQL equivalents in
  `sql/004_ops_modules.sql`), 00:00 scheduler producing online SQLite
  snapshots and JSON deltas chained from the last snapshot, AES-256-GCM
  sealing (scrypt-derived keys, `NESBK1` container), SHA-256 + MD5 digests,
  integrity verification, audited downloads, retention purge, and a State-Admin
  backup console.
- **Module 5 — Biometric hardware management**: self-contained WebAuthn
  implementation (CBOR decoder, ES256/RS256 verification, origin/RP-ID/UV and
  clone-detection checks), credential lifecycle (enroll, revoke, re-scan),
  exam-hall-entry and staff-attendance verification registers with
  timestamps, and a QA simulated reader for hardware-free environments.

### Changed
- Seeded schools now carry subject-specialist teachers, a conflict-free
  two-periods-per-day timetable, Class 1-12 syllabus plans, and demo
  biometric verification history.
- `cryptography` added to the runtime dependencies (AES-256-GCM + ECDSA).

## [1.0.0] — 2026-08-29

### Added — Initial release
- **Phase 1 database tier** — monolithic PostgreSQL 14+ schema: `private_schools`,
  `academic_years`, `users`, Class 1–12 `school_classes`, `students` (immutable
  `STU-YYYY-XY123` national IDs), `subjects`, `student_grades`,
  `live_attendance`, `daily_submission_logs`, `communication_logs`,
  `exam_submission_events`, the private financial tier, and the specified
  performance indexes.
- **Security tier** — tenant-isolation RLS, the DENY-ALL financial firewall for
  state roles, `state_readonly` grants (academics only) and immutability
  triggers (student IDs, exam events, irreversible publication).
- **Compliance engine** — 15:00 Red Alarm audit worker (cron + manual trigger)
  with alarm UPSERTs, communication-gateway logging and live WebSocket
  broadcasts to state dashboards.
- **Release valve** — private mark drafts plus the irreversible
  "Publish Exam Marks to State" action with an append-only event ledger.
- **Analytics platform** — Query A command board (alarms first), Query B
  statewide student directory search, Query C subject benchmarking index
  filtered by `exam_submission_events` tokens — as PostgreSQL views and
  portable SQLAlchemy services.
- **API** — `/api/v1/state/` (read-only state portal), `/api/v1/school/`
  (JWT-scoped tenant ERP) and `/api/v1/school/finance/` (hard-firewalled
  private tier with audited 403 enforcement).
- **Portals** — `/admin/state` and `/admin/school` workspaces: alert map,
  global search, benchmarking; roster sheet, exam manager, class setup,
  private billing with student transaction profiles.
- **Seeding pipeline** — 3 mock schools × Class 1–12 tracks, 270 students with
  generated IDs and guardian contacts, attendance history and tokenized
  published exams.
- **Hardening** — Argon2id + JWT auth, login throttling (429), security
  headers, structured request logging, leak-free 500s, gzip.
- **Quality** — 36-test pytest suite (firewall, release valve, alarm engine,
  ID generator, analytics, hardening), PostgreSQL-grammar DDL validation,
  CI workflow, Docker/Compose deployment assets.
