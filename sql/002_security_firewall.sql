-- ============================================================================
-- PHASE 1 (cont.) — TENANT ISOLATION, THE FINANCIAL FIREWALL & IMMUTABILITY
-- PostgreSQL 16
--
-- THE CRITICAL FIREWALL RULE, ENFORCED AT THE DATABASE LEVEL:
--   Under no circumstances can a State Government user or supervisor access,
--   query, or view any school's private financial data, base tuition rates,
--   billing configurations, student ledgers, outstanding balances, or
--   transaction payment logs.
--
-- Enforcement layers installed by this script:
--   1. A dedicated STATE_READONLY role that is granted SELECT on academic
--      tables ONLY — it receives zero privileges on the financial tier.
--   2. Row-Level Security on tenant tables so tenant sessions are scoped to
--      their own school_id.
--   3. RLS on the financial tier that explicitly evaluates to FALSE for any
--      state role, even if a grant were accidentally added later.
--   4. Immutability triggers: exam_submission_events can never be UPDATEd or
--      DELETEd, and students.national_student_id can never be rewritten.
--
-- Execute as superuser / database owner AFTER 001_schema.sql:
--   psql -v ON_ERROR_STOP=1 -f sql/002_security_firewall.sql
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Session context helpers (set per API request by the application server)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_current_school_id() RETURNS INT AS $$
    SELECT NULLIF(current_setting('app.school_id', true), '')::INT;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_current_role_name() RETURNS TEXT AS $$
    SELECT COALESCE(NULLIF(current_setting('app.role', true), ''), 'none');
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_is_state_role() RETURNS BOOLEAN AS $$
    SELECT app_current_role_name() IN ('state_admin', 'inspector', 'state_inspector');
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_is_state_admin() RETURNS BOOLEAN AS $$
    SELECT app_current_role_name() = 'state_admin';
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- 1. TENANT ISOLATION — every tenant row is scoped by school_id
-- ---------------------------------------------------------------------------
ALTER TABLE private_schools      ENABLE ROW LEVEL SECURITY;
ALTER TABLE users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_roll_sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_classes       ENABLE ROW LEVEL SECURITY;
ALTER TABLE students             ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects             ENABLE ROW LEVEL SECURITY;
ALTER TABLE teaching_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_grades       ENABLE ROW LEVEL SECURITY;
ALTER TABLE live_attendance      ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_submission_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_submission_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE communication_logs   ENABLE ROW LEVEL SECURITY;

