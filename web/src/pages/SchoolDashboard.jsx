import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import Badge from '../components/Badge';
import { BarList, KpiCard, StackedBar, TrendChart } from '../components/Charts';
import {
  fetchKpis,
  fetchPerformance,
  fetchTuitionStatus,
  selectKpis,
  selectPerformance,
  selectTuition,
} from '../features/schools/schoolSlice';
import { fetchAttendanceTrend, selectAttendanceTrend } from '../features/attendance/attendanceSlice';
import { fetchBiometricOverview } from '../features/biometrics/biometricsSlice';
import { selectIsManager, selectUser } from '../features/auth/authSlice';
import { selectBlocks } from '../features/design/designSlice';
import { api } from '../api/client';

const FEE_COLOURS = {
  PAID: '#1e8449',
  PENDING: '#e08e0b',
  NOT_PAID: '#c0392b',
  SCHOLARSHIP: '#2e86de',
};

/**
 * Tenant dashboard. Refinement 7 wraps the four headline blocks — Profile
 * Card, Academic Overview, Attendance Summary and the Biometrics Badge — in
 * the design system's visibility toggles, so the Design & Layout drawer can
 * show/hide each in real time without a page reload.
 */
export default function SchoolDashboard() {
  const dispatch = useDispatch();
  const user = useSelector(selectUser);
  const kpis = useSelector(selectKpis);
  const tuition = useSelector(selectTuition);
  const performance = useSelector(selectPerformance);
  const trend = useSelector(selectAttendanceTrend);
  const bioCounts = useSelector((state) => state.biometrics.counts);
  const isManager = useSelector(selectIsManager);
  const blocks = useSelector(selectBlocks);

  const showProfile = blocks.profileCard !== false;
  const showAcademics = blocks.academicOverview !== false;
  const showAttendance = blocks.attendanceSummary !== false;
  const showBiometrics = blocks.biometricsBadge !== false;

  const [profile, setProfile] = useState(null);

  useEffect(() => {
    dispatch(fetchKpis());
    dispatch(fetchPerformance());
    dispatch(fetchAttendanceTrend({ days: 14 }));
    if (isManager) dispatch(fetchTuitionStatus());
  }, [dispatch, isManager]);

  useEffect(() => {
    if (!showBiometrics) return;
    dispatch(fetchBiometricOverview({ limit: 400 }));
  }, [dispatch, showBiometrics]);

  useEffect(() => {
    if (!showProfile || !isManager) return undefined;
    let alive = true;
    api('/api/v1/school/profile')
      .then((data) => {
        if (alive) setProfile(data);
      })
      .catch(() => { /* the card falls back to session identity */ });
    return () => {
      alive = false;
    };
  }, [showProfile, isManager]);

  const distribution = performance?.distribution ?? [];
  const bySubject = performance?.by_subject ?? [];

  const enrolledShare =
    bioCounts?.students_total > 0
      ? Math.round((bioCounts.students_enrolled / bioCounts.students_total) * 100)
      : null;

  return (
    <div className="stack">
      {/* ------------------------- Block: Profile Card ------------------------ */}
      {showProfile && (
        <section className="card profile-card" aria-label="School profile snapshot">
          <div className="profile-card__crest" aria-hidden="true">
            {(profile?.school_code ?? user?.school_name ?? 'S').slice(0, 2)}
          </div>
          <div className="profile-card__body">
            <h2 className="card__title">{profile?.school_name ?? user?.school_name ?? 'School'}</h2>
            <p className="profile-card__meta">
              {profile?.school_code && <span className="mono">Code {profile.school_code}</span>}
              {profile?.state_license_number && <span className="mono">Licence {profile.state_license_number}</span>}
              {profile?.proprietor_name && <span>Proprietor · {profile.proprietor_name}</span>}
            </p>
          </div>
          <div className="profile-card__side">
            <Badge status="Active">{profile?.accreditation_status ?? 'Active'}</Badge>
            <span className="profile-card__stat">
              <strong>{kpis?.total_students ?? '—'}</strong> students · Classes 1–12
            </span>
          </div>
        </section>
      )}

      <section className="kpi-grid">
        <KpiCard
          label="Active Students"
          value={kpis?.total_students ?? '—'}
          hint="Enrolled across Class 1–12"
          tone="brand"
        />
        <KpiCard
          label="Season Attendance"
          value={kpis?.attendance?.attendance_pct != null ? `${kpis.attendance.attendance_pct}%` : '—'}
          hint={`${kpis?.attendance?.days_recorded ?? 0} roster days recorded`}
          tone={(kpis?.attendance?.attendance_pct ?? 0) >= 85 ? 'ok' : 'warn'}
        />
        <KpiCard
          label="Average Score"
          value={kpis?.average_score != null ? `${kpis.average_score}` : '—'}
          hint="All recorded assessments"
          tone="info"
        />
        {isManager && (
          <KpiCard
            label="Fee Collection"
            value={
              tuition?.collection_matrix?.collection_rate_pct != null
                ? `${tuition.collection_matrix.collection_rate_pct}%`
                : '—'
            }
            hint={
              tuition?.collection_matrix
                ? `${tuition.collection_matrix.collected.toLocaleString()} of ${tuition.collection_matrix.invoiced.toLocaleString()}`
                : 'Billing ledger'
            }
            tone="ok"
          />
        )}
      </section>

      {/* ----------------------- Block: Biometrics Badge ---------------------- */}
      {showBiometrics && (
        <section className="card biometrics-badge-card" aria-label="Biometric enrolment status">
          <div className="biometrics-badge-card__icon" aria-hidden="true">◉</div>
          <div className="biometrics-badge-card__body">
            <h2 className="card__title">Biometric verification</h2>
            <p className="profile-card__meta">
              <span>{bioCounts?.credentials_active ?? '—'} active credentials</span>
              <span>
                {bioCounts?.students_enrolled ?? '—'}/{bioCounts?.students_total ?? '—'} students
                {enrolledShare != null ? ` (${enrolledShare}%)` : ''} enrolled
              </span>
              <span>{bioCounts?.staff_enrolled ?? '—'}/{bioCounts?.staff_total ?? '—'} staff enrolled</span>
            </p>
          </div>
          <div className="profile-card__side">
            <Badge tone={bioCounts?.verifications_today?.failed ? 'warn' : 'ok'}>
              {bioCounts?.verifications_today?.success ?? 0} scans today
            </Badge>
            <Link className="link-button" to="/school/biometrics">Open biometric console</Link>
          </div>
        </section>
      )}

      <div className="grid grid--2">
        {/* ---------------------- Block: Attendance Summary -------------------- */}
        {showAttendance && (
          <section className="card">
            <header className="card__head">
              <h2 className="card__title">Attendance Trend</h2>
              <span className="card__hint">Daily percentage, last 14 days</span>
            </header>
            <TrendChart
              points={trend.map((t) => ({
                label: t.date.slice(5),
                value: t.attendance_pct ?? 0,
              }))}
            />
          </section>
        )}

        {/* ---------------------- Block: Academic Overview -------------------- */}
        {showAcademics && (
          <section className="card">
            <header className="card__head">
              <h2 className="card__title">Academic Performance</h2>
              <span className="card__hint">Grade distribution across {performance?.records ?? 0} records</span>
            </header>
            <BarList
              items={distribution.map((d) => ({
                label: d.band,
                value: d.students,
                colour: d.colour,
              }))}
              unit=""
            />
          </section>
        )}
      </div>

      <div className="grid grid--2">
        {showAcademics && (
          <section className="card">
            <header className="card__head">
              <h2 className="card__title">Subject Averages</h2>
              <span className="card__hint">Mean score by subject</span>
            </header>
            <BarList
              items={bySubject.map((s) => ({
                label: s.subject,
                value: s.average_score,
              }))}
              max={100}
            />
          </section>
        )}

        <section className="card">
          <header className="card__head">
            <h2 className="card__title">Tuition Status Breakdown</h2>
            <span className="card__hint">Students by fee standing</span>
          </header>

          {!isManager && (
            <p className="alert alert--muted">
              Fee standing is visible to school administrators only.
            </p>
          )}

          {isManager && tuition?.restricted && (
            <p className="alert alert--muted">{tuition.reason}</p>
          )}

          {isManager && tuition?.breakdown && (
            <>
              <StackedBar
                segments={tuition.breakdown.map((b) => ({
                  label: b.status.replace(/_/g, ' '),
                  value: b.students,
                  colour: FEE_COLOURS[b.status] ?? '#7f8c8d',
                }))}
                total={tuition.total_students}
              />
              <ul className="status-rows">
                {tuition.breakdown.map((b) => (
                  <li key={b.status}>
                    <Badge status={b.status}>{b.status.replace(/_/g, ' ')}</Badge>
                    <span className="status-rows__count">{b.students} students</span>
                    <span className="status-rows__pct">{b.share_pct}%</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
