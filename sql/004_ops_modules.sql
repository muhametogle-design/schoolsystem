-- ============================================================================
-- OPERATIONS MODULES — PostgreSQL 16 migration
--
-- Adds the production modules on top of sql/001-003:
--   Module 1  substitution engine (timetable_slots, teacher_absences,
--             substitution_assignments)
--   Module 2  syllabus completion tracker (syllabus_plans,
--             syllabus_progress_entries)
--   Module 4  encrypted backups (data_change_log + row-level capture
--             triggers, backup_records, backup_audit_events)
--   Module 5  biometric hardware management (biometric_credentials,
--             biometric_verification_logs)
--
-- Every tenant table carries school_id and mirrors the SQLAlchemy models in
-- app/models/operations.py. Execute as the database owner AFTER 001-003:
--   psql -v ON_ERROR_STOP=1 -f sql/004_ops_modules.sql
--
-- NOTE FOR HARDENED DEPLOYMENTS: 002_security_firewall.sql applies FORCE RLS
-- to the tenant tables it knows about. The tables created here should be
-- added to your RLS policy set (school_id = NULL:not_null() OR
-- school_id = current_setting('app.school_id')::int) before exposing them to
-- the runtime role; the API additionally enforces tenancy at the route layer.
-- ============================================================================

BEGIN;

-- ============================================================================
-- MODULE 1 — TEACHER ABSENCE & SUBSTITUTION ENGINE
-- ============================================================================

-- One period of the weekly timetable. Two uniqueness rules make the engine
-- sound: a class cannot be double-booked, and a teacher cannot teach two
-- classes in the same period ("unassigned period slots").
CREATE TABLE timetable_slots (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0 = Monday
    period_number INT NOT NULL CHECK (period_number BETWEEN 1 AND 8),
    CONSTRAINT uq_timetable_class_period UNIQUE (school_id, class_id, day_of_week, period_number),
    CONSTRAINT uq_timetable_teacher_period UNIQUE (school_id, teacher_id, day_of_week, period_number)
);
CREATE INDEX idx_timetable_teacher_day ON timetable_slots(school_id, teacher_id, day_of_week);
CREATE INDEX idx_timetable_class_day ON timetable_slots(school_id, class_id, day_of_week);

CREATE TABLE teacher_absences (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    teacher_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    absence_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'logged' CHECK (status IN ('logged', 'covered', 'cancelled')),
    logged_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    CONSTRAINT uq_absence_per_teacher_day UNIQUE (school_id, teacher_id, absence_date)
);
CREATE INDEX idx_absences_school_date ON teacher_absences(school_id, absence_date);

CREATE TABLE substitution_assignments (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    absence_id INT NOT NULL REFERENCES teacher_absences(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    original_teacher_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    substitute_teacher_id INT REFERENCES users(id) ON DELETE SET NULL,
    day_of_week INT NOT NULL,
    date_for_day DATE NOT NULL,
    period_number INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'confirmed', 'completed')),
    match_score INT,
    match_reason TEXT,
    assigned_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_substitution_per_slot UNIQUE (absence_id, period_number, class_id)
);
CREATE INDEX idx_substitutions_school_date ON substitution_assignments(school_id, date_for_day);

-- ============================================================================
-- MODULE 2 — SYLLABUS COMPLETION TRACKER
-- ============================================================================

CREATE TABLE syllabus_plans (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    term VARCHAR(50) NOT NULL DEFAULT 'Term 1',
    total_units INT NOT NULL CHECK (total_units > 0),
    midterm_target_pct INT NOT NULL DEFAULT 45 CHECK (midterm_target_pct BETWEEN 0 AND 100),
    final_target_pct INT NOT NULL DEFAULT 100 CHECK (final_target_pct BETWEEN 0 AND 100),
    term_start DATE,
    midterm_date DATE,
    term_end DATE,
    created_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_syllabus_plan UNIQUE (school_id, class_id, subject_id, term)
);
CREATE INDEX idx_syllabus_plans_school ON syllabus_plans(school_id, term);

CREATE TABLE syllabus_progress_entries (
    id SERIAL PRIMARY KEY,
    plan_id INT NOT NULL REFERENCES syllabus_plans(id) ON DELETE CASCADE,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    entry_date DATE NOT NULL,
    units_after INT NOT NULL CHECK (units_after >= 0),
    note TEXT,
    recorded_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_syllabus_entries_plan ON syllabus_progress_entries(plan_id, entry_date);

-- ============================================================================
-- MODULE 4 — AUTOMATED ENCRYPTED BACKUPS
-- ============================================================================

-- Row-level change feed written by the triggers below; the midnight JSON
-- delta exports everything newer than the last snapshot's high-water mark.
CREATE TABLE data_change_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    row_pk VARCHAR(64) NOT NULL,
    operation VARCHAR(1) NOT NULL CHECK (operation IN ('I', 'U', 'D')),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payload JSONB
);
CREATE INDEX idx_change_log_id ON data_change_log(id);

