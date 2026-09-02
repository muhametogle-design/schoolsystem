-- ============================================================================
-- MODULE REFINEMENTS — PostgreSQL 16 migration (applies after 001-004)
--
-- 1. Editable syllabus tracker : syllabus_topics + department-head authority
-- 2. Teacher authentication    : staff PIN credential column
-- 3. Subject-restricted roster : subject_attendance (per subject + period)
--
-- Execute as the database owner:
--   psql -v ON_ERROR_STOP=1 -f sql/005_module_refinements.sql
-- ============================================================================

BEGIN;

-- Refinement 2: Staff ID + PIN login (Argon2 hash, mirrors password_hash).
ALTER TABLE users ADD COLUMN IF NOT EXISTS staff_pin_hash VARCHAR(255);

-- Refinement 1: department heads are teaching staff with syllabus authority.
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_department_head BOOLEAN NOT NULL DEFAULT FALSE;

-- Refinement 1: national-curriculum units per syllabus plan; the
-- "Log Topic Covered" modal ticks these and checkpoints are derived.
CREATE TABLE syllabus_topics (
    id SERIAL PRIMARY KEY,
    plan_id INT NOT NULL REFERENCES syllabus_plans(id) ON DELETE CASCADE,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    position INT NOT NULL DEFAULT 0,
    code VARCHAR(30),
    title VARCHAR(255) NOT NULL,
    is_done BOOLEAN NOT NULL DEFAULT FALSE,
    done_date DATE,
    done_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_syllabus_topics_plan ON syllabus_topics(plan_id, position);

-- Refinement 3: per subject+period attendance. The daily class roster
-- (live_attendance) remains the compliance source of truth; this table holds
-- the finer subject-period marking with strict uniqueness per slot.
CREATE TABLE subject_attendance (
    id SERIAL PRIMARY KEY,
    school_id INT NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    period_number INT NOT NULL,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('Present', 'Absent', 'Late', 'Excused')),
    recorded_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subject_attendance_slot UNIQUE (student_id, date, subject_id, period_number)
);
CREATE INDEX IF NOT EXISTS idx_subject_attendance_slot
    ON subject_attendance(school_id, date, subject_id, period_number);

COMMIT;
