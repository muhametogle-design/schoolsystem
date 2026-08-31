# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