CREATE TABLE backup_records (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    kind VARCHAR(20) NOT NULL CHECK (kind IN ('full_snapshot', 'json_delta')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    size_bytes INT NOT NULL DEFAULT 0,
    sha256 VARCHAR(64),
    md5 VARCHAR(32),
    encrypted BOOLEAN NOT NULL DEFAULT TRUE,
    encryption VARCHAR(50) DEFAULT 'AES-256-GCM',
    status VARCHAR(20) NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'failed')),
    duration_ms INT,
    triggered_by VARCHAR(20) DEFAULT 'scheduled',
    delta_rows INT,
    last_change_id BIGINT,
    row_counts JSONB,
    error TEXT
);
CREATE INDEX idx_backup_records_created ON backup_records(created_at);

CREATE TABLE backup_audit_events (
    id SERIAL PRIMARY KEY,
    backup_id INT REFERENCES backup_records(id) ON DELETE SET NULL,
    actor_id INT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(30) NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_backup_audit_created ON backup_audit_events(created_at);

-- Generic change-capture trigger functions (mirror the SQLite triggers that
-- app.core.db installs from the ORM metadata).
CREATE OR REPLACE FUNCTION schoolsystem_clg_capture() RETURNS trigger AS $$
DECLARE
    payload JSONB;
BEGIN
    IF TG_OP = 'DELETE' THEN
        payload := to_jsonb(OLD);
    ELSE
        payload := to_jsonb(NEW);
    END IF;
    INSERT INTO data_change_log (table_name, row_pk, operation, payload)
    VALUES (
        TG_TABLE_NAME,
        COALESCE(payload->>'id', ''),
        CASE TG_OP WHEN 'INSERT' THEN 'I' WHEN 'UPDATE' THEN 'U' ELSE 'D' END,
        payload
    );
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'private_schools', 'users', 'school_classes', 'subjects',
        'teaching_assignments', 'students', 'live_attendance',
        'daily_submission_logs', 'student_grades', 'exam_submission_events',
        'student_invoices', 'payment_transactions', 'tuition_rates',
        'teacher_absences', 'substitution_assignments', 'timetable_slots',
        'syllabus_plans', 'syllabus_progress_entries',
        'biometric_credentials', 'biometric_verification_logs'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_clg AFTER INSERT OR UPDATE OR DELETE ON %I
             FOR EACH ROW EXECUTE FUNCTION schoolsystem_clg_capture()',
            t, t
        );
    END LOOP;
END;
$$;

-- ============================================================================
-- MODULE 5 — BIOMETRIC HARDWARE MANAGEMENT (WEBAUTHN)
-- ============================================================================

CREATE TABLE biometric_credentials (
    id SERIAL PRIMARY KEY,
    school_id INT REFERENCES private_schools(id) ON DELETE CASCADE,
    owner_type VARCHAR(10) NOT NULL CHECK (owner_type IN ('student', 'staff')),
    owner_id INT NOT NULL,
    credential_id VARCHAR(512) UNIQUE NOT NULL,
    public_key TEXT NOT NULL,                 -- base64 COSE key
    sign_count INT NOT NULL DEFAULT 0,
    aaguid VARCHAR(36),
    transports VARCHAR(120),
    device_type VARCHAR(50),
    method VARCHAR(20) DEFAULT 'fingerprint',
    label VARCHAR(120),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP
);
CREATE INDEX idx_biometric_credentials_owner ON biometric_credentials(owner_type, owner_id);

CREATE TABLE biometric_verification_logs (
    id SERIAL PRIMARY KEY,
    school_id INT REFERENCES private_schools(id) ON DELETE CASCADE,
    owner_type VARCHAR(10),
    owner_id INT,
    purpose VARCHAR(30) NOT NULL CHECK (purpose IN ('exam_hall_entry', 'staff_attendance', 'enrollment_check')),
    result VARCHAR(30) NOT NULL CHECK (result IN ('success', 'failed', 'unknown_credential', 'revoked_credential')),
    credential_id VARCHAR(512),
    person_label VARCHAR(255),
    detail TEXT,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operated_by INT REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX idx_biometric_logs_school_time ON biometric_verification_logs(school_id, verified_at);
CREATE INDEX idx_biometric_logs_owner ON biometric_verification_logs(owner_type, owner_id);

COMMIT;
