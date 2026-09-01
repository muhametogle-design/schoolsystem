import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import { selectUser } from '../features/auth/authSlice';
import {
  clearRoster,
  dismissNotice,
  fetchMyRoster,
  fetchMySchedule,
  saveMyRoster,
} from '../features/teacherPortal/teacherPortalSlice';

const todayISO = () => new Date().toISOString().slice(0, 10);
const QUICK_STATUSES = ['Present', 'Absent', 'Late', 'Excused'];

/**
 * Refinement 2 + 3 — restricted Teacher Dashboard ("My teaching day").
 *
 * Upon login teachers land here: their own subject schedule for today with
 * the active period highlighted, and one-tap Present/Absent/Late rosters for
 * each of THEIR periods. The backend enforces slot ownership, so any attempt
 * to open another teacher's register is refused.
 */
export default function TeacherDashboard() {
  const dispatch = useDispatch();
  const user = useSelector(selectUser);
  const {
    teacher,
    slots,
    activePeriod,
    date,
    pendingSlots,
    roster,
    busy,
    error,
    notice,
    status,
  } = useSelector((state) => state.teacherPortal);

  const [selectedDate, setSelectedDate] = useState(todayISO());

  useEffect(() => {
    dispatch(fetchMySchedule({ date: selectedDate }));
  }, [dispatch, selectedDate]);

  useEffect(() => {
    if (!notice && !error) return;
    const timer = setTimeout(() => dispatch(dismissNotice()), 4500);
    return () => clearTimeout(timer);
  }, [notice, error, dispatch]);

  const openRoster = (slot) => {
    dispatch(
      fetchMyRoster({
        date: selectedDate,
        classId: slot.class_id,
        subjectId: slot.subject_id,
        periodNumber: slot.period_number,
      })
    );
  };

  const activeSlots = slots.filter((s) => s.is_active_period);

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h2>My teaching day</h2>
          <p className="muted">
            {teacher?.name}
            {teacher?.staff_identifier ? (
              <> · <span className="mono">{teacher.staff_identifier}</span></>
            ) : null}
            {teacher?.is_department_head ? ' · Department Head' : ''} — marking is restricted to
            your assigned subjects and periods.
          </p>
        </div>
        <label className="field">
          <span>Date</span>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value || todayISO())}
          />
        </label>
      </header>

      {error && (
        <p className="alert alert--danger" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="alert alert--ok" role="status">
          {notice}
        </p>
      )}

      <div className="kpi-grid">
        <KpiCard label="Periods today" value={slots.length} tone="neutral" />
        <KpiCard
          label="Active period"
          value={activePeriod ? `Period ${activePeriod}` : 'Free'}
          hint={activePeriod ? 'Mark the roster now' : 'Outside scheduled periods'}
          tone={activePeriod ? 'info' : 'neutral'}
        />
        <KpiCard
          label="Registers pending"
          value={pendingSlots}
          tone={pendingSlots > 0 ? 'warn' : 'ok'}
        />
        <KpiCard
          label="Registers done"
          value={slots.length - pendingSlots}
          tone="ok"
        />
      </div>

      {activeSlots.length > 0 && (
        <div className="card active-period-card">
          <h3>Active now</h3>
          {activeSlots.map((slot) => (
            <div key={slot.slot_id} className="active-period-row">
              <div>
                <strong>{slot.period_label}</strong>
                <span className="muted"> · {slot.class_label} · {slot.subject_name}</span>
              </div>
              <div className="btn-row">
                <Badge tone={slot.marked_complete ? 'ok' : 'warn'}>
                  {slot.marked_complete ? 'MARKED' : `${slot.marked_count}/${slot.roster_size} MARKED`}
                </Badge>
                <button type="button" className="btn btn--primary btn--sm" onClick={() => openRoster(slot)}>
                  Quick roster
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h3>Subject schedule — {date}</h3>
        {status === 'loading' && slots.length === 0 ? (
          <p className="empty">Loading…</p>
        ) : slots.length === 0 ? (
          <p className="empty">
            No periods scheduled for this date — enjoy the preparation time.
          </p>
        ) : (
          <ol className="day-timeline">
            {slots.map((slot) => (
              <li
                key={slot.slot_id}
                className={`day-slot ${slot.is_active_period ? 'is-active-period' : ''}`}
              >
                <span className="day-slot__period mono">{slot.period_label}</span>
                <div className="day-slot__body">
                  <strong>{slot.subject_name}</strong>
                  <span className="muted">{slot.class_label}</span>
                </div>
                <div className="day-slot__side">
                  <Badge tone={slot.marked_complete ? 'ok' : 'muted'}>
                    {slot.marked_complete ? 'DONE' : `${slot.marked_count}/${slot.roster_size}`}
                  </Badge>
                  <button
                    type="button"
                    className="btn btn--sm btn--ghost"
                    onClick={() => openRoster(slot)}
                  >
                    Mark
                  </button>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      {roster && (
        <RosterSheet
          roster={roster}
          busy={busy}
          onSave={(entries) =>
            dispatch(
              saveMyRoster({
                class_id: roster.class_id,
                subject_id: roster.subject_id,
                period_number: roster.period_number,
                date: roster.date,
                entries,
              })
            ).then(() => dispatch(fetchMySchedule({ date: selectedDate })))
          }
          onClose={() => dispatch(clearRoster())}
          signedInAs={user?.first_name}
        />
      )}
    </section>
  );
}

function RosterSheet({ roster, busy, onSave, onClose, signedInAs }) {
  const [statuses, setStatuses] = useState(() =>
    Object.fromEntries(roster.students.map((s) => [s.student_id, s.status ?? '']))
  );

  const setAll = (value) =>
    setStatuses(Object.fromEntries(roster.students.map((s) => [s.student_id, value])));

  const entries = roster.students
    .filter((s) => statuses[s.student_id])
    .map((s) => ({ student_id: Number(s.student_id), status: statuses[s.student_id] }));

  return (
    <div className="card roster-sheet">
      <header className="page-head">
        <div>
          <h3>
            {roster.class_label} · {roster.subject_name} · Period {roster.period_number}
          </h3>
          <p className="muted">
            {roster.date} — {roster.students.length} student(s). Marks save against this subject
            period only.
          </p>
        </div>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onClose}>
          Close
        </button>
      </header>

      <div className="btn-row">
        <button type="button" className="btn btn--sm btn--ghost" onClick={() => setAll('Present')}>
          All present
        </button>
        <button type="button" className="btn btn--sm btn--ghost" onClick={() => setAll('')}>
          Clear
        </button>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Roll</th>
              <th>Student</th>
              <th>Mark</th>
            </tr>
          </thead>
          <tbody>
            {roster.students.map((student) => (
              <tr key={student.student_id}>
                <td className="mono">{student.roll_number}</td>
                <td>{student.name}</td>
                <td>
                  <div className="mark-row" role="group" aria-label={`Mark ${student.name}`}>
                    {QUICK_STATUSES.map((value) => (
                      <button
                        key={value}
                        type="button"
                        className={`mark-btn mark-btn--${value.toLowerCase()} ${
                          statuses[student.student_id] === value ? 'is-selected' : ''
                        }`}
                        onClick={() =>
                          setStatuses((prev) => ({
                            ...prev,
                            [student.student_id]: prev[student.student_id] === value ? '' : value,
                          }))
                        }
                      >
                        {value === 'Present' ? 'P' : value === 'Absent' ? 'A' : value === 'Late' ? 'L' : 'E'}
                        <span className="mark-btn__label">{value}</span>
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer className="roster-sheet__foot">
        <span className="muted">
          {entries.length}/{roster.students.length} marked
        </span>
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy || entries.length === 0}
          onClick={() => onSave(entries)}
        >
          {busy ? 'Saving…' : 'Save register'}
        </button>
      </footer>
    </div>
  );
}
