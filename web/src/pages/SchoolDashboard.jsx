import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
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
import { selectIsManager } from '../features/auth/authSlice';
import { selectBlocks } from '../features/design/designSlice';

const FEE_COLOURS = {
  PAID: '#1e8449',
  PENDING: '#e08e0b',
  NOT_PAID: '#c0392b',
  SCHOLARSHIP: '#2e86de',
};

export default function SchoolDashboard() {
  const dispatch = useDispatch();
  const kpis = useSelector(selectKpis);
  const tuition = useSelector(selectTuition);
  const performance = useSelector(selectPerformance);
  const trend = useSelector(selectAttendanceTrend);
  const isManager = useSelector(selectIsManager);
  const blocks = useSelector(selectBlocks);

  useEffect(() => {
    dispatch(fetchKpis());
    dispatch(fetchPerformance());
    dispatch(fetchAttendanceTrend({ days: 14 }));
    if (isManager) dispatch(fetchTuitionStatus());
  }, [dispatch, isManager]);

  const distribution = performance?.distribution ?? [];
  const bySubject = performance?.by_subject ?? [];

  return (
    <div className="stack">
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

      <div className="grid grid--2">
        {blocks.attendanceSummary !== false && (
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

        {blocks.academicOverview !== false && (
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
        {blocks.academicOverview !== false && (
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
