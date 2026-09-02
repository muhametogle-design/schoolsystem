import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import { selectUser } from '../features/auth/authSlice';
import {
  autoAssign,
  cancelAbsence,
  clearPanel,
  confirmSubstitution,
  fetchAbsences,
  fetchRecommendations,
  fetchTimetable,
  logAbsence,
  selectAbsencePanel,
} from '../features/absences/absenceSlice';
import { useDataSaver } from '../hooks/useDataSaver';

const todayISO = () => new Date().toISOString().slice(0, 10);

const PERIOD_LABELS = {
  1: 'Period 1 · 08:00',
  2: 'Period 2 · 09:00',
  3: 'Period 3 · 10:30',
  4: 'Period 4 · 11:30',
  5: 'Period 5 · 13:00',
  6: 'Period 6 · 14:00',
  7: 'Period 7 · 15:00',
  8: 'Period 8 · 16:00',
};

/**
 * Module 1 — Teacher Absence & Substitution Engine.
 *
 * Logging an absence immediately arms the coverage recommendation panel: each
 * affected timetable slot is listed with ranked substitutes (department
 * qualifications + subject specialization + free period slots), one click to
 * confirm or auto-cover everything.
 */
export default function Substitutions() {
  const dispatch = useDispatch();
  const user = useSelector(selectUser);
  const panel = useSelector(selectAbsencePanel);
  const { list, timetable, busy, error, notice } = useSelector((state) => state.absences);
  const saver = useDataSaver();
  const isManager = user?.role === 'school_manager';

  const [teacherId, setTeacherId] = useState('');
  const [date, setDate] = useState(todayISO());
  const [reason, setReason] = useState('');

  useEffect(() => {
    dispatch(fetchAbsences());
    dispatch(fetchTimetable({}));
  }, [dispatch]);

  const teachers = useMemo(() => {
    const seen = new Map();
    timetable.forEach((slot) => {
      if (!seen.has(slot.teacher_id)) {
        seen.set(slot.teacher_id, { id: slot.teacher_id, name: slot.teacher_name });
      }
    });
    return [...seen.values()].sort((a, b) => String(a.name).localeCompare(String(b.name)));
  }, [timetable]);

  const todaysCover = useMemo(
    () =>
      list
        .filter((a) => a.absence_date === todayISO())
        .flatMap((a) => a.substitutions.map((s) => ({ ...s, teacher_name: a.teacher_name, absence_status: a.status }))),
    [list]
  );

  const onSubmit = async (event) => {
    event.preventDefault();
    if (!teacherId) return;
    const result = await dispatch(logAbsence({ teacherId: Number(teacherId), date, reason }));
    if (logAbsence.fulfilled.match(result)) {
      setReason('');
      dispatch(fetchAbsences());
    }
  };

  const refresh = () => panel && dispatch(fetchRecommendations(panel.absence_id));

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h2>Substitution engine</h2>
          <p className="muted">
            Log a teacher absence — the engine matches available colleagues in real time by
            department qualifications, subject specialization and free period slots.
          </p>
        </div>
        {panel && (
          <button type="button" className="btn btn--ghost" onClick={refresh}>
            Refresh availability
          </button>
        )}
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
        <KpiCard label="Absences logged (recent)" value={list.length} tone="neutral" />
        <KpiCard
          label="Covered today"
          value={todaysCover.filter((s) => s.status !== 'open').length}
          tone="ok"
        />
        <KpiCard
          label="Open slots today"
          value={list
            .filter((a) => a.absence_date === todayISO() && a.status === 'logged')
            .reduce((acc, a) => acc + a.substitutions.filter((s) => s.status === 'open').length, 0)}
          tone={list.some((a) => a.absence_date === todayISO() && a.status === 'logged') ? 'warn' : 'neutral'}
        />
      </div>

      <form className="card card--form" onSubmit={onSubmit}>
        <h3>Log an absence</h3>
        <div className="form-row">
          <label className="field">
            <span>Teacher</span>
            <select value={teacherId} onChange={(e) => setTeacherId(e.target.value)} required>
              <option value="">Select teacher…</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Date</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </label>
          <label className="field field--grow">
            <span>Reason (optional)</span>
            <input
              type="text"
              value={reason}
              maxLength={200}
              placeholder="Medical leave, official duty…"
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <button type="submit" className="btn btn--primary" disabled={busy || !teacherId}>
            {busy ? 'Working…' : 'Log absence'}
          </button>
        </div>
      </form>

      {panel && <CoveragePanel panel={panel} saver={saver} isManager={isManager} dispatch={dispatch} busy={busy} />}

      <div className="card">
        <h3>Today&rsquo;s cover roster</h3>
        {todaysCover.length === 0 ? (
          <p className="empty">No substitutions arranged for today.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Absent teacher</th>
                  <th>Period</th>
                  <th>Class</th>
                  <th>Subject</th>
                  <th>Substitute</th>
                  <th>Status</th>
                  <th>Match</th>
                </tr>
              </thead>
              <tbody>
                {todaysCover.map((s) => (
                  <tr key={s.id}>
                    <td>{s.teacher_name}</td>
                    <td className="mono">{PERIOD_LABELS[s.period_number] ?? `P${s.period_number}`}</td>
                    <td>{s.class_label}</td>
                    <td>{s.subject_name}</td>
                    <td>{s.substitute_name ?? '—'}</td>
                    <td>
                      <Badge status={s.status === 'confirmed' ? 'PUBLISHED' : 'DRAFT'}>
                        {s.status}
                      </Badge>
                    </td>
                    <td className="muted">{s.match_score ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Absence log</h3>
        {list.length === 0 ? (
          <p className="empty">No absences logged yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Teacher</th>
                  <th>Reason</th>
                  <th>Slots covered</th>
                  <th>Status</th>
                  {isManager && <th />}
                </tr>
              </thead>
              <tbody>
                {list.slice(0, 20).map((a) => (
                  <tr key={a.absence_id}>
                    <td className="mono">{a.absence_date}</td>
                    <td>{a.teacher_name}</td>
                    <td className="muted">{a.reason ?? '—'}</td>
                    <td className="mono">
                      {a.substitutions.filter((s) => s.status === 'confirmed').length}/
                      {timetable.filter(
                        (s) =>
                          s.teacher_id === a.teacher_id &&
                          s.day_of_week === new Date(`${a.absence_date}T00:00:00`).getDay() % 7
                      ).length || a.substitutions.length}
                    </td>
                    <td>
                      <Badge
                        tone={a.status === 'covered' ? 'ok' : a.status === 'cancelled' ? 'muted' : 'warn'}
                      >
                        {a.status}
                      </Badge>
                    </td>
                    {isManager && (
                      <td>
                        {a.status !== 'cancelled' && (
                          <button
                            type="button"
                            className="btn btn--ghost btn--sm"
                            onClick={() => dispatch(cancelAbsence(a.absence_id)).then(() => dispatch(fetchAbsences()))}
                          >
                            Cancel
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function CoveragePanel({ panel, saver, isManager, dispatch, busy }) {
  return (
    <div className="card coverage">
      <header className="coverage__head">
        <div>
          <h3>
            Coverage recommendations — {panel.teacher_name} ·{' '}
            <span className="mono">{panel.absence_date}</span> ({panel.day_label})
          </h3>
          <p className="muted">
            {panel.slots_total} affected period(s) · {panel.slots_uncovered} still open · ranked by
            subject specialization, department qualifications and free slots
          </p>
        </div>
        {isManager && panel.slots_uncovered > 0 && (
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy}
            onClick={() => dispatch(autoAssign(panel.absence_id)).then(() => {})}
          >
            Auto-cover all
          </button>
        )}
      </header>

      <ol className="coverage__list">
        {panel.slots.map((slot) => (
          <li key={slot.slot_id} className={`coverage__slot ${slot.covered ? 'is-covered' : ''}`}>
            <div className="coverage__slot-meta">
              <strong>{PERIOD_LABELS[slot.period_number] ?? `Period ${slot.period_number}`}</strong>
              <span>
                {slot.class_label} · {slot.subject_name}
              </span>
              {slot.covered ? <Badge tone="ok">COVERED</Badge> : <Badge tone="warn">OPEN</Badge>}
            </div>

            {!slot.covered && slot.candidates.length === 0 && (
              <p className="muted">No available substitute for this period — consider merging classes.</p>
            )}

            {!slot.covered && slot.candidates.length > 0 && (
              <ul className="candidate-list">
                {slot.candidates.map((candidate, index) => (
                  <li key={candidate.teacher_id} className="candidate">
                    <span className="candidate__rank mono">{index + 1}</span>
                    <div className="candidate__body">
                      <strong>{candidate.full_name}</strong>
                      <span className="muted">
                        {candidate.designation ?? 'Teacher'}
                        {candidate.staff_identifier ? ` · ${candidate.staff_identifier}` : ''}
                      </span>
                      <ul className="candidate__reasons">
                        {candidate.reasons.map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="candidate__side">
                      <span className={`mono score score--${candidate.score >= 60 ? 'high' : candidate.score >= 30 ? 'mid' : 'low'}`}>
                        {candidate.score}
                      </span>
                      {isManager && (
                        <button
                          type="button"
                          className="btn btn--sm btn--primary"
                          disabled={busy}
                          onClick={() =>
                            dispatch(
                              confirmSubstitution({
                                absenceId: panel.absence_id,
                                periodNumber: slot.period_number,
                                classId: slot.class_id,
                                substituteTeacherId: candidate.teacher_id,
                              })
                            )
                          }
                        >
                          Assign
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {slot.covered && <p className="muted">Substitute confirmed for this period.</p>}
          </li>
        ))}
      </ol>
      {panel.reason && (
        <p className="muted coverage__reason">Recorded reason: {panel.reason}</p>
      )}
    </div>
  );
}
