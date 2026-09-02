import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import { api } from '../api/client';
import Accordion from '../components/Accordion';
import Badge from '../components/Badge';
import { selectIsManager } from '../features/auth/authSlice';

/**
 * SYLLABUS COMPLETION MODULE — Classes 1 through 12.
 *
 * School Managers hold full CRUD: topic lists, target completion %, term
 * deadlines and manual progress overrides. The 'Log Topic Covered' modal
 * ticks off national curriculum units. Teachers see a read-only tracker.
 */

const EMPTY_PLAN_FORM = {
  class_id: '',
  subject_id: '',
  term_name: 'Term 1',
  target_completion_pct: 100,
  term_deadline: '',
  topics_text: '',
};

export default function Syllabus() {
  const isManager = useSelector(selectIsManager);
  const [plans, setPlans] = useState([]);
  const [classes, setClasses] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const [creating, setCreating] = useState(false);
  const [planForm, setPlanForm] = useState(EMPTY_PLAN_FORM);
  const [formSubjects, setFormSubjects] = useState([]);
  const [editingPlan, setEditingPlan] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [loggingPlan, setLoggingPlan] = useState(null);
  const [ticked, setTicked] = useState({});
  const [newTopic, setNewTopic] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [syllabus, classData] = await Promise.all([
        api('/api/v1/school/syllabus'),
        api('/api/v1/school/classes'),
      ]);
      setPlans(syllabus.plans ?? []);
      setClasses(classData.classes ?? []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Load the subject catalogue for the class picked inside the create modal.
  useEffect(() => {
    const klass = classes.find((c) => c.id === Number(planForm.class_id));
    if (!klass) {
      setFormSubjects([]);
      return;
    }
    api(`/api/v1/school/subjects?class_level=${encodeURIComponent(klass.class_level)}`)
      .then((data) => setFormSubjects(data.subjects ?? []))
      .catch(() => setFormSubjects([]));
  }, [planForm.class_id, classes]);

  const grouped = useMemo(() => {
    const byLevel = new Map();
    plans.forEach((plan) => {
      const level = plan.class_level ?? 'Unassigned';
      if (!byLevel.has(level)) byLevel.set(level, []);
      byLevel.get(level).push(plan);
    });
    return [...byLevel.entries()];
  }, [plans]);

  const flash = (message) => {
    setNotice(message);
    setError(null);
    window.setTimeout(() => setNotice(null), 4000);
  };

  const run = async (fn, success) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
      if (success) flash(success);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const createPlan = async (event) => {
    event.preventDefault();
    const topics = planForm.topics_text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((title, index) => ({ title, sort_order: index }));
    const ok = await run(
      () =>
        api('/api/v1/school/syllabus', {
          method: 'POST',
          body: {
            class_id: Number(planForm.class_id),
            subject_id: Number(planForm.subject_id),
            term_name: planForm.term_name,
            target_completion_pct: Number(planForm.target_completion_pct),
            term_deadline: planForm.term_deadline || null,
            topics,
          },
        }),
      'Syllabus plan created.'
    );
    if (ok) {
      setCreating(false);
      setPlanForm(EMPTY_PLAN_FORM);
    }
  };

  const openEdit = (plan) => {
    setEditingPlan(plan);
    setEditForm({
      term_name: plan.term_name,
      target_completion_pct: plan.target_completion_pct,
      term_deadline: plan.term_deadline ?? '',
      progress_override_pct: plan.progress_override_pct ?? '',
      notes: plan.notes ?? '',
    });
  };

  const saveEdit = async (event) => {
    event.preventDefault();
    const body = {
      term_name: editForm.term_name,
      target_completion_pct: Number(editForm.target_completion_pct),
      notes: editForm.notes || null,
    };
    if (editForm.term_deadline) body.term_deadline = editForm.term_deadline;
    else body.clear_term_deadline = true;
    if (editForm.progress_override_pct !== '' && editForm.progress_override_pct !== null) {
      body.progress_override_pct = Number(editForm.progress_override_pct);
    } else {
      body.clear_progress_override = true;
    }
    const ok = await run(
      () => api(`/api/v1/school/syllabus/${editingPlan.id}`, { method: 'PATCH', body }),
      'Syllabus plan updated.'
    );
    if (ok) setEditingPlan(null);
  };

  const deletePlan = async (plan) => {
    if (!window.confirm(`Delete the ${plan.term_name} ${plan.subject_name} syllabus for ${plan.class_label}?`)) return;
    await run(
      () => api(`/api/v1/school/syllabus/${plan.id}`, { method: 'DELETE' }),
      'Syllabus plan deleted.'
    );
  };

  const openLogModal = (plan) => {
    setLoggingPlan(plan);
    const state = {};
    plan.topics.forEach((topic) => {
      state[topic.id] = topic.is_covered;
    });
    setTicked(state);
    setNewTopic('');
  };

  const saveLog = async () => {
    const cover = loggingPlan.topics.filter((t) => ticked[t.id] && !t.is_covered).map((t) => t.id);
    const uncover = loggingPlan.topics.filter((t) => !ticked[t.id] && t.is_covered).map((t) => t.id);
    const ok = await run(async () => {
      if (cover.length) {
        await api(`/api/v1/school/syllabus/${loggingPlan.id}/log-covered`, {
          method: 'POST',
          body: { topic_ids: cover, covered: true },
        });
      }
      if (uncover.length) {
        await api(`/api/v1/school/syllabus/${loggingPlan.id}/log-covered`, {
          method: 'POST',
          body: { topic_ids: uncover, covered: false },
        });
      }
    }, 'Coverage log updated.');
    if (ok) setLoggingPlan(null);
  };

  const addTopic = async () => {
    const title = newTopic.trim();
    if (!title) return;
    const ok = await run(
      () =>
        api(`/api/v1/school/syllabus/${loggingPlan.id}/topics`, {
          method: 'POST',
          body: { title },
        }),
      'Topic added to the unit list.'
    );
    if (ok) {
      setNewTopic('');
      // refresh the modal's topic list from the reloaded plans
      const fresh = (await api('/api/v1/school/syllabus')).plans.find((p) => p.id === loggingPlan.id);
      if (fresh) openLogModal(fresh);
    }
  };

  const removeTopic = async (topic) => {
    if (!window.confirm(`Remove unit “${topic.title}”?`)) return;
    const ok = await run(
      () => api(`/api/v1/school/syllabus/topics/${topic.id}`, { method: 'DELETE' }),
      'Topic removed.'
    );
    if (ok) {
      const fresh = (await api('/api/v1/school/syllabus')).plans.find((p) => p.id === loggingPlan.id);
      if (fresh) openLogModal(fresh);
      else setLoggingPlan(null);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Syllabus Completion Tracker</h2>
            <span className="card__hint">
              National curriculum delivery across Classes 1–12
              {isManager ? ' — full editorial control' : ' — read-only view'}
            </span>
          </div>
          {isManager && (
            <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
              New syllabus plan
            </button>
          )}
        </header>

        {notice && <p className="alert alert--ok">{notice}</p>}
        {error && <p className="alert alert--danger">{error}</p>}
        {plans.length === 0 && (
          <p className="empty">
            No syllabus plans yet.{isManager ? ' Create the first plan to begin tracking curriculum delivery.' : ''}
          </p>
        )}

        <div className="accordion-group">
          {grouped.map(([level, levelPlans]) => (
            <Accordion key={level} title={level} meta={`${levelPlans.length} subject plan${levelPlans.length === 1 ? '' : 's'}`}>
              <div className="syllabus-grid">
                {levelPlans.map((plan) => (
                  <article key={plan.id} className="syllabus-card">
                    <header className="syllabus-card__head">
                      <div>
                        <h3 className="syllabus-card__title">{plan.subject_name}</h3>
                        <span className="syllabus-card__meta">
                          {plan.class_label} · {plan.term_name}
                          {plan.term_deadline && ` · due ${plan.term_deadline}`}
                        </span>
                      </div>
                      <Badge status={plan.on_track ? 'Present' : 'Late'}>
                        {plan.on_track ? 'ON TRACK' : 'BEHIND'}
                      </Badge>
                    </header>

                    <div className="progress">
                      <div className="progress__track">
                        <div
                          className="progress__fill"
                          style={{ width: `${Math.min(100, plan.effective_progress_pct)}%` }}
                        />
                        <div className="progress__target" style={{ left: `${plan.target_completion_pct}%` }} />
                      </div>
                      <div className="progress__stats">
                        <span>
                          <strong>{plan.effective_progress_pct}%</strong> delivered
                          {plan.progress_override_pct != null && ' (manual override)'}
                        </span>
                        <span>target {plan.target_completion_pct}%</span>
                      </div>
                    </div>

                    <p className="syllabus-card__units">
                      {plan.topics_covered}/{plan.topics_total} curriculum units covered
                      {plan.days_to_deadline != null && (
                        <span className={plan.days_to_deadline < 0 ? 'syllabus-card__overdue' : ''}>
                          {' '}· {plan.days_to_deadline < 0
                            ? `${Math.abs(plan.days_to_deadline)} days overdue`
                            : `${plan.days_to_deadline} days to deadline`}
                        </span>
                      )}
                    </p>

                    {isManager && (
                      <div className="toolbar">
                        <button type="button" className="btn btn--small btn--primary" onClick={() => openLogModal(plan)}>
                          Log Topic Covered
                        </button>
                        <button type="button" className="btn btn--small" onClick={() => openEdit(plan)}>Edit</button>
                        <button type="button" className="btn btn--small btn--ghost" onClick={() => deletePlan(plan)}>
                          Delete
                        </button>
                      </div>
                    )}
                    {!isManager && plan.topics_total > 0 && (
                      <details className="syllabus-card__list">
                        <summary>View unit checklist</summary>
                        <ul>
                          {plan.topics.map((topic) => (
                            <li key={topic.id} className={topic.is_covered ? 'is-covered' : ''}>
                              {topic.is_covered ? '☑' : '☐'} {topic.unit_code && <span className="mono">{topic.unit_code} </span>}
                              {topic.title}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </article>
                ))}
              </div>
            </Accordion>
          ))}
        </div>
      </section>

      {/* ---------------- Create plan modal (managers) ---------------- */}
      {creating && (
        <div className="modal-backdrop" onClick={() => setCreating(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h2 className="card__title">New syllabus plan</h2>
            <form className="form" onSubmit={createPlan}>
              <div className="student-form__grid">
                <label className="field">
                  <span className="field__label">Class</span>
                  <select
                    className="input"
                    required
                    value={planForm.class_id}
                    onChange={(event) => setPlanForm({ ...planForm, class_id: event.target.value, subject_id: '' })}
                  >
                    <option value="">Select class…</option>
                    {classes.map((klass) => (
                      <option key={klass.id} value={klass.id}>
                        {klass.class_level} {klass.class_stream}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Subject</span>
                  <select
                    className="input"
                    required
                    value={planForm.subject_id}
                    onChange={(event) => setPlanForm({ ...planForm, subject_id: event.target.value })}
                  >
                    <option value="">Select subject…</option>
                    {formSubjects.map((subject) => (
                      <option key={subject.id} value={subject.id}>{subject.subject_name}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Term</span>
                  <select
                    className="input"
                    value={planForm.term_name}
                    onChange={(event) => setPlanForm({ ...planForm, term_name: event.target.value })}
                  >
                    {['Term 1', 'Term 2', 'Term 3'].map((term) => <option key={term}>{term}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Target completion %</span>
                  <input
                    className="input"
                    type="number"
                    min="0"
                    max="100"
                    value={planForm.target_completion_pct}
                    onChange={(event) => setPlanForm({ ...planForm, target_completion_pct: event.target.value })}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Term deadline</span>
                  <input
                    className="input"
                    type="date"
                    value={planForm.term_deadline}
                    onChange={(event) => setPlanForm({ ...planForm, term_deadline: event.target.value })}
                  />
                </label>
              </div>
              <label className="field">
                <span className="field__label">Curriculum units (one per line)</span>
                <textarea
                  className="input"
                  rows={6}
                  placeholder={'Unit 1 — Number systems\nUnit 2 — Algebraic expressions'}
                  value={planForm.topics_text}
                  onChange={(event) => setPlanForm({ ...planForm, topics_text: event.target.value })}
                />
              </label>
              <div className="toolbar toolbar--end">
                <button type="button" className="btn btn--ghost" onClick={() => setCreating(false)}>Cancel</button>
                <button type="submit" className="btn btn--primary" disabled={busy}>Create plan</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---------------- Edit plan modal (managers) ---------------- */}
      {editingPlan && editForm && (
        <div className="modal-backdrop" onClick={() => setEditingPlan(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h2 className="card__title">Edit — {editingPlan.subject_name} · {editingPlan.class_label}</h2>
            <form className="form" onSubmit={saveEdit}>
              <div className="student-form__grid">
                <label className="field">
                  <span className="field__label">Term</span>
                  <select
                    className="input"
                    value={editForm.term_name}
                    onChange={(event) => setEditForm({ ...editForm, term_name: event.target.value })}
                  >
                    {['Term 1', 'Term 2', 'Term 3'].map((term) => <option key={term}>{term}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Target completion %</span>
                  <input
                    className="input"
                    type="number"
                    min="0"
                    max="100"
                    value={editForm.target_completion_pct}
                    onChange={(event) => setEditForm({ ...editForm, target_completion_pct: event.target.value })}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Term deadline</span>
                  <input
                    className="input"
                    type="date"
                    value={editForm.term_deadline}
                    onChange={(event) => setEditForm({ ...editForm, term_deadline: event.target.value })}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Progress override % (blank = computed)</span>
                  <input
                    className="input"
                    type="number"
                    min="0"
                    max="100"
                    value={editForm.progress_override_pct}
                    onChange={(event) => setEditForm({ ...editForm, progress_override_pct: event.target.value })}
                  />
                </label>
              </div>
              <label className="field">
                <span className="field__label">Notes</span>
                <textarea
                  className="input"
                  rows={3}
                  value={editForm.notes}
                  onChange={(event) => setEditForm({ ...editForm, notes: event.target.value })}
                />
              </label>
              <div className="toolbar toolbar--end">
                <button type="button" className="btn btn--ghost" onClick={() => setEditingPlan(null)}>Cancel</button>
                <button type="submit" className="btn btn--primary" disabled={busy}>Save changes</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---------------- Log Topic Covered modal (managers) ---------------- */}
      {loggingPlan && (
        <div className="modal-backdrop" onClick={() => setLoggingPlan(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h2 className="card__title">Log Topic Covered</h2>
            <p className="card__hint">
              {loggingPlan.subject_name} · {loggingPlan.class_label} · {loggingPlan.term_name} — tick the national
              curriculum units delivered.
            </p>
            <ul className="unit-list">
              {loggingPlan.topics.map((topic) => (
                <li key={topic.id} className="unit-list__row">
                  <label className="unit-list__label">
                    <input
                      type="checkbox"
                      checked={Boolean(ticked[topic.id])}
                      onChange={() => setTicked({ ...ticked, [topic.id]: !ticked[topic.id] })}
                    />
                    <span>
                      {topic.unit_code && <span className="mono">{topic.unit_code} · </span>}
                      {topic.title}
                    </span>
                  </label>
                  <button
                    type="button"
                    className="btn btn--small btn--ghost"
                    title="Remove unit"
                    onClick={() => removeTopic(topic)}
                  >
                    ✕
                  </button>
                </li>
              ))}
              {loggingPlan.topics.length === 0 && <li className="empty">No units yet — add the first below.</li>}
            </ul>
            <div className="toolbar">
              <input
                className="input"
                placeholder="Add a curriculum unit…"
                value={newTopic}
                onChange={(event) => setNewTopic(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && (event.preventDefault(), addTopic())}
              />
              <button type="button" className="btn" onClick={addTopic} disabled={busy}>Add unit</button>
            </div>
            <div className="toolbar toolbar--end">
              <button type="button" className="btn btn--ghost" onClick={() => setLoggingPlan(null)}>Cancel</button>
              <button type="button" className="btn btn--primary" onClick={saveLog} disabled={busy}>
                Save coverage log
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
