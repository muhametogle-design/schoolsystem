# Database Design

Authoritative PostgreSQL 16 DDL:

- [`sql/001_schema.sql`](sql/001_schema.sql) — relational tables, checks, and indexes
- [`sql/002_security_firewall.sql`](sql/002_security_firewall.sql) — FORCE RLS,
  grants, financial firewall, and immutability triggers
- [`sql/003_analytics_views.sql`](sql/003_analytics_views.sql) — State academic
  reporting views

The SQLAlchemy models in `app/models/` mirror this schema for the SQLite local
tier and automated tests.

## Entity map

### Operations tier (sql/004_ops_modules.sql)

| Table | Purpose |
|---|---|
| `timetable_slots` | Weekly period grid; unique per (school, class, day, period) and (school, teacher, day, period) |
| `teacher_absences` | One absence per teacher per date; `logged → covered / cancelled` |
| `substitution_assignments` | Confirmed covers with frozen engine score/reason |
| `syllabus_plans` | Class+subject pacing contract with midterm/final benchmark gates |
| `syllabus_progress_entries` | Audited cumulative-unit checkpoints |
| `syllabus_topics` | Per-plan national-curriculum unit checklist (see Refinements) |
| `data_change_log` | Row-level change feed written by triggers (JSON payload per row) |
| `backup_records` | Artefact metadata: kind, size, SHA-256, MD5, encryption, status |
| `backup_audit_events` | Admin audit trail (created/verified/downloaded/purged) |
| `biometric_credentials` | WebAuthn credentials (COSE public key, sign counter, method) |
| `biometric_verification_logs` | Timestamped exam-hall-entry / staff-attendance register |

### Refinements (sql/005_module_refinements.sql)

| Table / column | Purpose |
|---|---|
| `users.staff_pin_hash` | Argon2 hash for Staff ID + PIN login (demo PIN `2026`) |
| `users.is_department_head` | Grants curriculum topic-log authority alongside the manager |
| `syllabus_topics` | Ordered national-curriculum list per plan (position, code, title, `is_done`, done date/by) |
| `subject_attendance` | Per-subject-period register; unique (student, date, subject, period); Present/Absent/Late/Excused |

```text
private_schools (unique two-letter school_code)
  ├── school_roll_sequences (next roll integer per school)
  ├── users
  │     ├── school_manager / teacher (bound to one school)
  │     └── state_admin / inspector / state_inspector (school_id NULL)
  ├── school_classes (Class 1..12 + stream)
  │     ├── students (immutable roll_number: XX-sequence)
  │     └── teaching_assignments (one class + subject + teacher mapping)
  ├── subjects (mandatory catalog per class level)
  ├── student_grades ← exam_submission_events (append-only release ledger)
  ├── live_attendance → daily_submission_logs (deadline/alarm state)
  │     └── subject_attendance (per subject-period register)
  ├── communication_logs (notification outbox)
  └── tenant-private finance
        ├── tuition_rates
        ├── student_invoices
        └── payment_transactions

academic_years (global calendar)     security_audit_log (guard decision evidence)
```

A `Subject` describes a curriculum item at one school/class level. A
`TeachingAssignment` is the authoritative mapping for each class stream and
subject; it is not inferred from historical grade entry. Seed and State Admin
provisioning create all ten core subjects and a mapped teacher for every class.
Manager removal/deactivation of a teacher reassigns that work first, preserving
the operational curriculum.

## Key constraints and controls

| Rule | Enforcement |
|---|---|
| School code is globally unique, exactly two uppercase letters | unique key + `chk_school_code` |
| Class levels restricted to Class 1–12 | `chk_class_level` / `chk_subject_class_level` |
| One class stream per school/level | `uq_class_per_school` |
| One subject catalog code per school/level | `uq_subject_per_school` |
| One teacher mapping per school/class/subject | `uq_class_subject_assignment` |
| Roll numbers unique and never rewritten | unique key + `trg_student_id_immutable` |
| School-code prefix cannot change after enrollment | API check + `trg_school_code_after_enrollment` |
| Scores within 0–100 | `chk_score_range` |
| One grade per student/subject/year/exam | `uq_grade_record` |
| One attendance row per student/day | `uq_attendance_per_day` |
| Worker UPSERT target | `uq_daily_log` on school/date |
| State roles never bound to a tenant | `chk_state_user_has_no_school` |
| Exam release ledger append-only | `trg_exam_event_immutable` |
| Published marks cannot return to draft | `trg_grade_publication_irreversible` |

## Roll allocation

`school_roll_sequences.next_value` begins at `10000` for each tenant.
Registration locks the sequence row (`SELECT … FOR UPDATE` in PostgreSQL),
issues `school_code-next_value`, and advances the value in the same
transaction. A State Admin can inspect or advance a sequence but cannot move
it backward or reuse an issued roll. This keeps `NG-10023` style identifiers
stable even after a student is withdrawn.

## RLS and financial boundary

Every tenant table is FORCE-RLS protected. The request layer sets a trusted
PostgreSQL session context only after it validates the signed token’s role and
school binding against the current account row.

- Tenant role: own school only.
- State Admin: cross-school academic visibility plus tenant provisioning.
- Inspector: cross-school read-only academic visibility.
- Finance tables: state contexts match no readable rows.
- `students.fee_status` is a finance-adjacent field and is omitted from the
  `state_readonly` column grant as well as all State API serializers.

See [`SECURITY_AND_RLS.md`](SECURITY_AND_RLS.md) for runtime role and deployment
requirements.

## State analytics views

- `state_compliance_map` — active-school attendance status and Red Alarm state.
- `state_student_lookup` — cross-school Class 1–12 lookup with roll numbers.
- `state_grade_analytics` — school/class/subject benchmarks restricted to
  published grades carrying a release event.

The API mirrors these projections through dialect-portable SQLAlchemy in
`app/services/analytics.py`, allowing the same flows in SQLite local mode.
