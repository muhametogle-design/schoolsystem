import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useSearchParams } from 'react-router-dom';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import {
  clearLookup,
  lookupStudent,
  selectLookup,
} from '../features/students/studentSlice';

/**
 * Global roll-number lookup. Returns a seasonal summary: profile, guardian contact,
 * every PUBLISHED marksheet and the full attendance log with truancy markers.
 */
export default function StudentLookup() {
  const dispatch = useDispatch();
  const [searchParams] = useSearchParams();
  const selectedRoll = searchParams.get('roll') ?? '';
  const result = useSelector(selectLookup);
  const { error } = useSelector((state) => state.students);
  const [term, setTerm] = useState('');

  useEffect(() => {
    dispatch(clearLookup());
    if (selectedRoll) {
      setTerm(selectedRoll);
      dispatch(lookupStudent(selectedRoll));
    }
  }, [dispatch, selectedRoll]);

  const search = (event) => {
    event.preventDefault();
    if (term.trim()) dispatch(lookupStudent(term.trim()));
  };

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head">
          <h2 className="card__title">Global Student Lookup</h2>
          <span className="card__hint">
            Search any school roll number across every licensed institution in the region
          </span>
        </header>

        <form className="toolbar toolbar--search" onSubmit={search}>
          <input
            className="input input--search"
            placeholder="NG-10023"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
          />
          <button type="submit" className="btn btn--primary">
            Search
          </button>
        </form>

        {error && <p className="alert alert--danger">{error}</p>}
        {!result && !error && (
          <p className="empty">Enter a student roll number to open their seasonal summary.</p>
        )}
      </section>

      {result && (
        <>
          <section className="card">
            <header className="card__head card__head--row">
              <div>
                <h2 className="card__title">{result.full_legal_name}</h2>
                <span className="card__hint mono">Roll number: {result.roll_number ?? result.ne_sid}</span>
              </div>
              <Badge status="Active">{result.school?.school_name}</Badge>
            </header>

            <div className="detail-grid">
              <div className="detail-block">
                <h3 className="detail-block__title">Personal details</h3>
                <dl className="detail-list">
                  <div>
                    <dt>Age</dt>
                    <dd>{result.age != null ? `${result.age} years` : '—'}</dd>
                  </div>
                  <div>
                    <dt>Date of birth</dt>
                    <dd>{result.date_of_birth ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Gender</dt>
                    <dd>{result.gender ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Class</dt>
                    <dd>{result.class_label ?? '—'}</dd>
                  </div>
                  <div className="detail-list__wide">
                    <dt>Address</dt>
                    <dd>{result.physical_address ?? '—'}</dd>
                  </div>
                </dl>
              </div>

              <div className="detail-block">
                <h3 className="detail-block__title">Guardian</h3>
                <div className="contact-card">
                  <span className="contact-card__name">{result.guardian?.name ?? '—'}</span>
                  <span className="contact-card__rel">
                    {result.guardian?.relationship ?? '—'}
                  </span>
                  <dl className="detail-list detail-list--tight">
                    <div>
                      <dt>Phone</dt>
                      <dd>{result.guardian?.phone ?? '—'}</dd>
                    </div>
                    <div>
                      <dt>Email</dt>
                      <dd>{result.guardian?.email ?? '—'}</dd>
                    </div>
                    <div>
                      <dt>Emergency</dt>
                      <dd>{result.guardian?.emergency_phone ?? '—'}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            </div>
          </section>

          <div className="kpi-grid">
            <KpiCard
              label="Season Attendance"
              value={
                result.attendance?.attendance_pct != null
                  ? `${result.attendance.attendance_pct}%`
                  : '—'
              }
              hint={`${result.attendance?.days_present ?? 0} present of ${result.attendance?.days_recorded ?? 0} days`}
              tone={(result.attendance?.attendance_pct ?? 0) >= 85 ? 'ok' : 'warn'}
            />
            <KpiCard label="Absences" value={result.attendance?.days_absent ?? 0} tone="danger" />
            <KpiCard label="Late arrivals" value={result.attendance?.days_late ?? 0} tone="warn" />
            <KpiCard
              label="Truancy marker"
              value={result.attendance?.truancy_flag ? 'FLAGGED' : 'CLEAR'}
              hint={`Longest absence run: ${result.attendance?.longest_absence_run ?? 0} days`}
              tone={result.attendance?.truancy_flag ? 'danger' : 'ok'}
            />
          </div>

          <section className="card">
            <header className="card__head">
              <h2 className="card__title">Published examination marksheets</h2>
              <span className="card__hint">
                Draft results are withheld until the school releases them
              </span>
            </header>

            {result.exams.length === 0 && (
              <p className="empty">No published results for this student.</p>
            )}

            {result.withheld?.draft_records > 0 && (
              <p className="alert alert--muted">
                {result.withheld.draft_records} draft record(s) withheld by the Exam Data
                Release Valve
                {result.withheld.exams.length
                  ? ` — ${result.withheld.exams.join(', ')}`
                  : ''}
                . They appear here once the school publishes them.
              </p>
            )}

            {result.exams.map((exam) => (
              <div key={exam.exam_name} className="sheet__exam">
                <header className="sheet__exam-head">
                  <h3>{exam.exam_name}</h3>
                  <span className="sheet__exam-meta">
                    Mean {exam.average_score ?? '—'}
                    <Badge status="PUBLISHED">PUBLISHED</Badge>
                  </span>
                </header>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Score</th>
                      <th>Grade</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exam.subjects.map((s) => (
                      <tr key={`${exam.exam_name}-${s.subject_name}`}>
                        <td>{s.subject_name}</td>
                        <td className="mono">{s.score}</td>
                        <td>{s.letter}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </section>

          <section className="card">
            <header className="card__head">
              <h2 className="card__title">Season attendance log</h2>
              <span className="card__hint">Most recent entries</span>
            </header>
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Truancy</th>
                </tr>
              </thead>
              <tbody>
                {result.attendance_log.map((entry) => (
                  <tr key={entry.date}>
                    <td className="mono">{entry.date}</td>
                    <td>
                      <Badge status={entry.status}>{entry.status}</Badge>
                    </td>
                    <td>
                      {entry.truancy ? (
                        <Badge status="NOT_PAID">Truancy run</Badge>
                      ) : (
                        <span className="card__hint">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="alert alert--muted">{result.financial_data}</p>
          </section>
        </>
      )}
    </div>
  );
}
