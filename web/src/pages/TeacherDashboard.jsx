import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { api } from '../api/client';
import Badge from '../components/Badge';
import PeriodRoster from '../components/PeriodRoster';
import { selectUser } from '../features/auth/authSlice';

/**
 * Restricted Teacher Dashboard.
 *
 * Rendered automatically after a teaching-staff sign-in: the teacher's active
 * subject schedule (only the periods assigned in the timetable matrix) with a
 * quick Mark Present / Absent / Late roster per period. Classes taught by
 * other staff are structurally absent — the API never returns them.
 */
export default function TeacherDashboard() {
  const user = useSelector(selectUser);
  const [schedule, setSchedule] = useState(null);
  const [error, setError] = useState(null);
  const [openPeriod, setOpenPeriod] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api('/api/v1/school/my-schedule')
      .then((data) => !cancelled && setSchedule(data))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const periods = schedule?.periods ?? [];
  const markedAll = periods.length > 0 && periods.every((p) => p.marked_today >= p.student_count && p.student_count > 0);

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">My Teaching Day</h2>
            <span className="card__hint">
              Welcome, {user?.first_name}. Attendance closes at {schedule?.attendance_deadline ?? '12:00'} — you can
              mark only the periods assigned to you.
            </span>
          </div>
          <div className="toolbar">
            <Badge status={markedAll ? 'Present' : 'Pending'}>
              {markedAll ? 'ALL ROSTERS MARKED' : `${periods.filter((p) => p.marked_today > 0).length}/${periods.length} MARKED`}
            </Badge>
            <Link className="btn btn--small" to="/school/attendance">Full attendance sheet</Link>
          </div>
        </header>

        {error && <p className="alert alert--danger">{error}</p>}
        {!schedule && !error && <p className="empty">Loading your timetable…</p>}
        {schedule && periods.length === 0 && (
          <p className="empty">
            No timetable periods are assigned to you yet. Ask your School Manager to add you to the
            teaching schedule.
          </p>
        )}

        <div className="period-grid">
          {periods.map((period) => {
            const key = `${period.class_id}-${period.subject_id}`;
            const isOpen = openPeriod === key;
            return (
              <article key={key} className={`period-card ${isOpen ? 'is-open' : ''}`}>
                <header className="period-card__head">
                  <div>
                    <h3 className="period-card__class">{period.class_label}</h3>
                    <span className="period-card__subject">{period.subject_name}</span>
                  </div>
                  <div className="period-card__meta">
                    {period.room_number && <span className="period-card__room mono">{period.room_number}</span>}
                    <Badge status={period.marked_today > 0 ? 'Present' : 'Pending'}>
                      {period.marked_today > 0 ? `${period.marked_today}/${period.student_count} marked` : 'Not marked'}
                    </Badge>
                  </div>
                </header>
                <div className="period-card__foot">
                  <span className="period-card__count">{period.student_count} students</span>
                  <button
                    type="button"
                    className={`btn btn--small ${isOpen ? '' : 'btn--primary'}`}
                    onClick={() => setOpenPeriod(isOpen ? null : key)}
                  >
                    {isOpen ? 'Close roster' : 'Mark attendance'}
                  </button>
                </div>
                {isOpen && (
                  <PeriodRoster
                    classId={period.class_id}
                    classLevel={period.class_label}
                    onSaved={() => setRefreshKey((k) => k + 1)}
                  />
                )}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
