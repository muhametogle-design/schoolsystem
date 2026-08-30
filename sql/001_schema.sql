-- ============================================================================
-- PRIVATE SCHOOL MANAGEMENT & STATE COMPLIANCE MONITORING SYSTEM
-- Monolithic Database Schema — PostgreSQL 16
--
-- IMPLEMENTATION PHASE 1
--
-- Multi-tenant SaaS: every tenant table is logically isolated via school_id.
-- The State Government (super-admin) has absolute READ-ONLY visibility into
-- academic operations (students, attendance, PUBLISHED exam marks) for
-- Class 1 - Class 12, and ZERO visibility into private financial data
-- (see 002_security_firewall.sql for the hard financial firewall).
--
-- Execute as the database owner:
--   psql -v ON_ERROR_STOP=1 -f sql/001_schema.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- GLOBAL PLATFORM CONFIGURATION & STATE ACCREDITATION CORE
-- ============================================================================

CREATE TABLE private_schools (
    id SERIAL PRIMARY KEY,
    state_license_number VARCHAR(100) UNIQUE NOT NULL,
    school_code VARCHAR(2) UNIQUE NOT NULL, -- used in roll numbers, e.g. NG-10023
    school_name VARCHAR(255) NOT NULL,
    proprietor_name VARCHAR(255),
    contact_phone VARCHAR(50),
    contact_email VARCHAR(255),
    physical_address TEXT,
    accreditation_status VARCHAR(50) DEFAULT 'Active', -- Active, Probation, Suspended
    -- Tenant-private billing contacts: never granted to state_readonly.
    billing_contact_name VARCHAR(255),
    billing_phone VARCHAR(50),
    billing_email VARCHAR(255),
    billing_address TEXT,
    billing_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_school_code CHECK (school_code ~ '^[A-Z]{2}$'),
    CONSTRAINT chk_accreditation_status CHECK (accreditation_status IN ('Active', 'Probation', 'Suspended'))
);

-- Per-tenant monotonically increasing roll number allocator. The State Admin
-- controls next_value; student registration advances it transactionally.
CREATE TABLE school_roll_sequences (
    school_id INT PRIMARY KEY REFERENCES private_schools(id) ON DELETE CASCADE,
    next_value INT NOT NULL DEFAULT 10000 CHECK (next_value > 0),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE academic_years (
    id SERIAL PRIMARY KEY,
    label VARCHAR(50) NOT NULL,              -- e.g., "2026-2027"
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_current BOOLEAN DEFAULT FALSE
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    school_id INT REFERENCES private_schools(id) ON DELETE CASCADE, -- NULL value indicates a State Gov Admin User
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,               -- state_admin / inspector / school_manager / teacher
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    staff_identifier VARCHAR(30) UNIQUE,
    phone VARCHAR(50),
    qualifications TEXT,
    designation VARCHAR(100),
    bio TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_role CHECK (role IN ('state_admin', 'inspector', 'state_inspector', 'school_manager', 'teacher')),
    -- State roles must never be bound to a school tenant.
    CONSTRAINT chk_state_user_has_no_school CHECK (
        role NOT IN ('state_admin', 'inspector', 'state_inspector') OR school_id IS NULL
    )
);

-- ============================================================================
-- COMPLIANCE TIERS: CLASSES 1-12, GRADES, & STUDENT DATA (FULLY GOVT VISIBLE)
-- ============================================================================

CREATE TABLE school_classes (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_level VARCHAR(50) NOT NULL,
    class_stream VARCHAR(50) NOT NULL,       -- e.g., 'A', 'Blue', 'Gold'
    room_number VARCHAR(50),
    class_teacher_id INT REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_class_level CHECK (class_level IN (
        'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'Class 6',
        'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12'
    )),
    CONSTRAINT uq_class_per_school UNIQUE (school_id, class_level, class_stream)
);

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    national_student_id VARCHAR(30) UNIQUE NOT NULL,  -- compatibility identifier; new rows equal roll_number
    roll_number VARCHAR(30) UNIQUE NOT NULL,          -- e.g. NG-10023, immutable, school-sequential
    current_class_id INT REFERENCES school_classes(id) ON DELETE SET NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(20),
    guardian_name VARCHAR(255),
    guardian_relationship VARCHAR(50),
    guardian_phone VARCHAR(50),
    guardian_email VARCHAR(255),
    emergency_contact_phone VARCHAR(50),
    physical_address TEXT,
    fee_status VARCHAR(20) DEFAULT 'NOT_PAID',
    enrollment_date DATE DEFAULT CURRENT_DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_gender CHECK (gender IN ('Male', 'Female', 'Other') OR gender IS NULL),
    CONSTRAINT chk_fee_status CHECK (fee_status IN ('PAID', 'PENDING', 'NOT_PAID', 'SCHOLARSHIP') OR fee_status IS NULL)
);

