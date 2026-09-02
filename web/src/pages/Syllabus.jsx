import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import Modal from '../components/Modal';
import ProgressMeter from '../components/ProgressMeter';
import { KpiCard } from '../components/Charts';
import { selectUser } from '../features/auth/authSlice';
import {
  clearNotice,
  closeTopics,
  createPlanTopic,
  deletePlanTopic,
  deleteProgressEntry,
  deleteSyllabusPlan,
  fetchPlanDetail,
  fetchPlanTopics,
  fetchSyllabusSummary,
  logTopicsCovered,
  recordSyllabusProgress,
  setClassLevel,
  undoTopicsCovered,
  updateBenchmarks,
  updatePlanTopic,
  updateSyllabusPlan,
} from '../features/syllabus/syllabusSlice';
import { useDataSaver } from '../hooks/useDataSaver';

const STATUS_TONE = { 'On Track': 'ok', Ahead: 'info', 'Behind Schedule': 'danger' };
const todayISO = () => new Date().toISOString().slice(0, 10);

/**
 * Module 2 + Refinement 1 — Syllabus Completion Tracker (Classes 1–12).
 *
 * Managers get full plan administration: edit the topic list, unit counts,
 * target percentages and term deadlines, delete plans, and override progress
 * history. Managers and Department Heads tick specific national-curriculum
 * units through the "Log Topic Covered" checklist, which writes an audited
 * checkpoint automatically.
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
  const isDeptHead = user?.role === 'teacher' && user?.is_department_head === true;
  const canLogTopics = isManager || isDeptHead;

  const [editing, setEditing] = useState(null); // plan_id with open inline form
  const [planEditor, setPlanEditor] = useState(null); // row object for full plan editor
  const [topicPlan, setTopicPlan] = useState(null); // row object for the topic checklist

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

  const closePlanEditor = () => setPlanEditor(null);

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h2>Syllabus completion tracker</h2>
          <p className="muted">
            Curriculum pace for Classes 1&ndash;12 against midterm and final exam benchmarks.
            {canLogTopics
              ? ' Tick the national-curriculum units you have covered to log audited progress.'
              : ' Subjects behind the interpolated schedule are flagged.'}
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
                      canLogTopics={canLogTopics}
                      busy={busy}
                      editing={editing === row.plan_id}
                      onEdit={() => setEditing(editing === row.plan_id ? null : row.plan_id)}
                      onTopics={() => setTopicPlan(row)}
                      onManage={() => setPlanEditor(row)}
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

      {topicPlan && <TopicsModal row={topicPlan} canEditTopics={canLogTopics} busy={busy} onClose={() => setTopicPlan(null)} />}

      {planEditor && (
        <PlanEditorModal
          row={planEditor}
          busy={busy}
          onClose={closePlanEditor}
          onDeleted={() => {
            closePlanEditor();
          }}
        />
      )}
    </section>
  );
}

function TableRow({ row, saver, isManager, canLogTopics, busy, editing, onEdit, onTopics, onManage, dispatch }) {
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
        {canLogTopics && (
          <button type="button" className="btn btn--sm btn--primary" onClick={onTopics}>
            Topics
          </button>
        )}
        {(isManager || !saver) && (
          <button type="button" className="btn btn--sm btn--ghost" onClick={onEdit}>
            {editing ? 'Close' : 'Update'}
          </button>
        )}
        {isManager && (
          <button type="button" className="btn btn--sm btn--ghost" onClick={onManage}>
            Manage
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

/** Refinement 1 — "Log Topic Covered" checklist over the national curriculum. */
function TopicsModal({ row, canEditTopics, busy, onClose }) {
  const dispatch = useDispatch();
  const { topics, topicsStatus } = useSelector((state) => state.syllabus);
  const [ticked, setTicked] = useState(() => new Set());
  const [note, setNote] = useState('');
  const [coveredOn, setCoveredOn] = useState(todayISO());
  const [draft, setDraft] = useState(null); // {id?, code, title}

  useEffect(() => {
    dispatch(fetchPlanTopics(row.plan_id));
    return () => dispatch(closeTopics());
  }, [dispatch, row.plan_id]);

  const doneCount = topics.filter((t) => t.is_done).length;

  const toggle = (topicId) =>
    setTicked((prev) => {
      const next = new Set(prev);
      if (next.has(topicId)) next.delete(topicId);
      else next.add(topicId);
      return next;
    });

  const saveDraft = (event) => {
    event.preventDefault();
    if (!draft?.title?.trim()) return;
    const body = { code: draft.code?.trim() || undefined, title: draft.title.trim() };
    if (draft.id) {
      dispatch(updatePlanTopic({ planId: row.plan_id, topicId: draft.id, ...body }));
    } else {
      dispatch(createPlanTopic({ planId: row.plan_id, ...body }));
    }
    setDraft(null);
  };

  return (
    <Modal title={`Curriculum topics — ${row.subject_name} (${row.class_level})`} onClose={onClose} wide>
      <p className="muted">
        {row.term} · {doneCount}/{topics.length || row.total_units} topics marked covered · plan at{' '}
        {row.completion_pct}%. Tick the units covered and log them — a progress checkpoint is
        written automatically.
      </p>

      {topicsStatus === 'loading' && topics.length === 0 ? (
        <p className="empty">Loading topics…</p>
      ) : topics.length === 0 ? (
        <p className="empty">No topic list yet for this plan.</p>
      ) : (
        <ul className="topic-list">
          {topics.map((topic) => (
            <li key={topic.id} className={`topic ${topic.is_done ? 'is-done' : ''}`}>
              <label className="topic__tick">
                <input
                  type="checkbox"
                  checked={ticked.has(topic.id)}
                  onChange={() => toggle(topic.id)}
                />
                <span className="mono topic__code">{topic.code}</span>
                <span className="topic__title">{topic.title}</span>
              </label>
              <span className="topic__meta">
                {topic.is_done ? (
                  <Badge tone="ok">COVERED{topic.done_date ? ` ${topic.done_date}` : ''}</Badge>
                ) : null}
                {canEditTopics && (
                  <span className="topic__actions">
                    <button
                      type="button"
                      className="btn btn--sm btn--ghost"
                      onClick={() => setDraft({ id: topic.id, code: topic.code, title: topic.title })}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn--sm btn--danger"
                      onClick={() => dispatch(deletePlanTopic({ planId: row.plan_id, topicId: topic.id }))}
                    >
                      ✕
                    </button>
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {canEditTopics && (
        <form className="form-row" onSubmit={saveDraft}>
          {draft && (
            <label className="field field--tight">
              <span>Code</span>
              <input
                type="text"
                className="mono"
                maxLength={20}
                placeholder="auto"
                value={draft.code ?? ''}
                onChange={(e) => setDraft({ ...draft, code: e.target.value })}
              />
            </label>
          )}
          <label className="field field--grow">
            <span>New topic title</span>
            <input
              type="text"
              maxLength={200}
              placeholder="e.g. Fractions and decimals"
              value={draft?.id ? undefined : draft?.title ?? ''}
              onChange={(e) => setDraft({ ...(draft ?? {}), title: e.target.value })}
              required={Boolean(draft)}
              disabled={!draft}
            />
          </label>
          {draft?.id ? (
            <>
              <button type="submit" className="btn btn--sm btn--primary">
                Save topic
              </button>
              <button type="button" className="btn btn--sm btn--ghost" onClick={() => setDraft(null)}>
                Cancel
              </button>
            </>
          ) : (
            <button type="button" className="btn btn--sm btn--ghost" onClick={() => setDraft({ title: '' })}>
              Add topic…
            </button>
          )}
        </form>
      )}

      <footer className="modal__foot">
        <label className="field field--tight">
          <span>Covered on</span>
          <input type="date" value={coveredOn} max={todayISO()} onChange={(e) => setCoveredOn(e.target.value)} />
        </label>
        <label className="field field--grow">
          <span>Note</span>
          <input
            type="text"
            maxLength={160}
            placeholder="auto-generated when left blank"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={busy || ticked.size === 0}
          onClick={() => {
            dispatch(undoTopicsCovered({ planId: row.plan_id, topicIds: [...ticked] })).then(() => setTicked(new Set()));
          }}
        >
          Un-tick selected
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy || ticked.size === 0}
          onClick={() => {
            dispatch(
              logTopicsCovered({
                planId: row.plan_id,
                topicIds: [...ticked],
                note: note || undefined,
                coveredOn: coveredOn || undefined,
              })
            ).then(() => {
              setTicked(new Set());
              setNote('');
            });
          }}
        >
          Log {ticked.size || ''} topic(s) covered
        </button>
      </footer>
    </Modal>
  );
}

/** Refinement 1 — manager plan editor: units, targets, term deadlines + history override. */
function PlanEditorModal({ row, busy, onClose, onDeleted }) {
  const dispatch = useDispatch();
  const { planEntries } = useSelector((state) => state.syllabus);
  const [form, setForm] = useState({
    term: row.term,
    totalUnits: row.total_units,
    midtermTargetPct: row.midterm_target_pct,
    finalTargetPct: row.final_target_pct,
    midtermDate: row.midterm_date ?? '',
    termStart: row.term_start ?? '',
    termEnd: row.term_end ?? '',
  });
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    dispatch(fetchPlanDetail(row.plan_id));
  }, [dispatch, row.plan_id]);

  const set = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const save = (event) => {
    event.preventDefault();
    dispatch(
      updateSyllabusPlan({
        planId: row.plan_id,
        term: form.term || undefined,
        total_units: form.totalUnits === '' ? undefined : Number(form.totalUnits),
        midterm_target_pct: form.midtermTargetPct === '' ? undefined : Number(form.midtermTargetPct),
        final_target_pct: form.finalTargetPct === '' ? undefined : Number(form.finalTargetPct),
        midterm_date: form.midtermDate || undefined,
        term_start: form.termStart || undefined,
        term_end: form.termEnd || undefined,
      })
    ).then(() => dispatch(fetchSyllabusSummary({})));
  };

  const remove = () => {
    dispatch(deleteSyllabusPlan({ planId: row.plan_id })).then((action) => {
      if (deleteSyllabusPlan.fulfilled.match(action)) onDeleted();
    });
  };

  return (
    <Modal title={`Manage plan — ${row.subject_name} (${row.class_level})`} onClose={onClose} wide>
      <form className="form-grid" onSubmit={save}>
        <label className="field">
          <span>Term</span>
          <select value={form.term} onChange={set('term')}>
            <option>Term 1</option>
            <option>Term 2</option>
            <option>Term 3</option>
          </select>
        </label>
        <label className="field">
          <span>Total units in syllabus</span>
          <input type="number" min={1} max={500} value={form.totalUnits} onChange={set('totalUnits')} required />
        </label>
        <label className="field">
          <span>Midterm target %</span>
          <input type="number" min={0} max={100} value={form.midtermTargetPct} onChange={set('midtermTargetPct')} required />
        </label>
        <label className="field">
          <span>Final target %</span>
          <input type="number" min={0} max={100} value={form.finalTargetPct} onChange={set('finalTargetPct')} required />
        </label>
        <label className="field">
          <span>Term start</span>
          <input type="date" value={form.termStart ?? ''} onChange={set('termStart')} />
        </label>
        <label className="field">
          <span>Midterm deadline</span>
          <input type="date" value={form.midtermDate ?? ''} onChange={set('midtermDate')} />
        </label>
        <label className="field">
          <span>Term end</span>
          <input type="date" value={form.termEnd ?? ''} onChange={set('termEnd')} />
        </label>
        <div className="form-grid__actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Save plan
          </button>
        </div>
      </form>

      <h4 className="section-title">Progress history ({planEntries.length})</h4>
      {planEntries.length === 0 ? (
        <p className="empty">No checkpoints recorded yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Units after</th>
                <th>Note</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {planEntries.map((entry) => (
                <tr key={entry.id}>
                  <td className="mono">{entry.entry_date}</td>
                  <td className="mono">{entry.units_after}</td>
                  <td className="muted">{entry.note ?? '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--sm btn--danger"
                      disabled={busy}
                      title="Delete this checkpoint and re-derive progress"
                      onClick={() => dispatch(deleteProgressEntry({ planId: row.plan_id, entryId: entry.id }))}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <footer className="modal__foot modal__foot--danger">
        {confirmDelete ? (
          <>
            <span className="muted">Delete this plan, its topic list and progress history?</span>
            <button type="button" className="btn btn--danger" disabled={busy} onClick={remove}>
              Yes, delete plan
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setConfirmDelete(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button type="button" className="btn btn--danger" onClick={() => setConfirmDelete(true)}>
            Delete plan…
          </button>
        )}
      </footer>
    </Modal>
  );
}
