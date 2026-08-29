# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
