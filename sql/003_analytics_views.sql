-- ============================================================================
-- IMPLEMENTATION PHASE 3 — INTERACTIVE QUERY ANALYTICS PLATFORM
-- PostgreSQL 16 — Views A / B / C installed as first-class database views.
--
-- The API layer (app/services/analytics.py) mirrors these exact projections
-- in dialect-portable SQLAlchemy so the platform can also run its demo tier
-- on SQLite.
--
-- Execute AFTER 001_schema.sql and 002_security_firewall.sql:
--   psql -v ON_ERROR_STOP=1 -f sql/003_analytics_views.sql
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- View A: State Supervisor Core Command Map & Alarm Portal
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW state_compliance_map AS
SELECT
    ps.id AS school_id,
    ps.school_name,
    ps.state_license_number,
    COALESCE(dsl.attendance_submitted, FALSE) AS daily_attendance_logged,
    dsl.attendance_submitted_at AS time_received,
    COALESCE(dsl.alarm_triggered, FALSE) AS is_red_alarm_active,
    CASE
        WHEN dsl.alarm_triggered = TRUE THEN '🚨 RED ALARM: OVERDUE BY 3+ HOURS'
        WHEN dsl.attendance_submitted = FALSE THEN '⚠️ PENDING SUBMISSION WINDOW'
        ELSE '✅ COMPLIANT'
    END AS state_compliance_status
FROM private_schools ps
LEFT JOIN daily_submission_logs dsl
    ON ps.id = dsl.school_id AND dsl.log_date = CURRENT_DATE
WHERE ps.accreditation_status = 'Active'
ORDER BY is_red_alarm_active DESC, dsl.attendance_submitted ASC;

-- ---------------------------------------------------------------------------
-- View B: State-Wide Student ID National Lookup Engine (Class 1 to Class 12
--         Deep Search)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW state_student_lookup AS
SELECT
    ps.school_name,
    sc.class_level,
    sc.class_stream,
    s.national_student_id,
    s.roll_number,
    s.first_name,
    s.last_name,
    s.guardian_name,
    s.guardian_relationship,
    s.guardian_phone,
    s.guardian_email,
    s.emergency_contact_phone
FROM students s
JOIN private_schools ps ON s.school_id = ps.id
JOIN school_classes sc ON s.current_class_id = sc.id;

-- Usage:  SELECT * FROM state_student_lookup
--         WHERE national_student_id = :user_query_input
--            OR last_name ILIKE :user_query_input;

-- ---------------------------------------------------------------------------
-- View C / Query C: State Subject Benchmarking Index
--   Only scores carrying a matching publication token event inside
--   exam_submission_events are pulled (the Exam Data Release Valve).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW state_grade_analytics AS
SELECT
    ps.school_name,
    sc.class_level,
    sub.subject_name,
    COUNT(sg.id) AS total_marked_records,
    ROUND(AVG(sg.numeric_score), 2) AS structural_average_mark,
    MAX(sg.numeric_score) AS peak_score
FROM student_grades sg
JOIN private_schools ps  ON sg.school_id = ps.id
JOIN school_classes sc   ON sg.class_id = sc.id
JOIN subjects sub        ON sg.subject_id = sub.id
WHERE sg.is_published = TRUE
  AND EXISTS (
    SELECT 1
    FROM exam_submission_events ese
    WHERE ese.school_id         = sg.school_id
      AND ese.class_id          = sg.class_id
      AND ese.subject_id        = sg.subject_id
      AND ese.academic_year_id  = sg.academic_year_id
      AND ese.exam_name         = sg.exam_name
)
GROUP BY ps.school_name, sc.class_level, sub.subject_name
ORDER BY ps.school_name, sc.class_level, sub.subject_name;

-- The restricted reporting role receives these academic projections only.
GRANT SELECT ON state_compliance_map, state_student_lookup, state_grade_analytics TO state_readonly;

COMMIT;