-- Academic tier: a school session sees only its own tenant rows;
-- a state session sees EVERYTHING (read visibility is granted separately).
CREATE POLICY tenant_isolation ON private_schools
    USING (id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (id = app_current_school_id() OR app_is_state_admin());

-- State users may read staff academic profiles; tenant staff are scoped.
CREATE POLICY tenant_isolation ON users
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

-- Inspectors cannot access allocation state. State Admins oversee every
-- sequence; a school's Manager may atomically advance only its own allocator
-- while registering a student. Teachers never receive this write capability.
CREATE POLICY roll_sequence_admin_only ON school_roll_sequences
    USING (school_id = app_current_school_id() OR app_is_state_admin())
    WITH CHECK (
        app_is_state_admin()
        OR (
            school_id = app_current_school_id()
            AND app_current_role_name() = 'school_manager'
        )
    );

CREATE POLICY tenant_isolation ON school_classes
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

CREATE POLICY tenant_isolation ON students
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

CREATE POLICY tenant_isolation ON subjects
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

CREATE POLICY tenant_isolation ON teaching_assignments
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

-- Draft marks stay private to the school; publication flips is_published and
-- the state may then read the released rows.
CREATE POLICY tenant_isolation ON student_grades
    USING (
        school_id = app_current_school_id()
        OR (app_is_state_role() AND is_published = TRUE)
    )
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

CREATE POLICY tenant_isolation ON live_attendance
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

CREATE POLICY tenant_isolation ON daily_submission_logs
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

CREATE POLICY tenant_isolation ON exam_submission_events
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

CREATE POLICY tenant_isolation ON communication_logs
    USING (school_id = app_current_school_id() OR app_is_state_role())
    WITH CHECK (school_id = app_current_school_id() OR app_is_state_admin());

-- ---------------------------------------------------------------------------
-- 2. 🔒 THE FINANCIAL FIREWALL 🔒
--    tuition_rates, student_invoices, payment_transactions carry an explicit
--    DENY-ALL policy for state roles. A state session cannot even see that
--    the rows exist.
-- ---------------------------------------------------------------------------
ALTER TABLE tuition_rates        ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_invoices     ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;

-- The database owner normally bypasses RLS. FORCE is essential because the
-- application may connect as the schema owner in smaller deployments: every
-- runtime request must still honour the tenant context set by app/core/db.py.
ALTER TABLE private_schools       FORCE ROW LEVEL SECURITY;
ALTER TABLE users                 FORCE ROW LEVEL SECURITY;
ALTER TABLE school_roll_sequences FORCE ROW LEVEL SECURITY;
ALTER TABLE school_classes        FORCE ROW LEVEL SECURITY;
ALTER TABLE students              FORCE ROW LEVEL SECURITY;
ALTER TABLE subjects              FORCE ROW LEVEL SECURITY;
ALTER TABLE teaching_assignments  FORCE ROW LEVEL SECURITY;
ALTER TABLE student_grades        FORCE ROW LEVEL SECURITY;
ALTER TABLE live_attendance       FORCE ROW LEVEL SECURITY;
ALTER TABLE daily_submission_logs FORCE ROW LEVEL SECURITY;
ALTER TABLE exam_submission_events FORCE ROW LEVEL SECURITY;
ALTER TABLE communication_logs    FORCE ROW LEVEL SECURITY;
ALTER TABLE tuition_rates         FORCE ROW LEVEL SECURITY;
ALTER TABLE student_invoices      FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_transactions  FORCE ROW LEVEL SECURITY;

CREATE POLICY financial_firewall ON tuition_rates
    USING (school_id = app_current_school_id() AND NOT app_is_state_role())
    WITH CHECK (
        (school_id = app_current_school_id() AND NOT app_is_state_role())
        OR app_is_state_admin() -- provisioning-only INSERT; USING still denies reads
    );

CREATE POLICY financial_firewall ON student_invoices
    USING (school_id = app_current_school_id() AND NOT app_is_state_role())
    WITH CHECK (
        (school_id = app_current_school_id() AND NOT app_is_state_role())
        OR app_is_state_admin() -- provisioning-only INSERT; USING still denies reads
    );

CREATE POLICY financial_firewall ON payment_transactions
    USING (school_id = app_current_school_id() AND NOT app_is_state_role())
    WITH CHECK (
        (school_id = app_current_school_id() AND NOT app_is_state_role())
        OR app_is_state_admin() -- provisioning-only INSERT; USING still denies reads
    );

-- ---------------------------------------------------------------------------
-- 3. ROLE GRANTS — the State Government gets strictly READ-ONLY academics
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'state_readonly') THEN
        CREATE ROLE state_readonly NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'school_app') THEN
        CREATE ROLE school_app NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO state_readonly, school_app;

-- READ-ONLY academic visibility for the State (super-admin dashboards).
-- PrivateSchool contains tenant-private billing contacts. Grant only the
-- public accreditation columns to state_readonly, never billing_* columns.
GRANT SELECT (id, state_license_number, school_code, school_name, proprietor_name,
              contact_phone, contact_email, physical_address, accreditation_status, created_at)
ON private_schools TO state_readonly;
GRANT SELECT ON academic_years, school_classes, subjects,
                teaching_assignments, student_grades, live_attendance,
                daily_submission_logs, exam_submission_events,
                communication_logs
TO state_readonly;
-- fee_status is a tenant billing standing even though it is stored alongside
-- student identity for manager dashboards; never grant it to State readers.
GRANT SELECT (id, school_id, national_student_id, roll_number, current_class_id,
              first_name, last_name, date_of_birth, gender, guardian_name,
              guardian_relationship, guardian_phone, guardian_email,
              emergency_contact_phone, physical_address, enrollment_date,
              is_active, created_at)