CREATE TABLE subjects (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    subject_code VARCHAR(30) NOT NULL,
    subject_name VARCHAR(150) NOT NULL,
    class_level VARCHAR(50) NOT NULL,
    CONSTRAINT chk_subject_class_level CHECK (class_level IN (
        'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'Class 6',
        'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12'
    )),
    CONSTRAINT uq_subject_per_school UNIQUE (school_id, subject_code, class_level)
);

-- Explicit schedule source of truth. A subject is catalogued per class level,
-- while this table maps every stream + subject to its assigned teacher.
CREATE TABLE teaching_assignments (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_id INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_class_subject_assignment UNIQUE (school_id, class_id, subject_id)
);

-- ============================================================================
-- CONTINUOUS ASSESSMENT MARKS + THE EXAM DATA RELEASE VALVE
-- ----------------------------------------------------------------------------
-- student_grades are PRIVATE school drafts until the school administrator
-- hits "Publish Exam Marks to State". Publication:
--   1. flips is_published => TRUE for the released scope,
--   2. writes an IMMUTABLE row into exam_submission_events.
-- Government analytics (View C) only ever aggregate PUBLISHED rows.
-- ============================================================================

CREATE TABLE student_grades (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    academic_year_id INT NOT NULL REFERENCES academic_years(id) ON DELETE RESTRICT,
    exam_name VARCHAR(150) NOT NULL,         -- e.g., 'Term 1 Opener', 'Mid-Term 1'
    numeric_score NUMERIC(5,2) NOT NULL,
    is_published BOOLEAN DEFAULT FALSE,      -- RELEASE VALVE: FALSE = private school draft
    recorded_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_score_range CHECK (numeric_score >= 0 AND numeric_score <= 100),
    CONSTRAINT uq_grade_record UNIQUE (student_id, subject_id, academic_year_id, exam_name)
);

