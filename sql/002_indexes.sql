-- ============================================================================
-- NE-EMIS Phase 2 & 4 read-optimization indexes.
-- Run after 001_schema.sql. Indexes are intentionally aligned with:
--   * campus-dean summary queries (Phase 2 review)
--   * overnight batch queries (Phase 3)
--   * state KPI / vacancy / payout queries (Phase 4)
-- ============================================================================

BEGIN;

-- Students ----------------------------------------------------------------
CREATE INDEX idx_students_campus_name ON public.students (campus_id, last_name, first_name);
CREATE INDEX idx_students_national_id ON public.students (national_id_hash) WHERE national_id_hash IS NOT NULL;
CREATE INDEX idx_students_status ON public.students (campus_id, status);
CREATE INDEX idx_students_enrollment_kind ON public.students (campus_id, enrollment_kind);

-- Mobility / transfer tree -------------------------------------------------
CREATE INDEX idx_mobility_student ON public.student_mobility (student_id, effective_on DESC);
CREATE INDEX idx_mobility_prev ON public.student_mobility (previous_mobility_id);
CREATE INDEX idx_mobility_campus ON public.student_mobility (campus_id, transfer_state);

-- Enrollments ---------------------------------------------------------------
CREATE INDEX idx_enroll_student_active ON public.enrollments (student_id) WHERE status = 'active';
CREATE INDEX idx_enroll_year ON public.enrollments (campus_id, academic_year_id);

-- Course sections (NE-CID composite) ---------------------------------------
CREATE INDEX idx_course_section_campus_term
  ON public.course_sections (campus_id, academic_year_id, term_id, is_active);
CREATE INDEX idx_course_section_teacher
  ON public.course_sections (teacher_id) WHERE teacher_id IS NOT NULL;

-- Attendance -----------------------------------------------------------------
CREATE INDEX idx_attendance_campus_page ON public.attendance (campus_id, attendance_date, status);
CREATE INDEX idx_attendance_truant ON public.attendance (student_id, status) WHERE status = 'truant';

-- Exams & transcripts --------------------------------------------------------
CREATE INDEX idx_exams_section ON public.exam_sheets (course_section_id, campus_id);
CREATE INDEX idx_transcripts_student_term ON public.transcripts (student_id, academic_year_id DESC, term_id DESC);

-- Teachers -------------------------------------------------------------------
CREATE INDEX idx_teachers_campus_status ON public.teachers (campus_id, employment_state);
CREATE INDEX idx_teachers_ids ON public.teachers (national_id_hash) WHERE national_id_hash IS NOT NULL;
CREATE INDEX idx_assignments_load ON public.teacher_assignments (campus_id, weekly_contact_hours);

-- Payroll --------------------------------------------------------------------
CREATE INDEX idx_payroll_period_status ON public.payroll_entries (campus_id, pay_period, status);
CREATE INDEX idx_payroll_tier ON public.teacher_payroll_profiles (grade_tier);
CREATE INDEX idx_cert_renewal ON public.teacher_certifications (next_renewal) WHERE status = 'active';

-- Record locks / Phase 2 ------------------------------------------------------
CREATE INDEX idx_record_locks_campus ON public.record_locks (campus_id, locked_at DESC);
CREATE INDEX idx_pending_locks_campus ON public.pending_locks (campus_id, locked_at DESC);

-- Aggregation / Phase 3 -------------------------------------------------------
CREATE INDEX idx_ingest_phase ON public.ingestion_jobs (phase, campus_id, created_at);
CREATE INDEX idx_agg_batches_date ON public.aggregation_batches (batch_date, batch_state);

-- Central / Phase 4 -----------------------------------------------------------
CREATE INDEX idx_central_student_campus ON central.student_registry (current_campus_id, status);
CREATE INDEX idx_central_teacher_campus ON central.teacher_registry (current_campus_id, status);
CREATE INDEX idx_funding_period ON central.funding_payouts (period, funding_kind, status);
CREATE INDEX idx_kpi_rollup ON central.kpi_rollups (campus_id, period_start DESC);

-- JSONB search paths ----------------------------------------------------------
CREATE INDEX idx_mobility_history_gin ON central.student_registry USING gin (schooling_history jsonb_path_ops);
CREATE INDEX idx_schedule_gin ON public.course_sections USING gin (schedule_json jsonb_path_ops);
CREATE INDEX idx_kpi_metrics_gin ON central.kpi_rollups USING gin (metrics jsonb_path_ops);

COMMIT;