ON students TO state_readonly;
GRANT SELECT (id, school_id, email, role, first_name, last_name, staff_identifier,
              phone, qualifications, designation, bio, is_active, created_at)
ON users TO state_readonly;

-- 🔒 ZERO grants on the financial tier for state_readonly.
--    (Deliberately absent: tuition_rates, student_invoices, payment_transactions.)

-- The tenant application role may write academic + financial data (RLS scopes it).
GRANT SELECT, INSERT, UPDATE, DELETE ON private_schools, academic_years, users,
    school_roll_sequences, school_classes, students, subjects, teaching_assignments,
    student_grades, exam_submission_events,
    live_attendance, daily_submission_logs, communication_logs,
    tuition_rates, student_invoices, payment_transactions
TO school_app;
-- Audit records are append-only operational evidence; tenant DB sessions may
-- write their own guard outcomes but cannot browse another tenant's audit data.
GRANT INSERT ON security_audit_log TO school_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO school_app;

-- ---------------------------------------------------------------------------
-- 4. IMMUTABILITY GUARDS
-- ---------------------------------------------------------------------------

-- 4a. exam_submission_events: an immutable, append-only audit trail.
CREATE OR REPLACE FUNCTION enforce_exam_event_immutability() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'exam_submission_events are IMMUTABLE: % is blocked on row %',
        TG_OP, OLD.id;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_exam_event_immutable ON exam_submission_events;
CREATE TRIGGER trg_exam_event_immutable
    BEFORE UPDATE OR DELETE ON exam_submission_events
    FOR EACH ROW EXECUTE FUNCTION enforce_exam_event_immutability();

-- 4b. national_student_id: assigned at registration, never rewritten.
CREATE OR REPLACE FUNCTION enforce_student_id_immutability() RETURNS trigger AS $$
BEGIN
    IF NEW.national_student_id <> OLD.national_student_id THEN
        RAISE EXCEPTION 'national_student_id % is IMMUTABLE and cannot be changed to %',
            OLD.national_student_id, NEW.national_student_id;
    END IF;
    IF NEW.roll_number <> OLD.roll_number THEN
        RAISE EXCEPTION 'roll_number % is IMMUTABLE and cannot be changed to %',
            OLD.roll_number, NEW.roll_number;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_student_id_immutable ON students;
CREATE TRIGGER trg_student_id_immutable
    BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION enforce_student_id_immutability();

-- 4c. A school code is the immutable prefix of issued rolls. State Admins may
--     correct it before the first enrollment, never after any roll exists.
CREATE OR REPLACE FUNCTION enforce_school_code_after_enrollment() RETURNS trigger AS $$
BEGIN
    IF NEW.school_code <> OLD.school_code
       AND EXISTS (SELECT 1 FROM students WHERE school_id = OLD.id) THEN
        RAISE EXCEPTION 'school_code % cannot change after roll numbers have been issued', OLD.school_code;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_school_code_after_enrollment ON private_schools;
CREATE TRIGGER trg_school_code_after_enrollment
    BEFORE UPDATE OF school_code ON private_schools
    FOR EACH ROW EXECUTE FUNCTION enforce_school_code_after_enrollment();

-- 4d. Published exam marks cannot be silently reverted to draft
--     (un-publication would corrupt state analytics history).
CREATE OR REPLACE FUNCTION enforce_publication_irreversibility() RETURNS trigger AS $$
BEGIN
    IF OLD.is_published = TRUE AND NEW.is_published = FALSE THEN
        RAISE EXCEPTION 'Published exam marks cannot be recalled to private draft (grade %)', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_grade_publication_irreversible ON student_grades;
CREATE TRIGGER trg_grade_publication_irreversible
    BEFORE UPDATE ON student_grades
    FOR EACH ROW EXECUTE FUNCTION enforce_publication_irreversibility();

COMMIT;
