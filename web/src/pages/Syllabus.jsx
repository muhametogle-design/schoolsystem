import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import ProgressMeter from '../components/ProgressMeter';
import { KpiCard } from '../components/Charts';
import { selectUser } from '../features/auth/authSlice';
import {
  clearNotice,
  fetchSyllabusSummary,
  recordSyllabusProgress,
  setClassLevel,
  updateBenchmarks,
} from '../features/syllabus/syllabusSlice';
import { useDataSaver } from '../hooks/useDataSaver';

const STATUS_TONE = { 'On Track': 'ok', Ahead: 'info', 'Behind Schedule': 'danger' };

/**
 * Module 2 — Syllabus Completion Tracker (Classes 1-12).
 *
 * Per-subject curriculum progress with midterm/final benchmark gates. Subjects
 * falling behind schedule are flagged with an actionable status tag; managers
 * can adjust the benchmarks, teachers record audited progress checkpoints.
 */
export default function Syllabus() {
  const dispatch = useDispatch();
  const user = useSelector(selectUser);
  const saver = useDataSaver();
  const {
    rows,
    counts,
    averageCompletionPct,
    flaggedCount,
    classLevel,
    allClassLevels,
    busy,
    error,
    notice,
  } = useSelector((state) => state.syllabus);
  const isManager = user?.role === 'school_manager';

  const [editing, setEditing] = useState(null); // plan_id with open inline form

  useEffect(() => {
    dispatch(fetchSyllabusSummary({ classLevel }));
  }, [dispatch, classLevel]);

  useEffect(() => {
    if (!notice && !error) return;
    const timer = setTimeout(() => dispatch(clearNotice()), 4000);
    return () => clearTimeout(timer);
  }, [notice, error, dispatch]);

  const grouped = useMemo(() => {
    const map = new Map();
    rows.forEach((row) => {
      const key = `${row.class_level} ${row.class_stream ?? ''}`.trim();
      map.set(key, [...(map.get(key) ?? []), row]);
    });
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }));
  }, [rows]);

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h2>Syllabus completion tracker</h2>
          <p className="muted">
            Curriculum pace for Classes 1&ndash;12 against midterm and final exam benchmarks.
            Subjects behind the interpolated schedule are flagged.
          </p>
        </div>
        <label className="field">
          <span>Class level</span>
          <select value={classLevel ?? ''} onChange={(e) => dispatch(setClassLevel(e.target.value || null))}>
            <option value="">All classes (1&ndash;12)</option>
            {allClassLevels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
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
        <KpiCard label="On Track" value={counts['On Track'] ?? 0} tone="ok" />
        <KpiCard label="Ahead" value={counts['Ahead'] ?? 0} tone="info" />
        <KpiCard label="Behind Schedule" value={counts['Behind Schedule'] ?? 0} tone="danger" />
        <KpiCard label="Average completion" value={`${averageCompletionPct}%`} tone="neutral" />
      </div>

      {rows.length === 0 ? (
        <div className="card">
          <p className="empty">No syllabus plans yet — managers create them per class and subject.</p>
        </div>
      ) : (
        grouped.map(([label, subjectRows]) => (
          <div key={label} className="card">
            <h3 className="card__title">{label}</h3>
            <div className="table-wrap">
              <table className="table syllabus-table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Progress</th>
                    <th>Units</th>
                    <th>Expected</th>
                    <th>Midterm gate</th>
                    <th>Final gate</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {subjectRows.map((row) => (
                    <TableRow
                      key={row.plan_id}
                      row={row}
                      saver={saver}
                      isManager={isManager}
                      busy={busy}
                      editing={editing === row.plan_id}
                      onEdit={() => setEditing(editing === row.plan_id ? null : row.plan_id)}
                      dispatch={dispatch}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}

      {flaggedCount > 0 && (
        <p className="alert alert--warn" role="status">
          {flaggedCount} subject plan(s) are behind schedule — record catch-up progress or adjust
          the benchmark gates with the school manager.
        </p>
      )}
    </section>
  );
}

function TableRow({ row, saver, isManager, busy, editing, onEdit, dispatch }) {
  const [units, setUnits] = useState(row.units_completed);
  const [note, setNote] = useState('');
  const [midterm, setMidterm] = useState(row.midterm_target_pct);

  useEffect(() => {
    setUnits(row.units_completed);
    setMidterm(row.midterm_target_pct);
  }, [row.units_completed, row.midterm_target_pct]);

  return (
    <tr className={row.flagged ? 'row-flagged' : ''}>
      <td>
        <strong>{row.subject_name}</strong>
        <span className="muted table-sub">{row.term}</span>
      </td>
      <td className="meter-cell">
        <ProgressMeter value={row.completion_pct} label={`${row.completion_pct}% of syllabus`} />
      </td>
      <td className="mono">
        {row.units_completed}/{row.total_units}
      </td>
      <td className="mono muted">{row.expected_pct}%</td>
      <td className="mono">{row.midterm_target_pct}%</td>
      <td className="mono">{row.final_target_pct}%</td>
      <td>
        <Badge tone={STATUS_TONE[row.status]}>{row.status}</Badge>
      </td>
      <td className="actions-cell">
        {(isManager || !saver) && (
          <button type="button" className="btn btn--sm btn--ghost" onClick={onEdit}>
            {editing ? 'Close' : 'Update'}
          </button>
        )}
      </td>
      {editing && (
        <td colSpan={8} className="inline-forms">
          <form
            className="form-row"
            onSubmit={(event) => {
              event.preventDefault();
              dispatch(
                recordSyllabusProgress({
                  planId: row.plan_id,
                  unitsAfter: Number(units),
                  note: note || undefined,
                })
              ).then(() => setNote(''));
            }}
          >
            <label className="field">
              <span>Units completed to date</span>
              <input
                type="number"
                min={0}
                max={row.total_units}
                value={units}
                onChange={(e) => setUnits(e.target.value)}
                required
              />
            </label>
            <label className="field field--grow">
              <span>Note</span>
              <input
                type="text"
                value={note}
                maxLength={120}
                placeholder="e.g. finished unit 9 before midterm break"
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            <button type="submit" className="btn btn--sm btn--primary" disabled={busy}>
              Record progress
            </button>
          </form>
          {isManager && (
            <form
              className="form-row"
              onSubmit={(event) => {
                event.preventDefault();
                dispatch(
                  updateBenchmarks({
                    planId: row.plan_id,
                    midtermTargetPct: Number(midterm),
                  })
                );
              }}
            >
              <label className="field">
                <span>Midterm benchmark %</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={midterm}
                  onChange={(e) => setMidterm(e.target.value)}
                  required
                />
              </label>
              <button type="submit" className="btn btn--sm btn--ghost">
                Save benchmark
              </button>
            </form>
          )}
        </td>
      )}
    </tr>
  );
}
