# Database Design

Authoritative DDL: `sql/001_schema.sql` (tables + performance indexes),
`sql/002_security_firewall.sql` (RLS, grants, immutability triggers),
`sql/003_analytics_views.sql` (Views A/B/C). The SQLAlchemy models in
`app/models/` mirror the schema so the demo tier runs on SQLite unchanged.

## Entity map

```text
private_schools ──┬── users (role: school_manager | teacher; NULL school = state)
                  ├── school_classes (Class 1..12 + stream, CHECK-constrained)
                  │      └── students (immutable STU-YYYY-XY123 national ID)
                  ├── subjects (per class level)
                  │      └── student_grades  ←── exam_submission_events (immutable)
                  ├── live_attendance (per student per day, UNIQUE(student_id, date))
                  ├── daily_submission_logs (UNIQUE(school_id, log_date) — 12PM deadline
                  │                        + 3PM red alarm state)
                  ├── communication_logs (Red_Alarm / notification outbox)
                  └── 🔒 tuition_rates · student_invoices · payment_transactions
                                        (financial firewall zone — no state access)
academic_years (cross-tenant)      security_audit_log (firewall decisions)
```

## Key constraints

| Rule | Enforcement |
|---|---|
| Class levels restricted to Class 1–12 | `chk_class_level` CHECK |
| Scores within 0–100 | `chk_score_range` CHECK |
| One grade per (student, subject, year, exam) | `UNIQUE` constraint |
| One attendance row per student per day | `uq_attendance_per_day` |
| Worker UPSERT target | `UNIQUE(school_id, log_date)` on `daily_submission_logs` |
| State users never bound to a tenant | `chk_state_user_has_no_school` |
| National student ID never rewritten | trigger `trg_student_id_immutable` |
| `exam_submission_events` append-only | trigger `trg_exam_event_immutable` |
| Published marks cannot return to draft | trigger `trg_grade_publication_irreversible` |

## Performance indexes (per specification)

```sql
CREATE INDEX idx_student_search_national_id ON students(national_student_id);
CREATE INDEX idx_student_names               ON students(last_name, first_name);
CREATE INDEX idx_grades_lookup               ON student_grades(school_id, class_id, subject_id);
CREATE INDEX idx_attendance_compliance       ON live_attendance(date, school_id);
CREATE INDEX idx_compliance_tracker          ON daily_submission_logs(log_date, alarm_triggered);
```

Plus supporting indexes for the release valve, event ledger, communication
feed and invoice ledger hot paths.

## Analytics views (Phase 3)

* `state_compliance_map` — **View A**: every active school with today's
  submission state, alarm flag and 🚨/⚠️/✅ status, alarms sorted first.
* `state_student_lookup` — **View B**: statewide Class 1–12 deep search joined
  with guardian + emergency contact details (queried by national ID or
  `ILIKE` surname).
* `state_grade_analytics` — **View C**: per school/class/subject COUNT/AVG/MAX
  benchmarking, `WHERE is_published = TRUE` (release valve at the query root).

The API mirrors all three in dialect-portable SQLAlchemy
(`app/services/analytics.py`).
