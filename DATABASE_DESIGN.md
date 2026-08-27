# Database Design Notes

## Entities

### Identity / tenancy
- `campus` — tenant root.
- `app_users` — login principals; `role` in `clerk|dean|state_admin|system|aggregator`.
- `managers` — NE-MID managers, Ed25519 verification public keys.

### Students
- `students` — NE-SID, demographics, national id hash, coordinates.
- `enrollments` — current/year enrolment for a campus.
- `student_mobility` — chronological schooling-history tree (`previous_mobility_id`).
- `transfer_clearances` — dean-signed clearance files.

### Academics
- `state_curricula`, `academic_years`, `terms`, `classrooms`.
- `course_sections` — NE-CID binding state curriculum + campus section + room.
- `course_enrollments`, `transcripts`, `exam_sheets`, `attendance`,
  `incident_reports`, `truancy_marks`.

### Teachers / payroll
- `teachers` — NE-TID.
- `teacher_qualifications`, `teacher_certifications`, `teacher_assignments`.
- `civil_service_grades` — grade tiers and base salary.
- `teacher_payroll_profiles`, `payroll_entries`.
- `teacher_background_logs`, `teacher_exit_records`.

### Locking / pipeline
- `record_locks` — dean signatures & frozen payload hash.
- `ingestion_jobs`, `aggregation_batches`.

### Central state (Phase 3/4)
- `central.student_registry`, `central.teacher_registry`.
- `central.funding_payouts`, `central.kpi_rollups`.

## Indexing strategy

Indexes are in `sql/002_indexes.sql`:

- `(campus_id, attendance_date)` for phase 1/2 daily summaries.
- `(campus_id, employment_state)` for teacher vacancy tracking.
- `(campus_id, academic_year_id, term_id)` for section review.
- GIN indexes on `schooling_history`, `schedule_json`, `kpi_metrics`.
- Partial index on `teacher_certifications(expiry_date)` for renewal jobs.

## Idempotency

- `snapshot_key` in `central.*` prevents double-counting in overnight runs.
- `UNIQUE (teacher_id, pay_period)` prevents duplicate payroll.
- `UNIQUE (entity_type, entity_id)` on `record_locks` prevents double locks.