-- Immutable audit trail of every "Publish Exam Marks to State" action.
-- 002_security_firewall.sql installs a trigger that blocks UPDATE/DELETE here.
CREATE TABLE exam_submission_events (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    academic_year_id INT NOT NULL REFERENCES academic_years(id) ON DELETE RESTRICT,
    exam_name VARCHAR(150) NOT NULL,
    records_released INT NOT NULL DEFAULT 0,
    published_by INT NOT NULL REFERENCES users(id),
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- LIVE ATTENDANCE & THE 12:00 PM STATE DEADLINE / 3:00 PM RED ALARM ENGINE
-- ============================================================================

CREATE TABLE live_attendance (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,             -- 'Present', 'Absent', 'Late', 'Excused'
    recorded_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_attendance_status CHECK (status IN ('Present', 'Absent', 'Late', 'Excused')),
    CONSTRAINT uq_attendance_per_day UNIQUE (student_id, date)
);

CREATE TABLE daily_submission_logs (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    log_date DATE NOT NULL,
    attendance_submitted BOOLEAN DEFAULT FALSE,
    attendance_submitted_at TIMESTAMP,
    alarm_triggered BOOLEAN DEFAULT FALSE,
    alarm_raised_at TIMESTAMP,
    CONSTRAINT uq_daily_log UNIQUE (school_id, log_date)  -- required by the 3PM worker UPSERT
);

-- ============================================================================
-- COMMUNICATION GATEWAY (RED ALARM + SYSTEM NOTIFICATION OUTBOX)
-- ============================================================================

CREATE TABLE communication_logs (
    id SERIAL PRIMARY KEY,
    school_id INT REFERENCES private_schools(id) ON DELETE CASCADE,
    recipient_phone VARCHAR(50),
    message_type VARCHAR(50) NOT NULL,       -- 'Red_Alarm', 'System_Notification', 'SMS', 'Email'
    message_content TEXT NOT NULL,
    delivery_status VARCHAR(20) DEFAULT 'Pending',
    timestamp_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_delivery_status CHECK (delivery_status IN ('Pending', 'Sent', 'Delivered', 'Failed'))
);

-- ============================================================================
-- PRIVATE FINANCIAL ERP TIER — 🔒 CRITICAL FIREWALL ZONE 🔒
-- ----------------------------------------------------------------------------
-- Base tuition rates, billing configurations, student ledgers, outstanding
-- balances and transaction payment logs are the PRIVATE property of each
-- tenant school. NO State Government role, query, view, API route or grants
-- may ever touch these tables. 002_security_firewall.sql revokes every path.
-- ============================================================================

CREATE TABLE tuition_rates (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_level VARCHAR(50) NOT NULL,
    base_tuition_amount NUMERIC(12,2) NOT NULL,
    billing_cycle VARCHAR(30) DEFAULT 'Termly',  -- 'Termly', 'Monthly', 'Annual'
    effective_date DATE DEFAULT CURRENT_DATE,
    CONSTRAINT chk_tuition_class_level CHECK (class_level IN (
        'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'Class 6',
        'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12'
    )),
    CONSTRAINT chk_billing_cycle CHECK (billing_cycle IN ('Termly', 'Monthly', 'Annual')),
    CONSTRAINT uq_tuition_rate UNIQUE (school_id, class_level, billing_cycle)
);

CREATE TABLE student_invoices (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    academic_year_id INT REFERENCES academic_years(id) ON DELETE SET NULL,
    description VARCHAR(255) NOT NULL,
    amount_due NUMERIC(12,2) NOT NULL CHECK (amount_due >= 0),
    amount_paid NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
    due_date DATE,
    status VARCHAR(30) DEFAULT 'NOT_PAID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_invoice_status CHECK (status IN (
        'PAID', 'PENDING', 'NOT_PAID', 'SCHOLARSHIP',
        'Outstanding', 'Partially_Paid', 'Settled', 'Overdue', 'Paid', 'Partially Paid', 'Void'
    ))
);

CREATE TABLE payment_transactions (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    invoice_id INT NOT NULL REFERENCES student_invoices(id) ON DELETE CASCADE,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    payment_method VARCHAR(50) NOT NULL,     -- 'Cash', 'Bank_Transfer', 'Mobile_Money', 'Card'
    reference_number VARCHAR(100),
    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    received_by INT REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_payment_method CHECK (payment_method IN ('Cash', 'Bank_Transfer', 'Mobile_Money', 'Card'))
);

-- ============================================================================
-- SECURITY AUDIT TRAIL — records every blocked firewall violation attempt
-- ============================================================================

CREATE TABLE security_audit_log (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    role VARCHAR(50),
    endpoint VARCHAR(255),
    verdict VARCHAR(30) NOT NULL,            -- 'BLOCKED', 'ALLOWED'
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PERFORMANCE SEARCH OPTIMIZATION INDEXES
-- ============================================================================

CREATE INDEX idx_student_search_national_id ON students(national_student_id);
CREATE INDEX idx_student_search_roll_number ON students(roll_number);
CREATE INDEX idx_student_names ON students(last_name, first_name);
CREATE INDEX idx_grades_lookup ON student_grades(school_id, class_id, subject_id);
CREATE INDEX idx_attendance_compliance ON live_attendance(date, school_id);
CREATE INDEX idx_compliance_tracker ON daily_submission_logs(log_date, alarm_triggered);

-- Supporting indexes for the hot paths of Phases 2 & 3
CREATE INDEX idx_grades_publication_valve ON student_grades(is_published, school_id);
CREATE INDEX idx_exam_events_school ON exam_submission_events(school_id, published_at DESC);
CREATE INDEX idx_comm_logs_type ON communication_logs(message_type, timestamp_sent DESC);
CREATE INDEX idx_tenant_users ON users(school_id, role);
CREATE INDEX idx_teaching_assignments_teacher ON teaching_assignments(school_id, teacher_id);
CREATE INDEX idx_teaching_assignments_class ON teaching_assignments(school_id, class_id);
CREATE INDEX idx_invoices_ledger ON student_invoices(school_id, status);

COMMIT;
