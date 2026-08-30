import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Logo from '../components/Logo';
import Badge from '../components/Badge';
import {
  fetchReportCard,
  selectReportCard,
} from '../features/students/studentSlice';

/**
 * Official single-page assessment card.
 *
 * The screen version carries the action buttons; `@media print` in styles.css
 * strips the chrome, hides the buttons and fixes the sheet to A4 so the
 * browser's print dialog produces a clean PDF.
 */
export default function ReportCard() {
  const { neSid } = useParams();
  const dispatch = useDispatch();
  const card = useSelector(selectReportCard);

  useEffect(() => {
    dispatch(fetchReportCard(neSid));
  }, [dispatch, neSid]);

  if (!card) {
    return (
      <div className="report">
        <p className="empty">Preparing assessment card…</p>
      </div>
    );
  }

  const { school, student, exams, overall, attendance, academic_year, class_teacher } = card;

  return (
    <div className="report">
      <div className="report__actions no-print">
        <button type="button" className="btn btn--primary" onClick={() => window.print()}>
          Print Report Card
        </button>
        <span className="report__hint">
          Use “Save as PDF” in the print dialog for a digital copy.
        </span>
      </div>

      <article className="sheet">
        <header className="sheet__head">
          <Logo size={54} withWordmark={false} />
          <div className="sheet__school">
            <h1>{school.school_name}</h1>
            <p>
              Licence {school.state_license_number} · {school.physical_address}
            </p>
            <p>
              {school.contact_phone} · {school.contact_email}
            </p>
          </div>
          <div className="sheet__meta">
            <span className="sheet__doc">Student Assessment Report</span>
            <span className="sheet__year">{academic_year?.label ?? '—'}</span>
          </div>
        </header>

        <section className="sheet__identity">
          <div className="sheet__id-block">
            <span className="sheet__label">Student name</span>
            <strong>{student.full_legal_name}</strong>
          </div>
          <div className="sheet__id-block">
            <span className="sheet__label">Roll number</span>
            <strong className="mono">{student.roll_number ?? student.ne_sid}</strong>
          </div>
          <div className="sheet__id-block">
            <span className="sheet__label">Age</span>
            <strong>{student.age != null ? `${student.age} yrs` : '—'}</strong>
          </div>
          <div className="sheet__id-block">
            <span className="sheet__label">Class</span>
            <strong>{student.class_label ?? '—'}</strong>
          </div>
          <div className="sheet__id-block sheet__id-block--wide">
            <span className="sheet__label">Parent / Guardian contact</span>
            <strong>
              {student.guardian?.name ?? '—'}
              {student.guardian?.relationship ? ` (${student.guardian.relationship})` : ''}
            </strong>
            <span>
              {student.guardian?.phone ?? '—'} · {student.guardian?.email ?? '—'}
            </span>
          </div>
          <div className="sheet__id-block sheet__id-block--wide">
            <span className="sheet__label">Residential address</span>
            <strong>{student.physical_address ?? '—'}</strong>
          </div>
        </section>

        <section className="sheet__section">
          <h2>Term examination breakdown</h2>
          {exams.length === 0 && <p className="empty">No assessments recorded.</p>}

          {exams.map((exam) => (
            <div key={exam.exam_name} className="sheet__exam">
              <header className="sheet__exam-head">
                <h3>{exam.exam_name}</h3>
                <span className="sheet__exam-meta">
                  Mean {exam.average_score ?? '—'} · GPA {exam.gpa ?? '—'}
                  <Badge status={exam.is_published ? 'PUBLISHED' : 'DRAFT'}>
                    {exam.is_published ? 'PUBLISHED' : 'DRAFT'}
                  </Badge>
                </span>
              </header>
              <table className="table table--sheet">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Score</th>
                    <th>Grade</th>
                    <th>Points</th>
                  </tr>
                </thead>
                <tbody>
                  {exam.subjects.map((s) => (
                    <tr key={`${exam.exam_name}-${s.subject_name}`}>
                      <td>{s.subject_name}</td>
                      <td className="mono">{s.score}</td>
                      <td>{s.grade}</td>
                      <td className="mono">{s.points.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>

        <section className="sheet__summary">
          <div className="sheet__summary-box">
            <span className="sheet__label">Overall average</span>
            <strong>{overall.average_score ?? '—'}</strong>
          </div>
          <div className="sheet__summary-box">
            <span className="sheet__label">Cumulative GPA</span>
            <strong>{overall.gpa ?? '—'}</strong>
          </div>
          <div className="sheet__summary-box">
            <span className="sheet__label">Season attendance</span>
            <strong>{attendance.attendance_pct != null ? `${attendance.attendance_pct}%` : '—'}</strong>
            <span className="sheet__hint">
              {attendance.days_present} present of {attendance.days_recorded} recorded days
            </span>
          </div>
        </section>

        <section className="sheet__signoff">
          <div className="sheet__signoff-box">
            <span className="sheet__label">Class teacher remarks</span>
            <div className="sheet__rule" />
            <div className="sheet__rule" />
            <div className="sheet__rule" />
          </div>
          <div className="sheet__signoff-box">
            <span className="sheet__label">Sign-off</span>
            <div className="sheet__rule sheet__rule--short" />
            <span className="sheet__hint">
              {class_teacher?.name ?? 'Class teacher'}
              {class_teacher?.ne_tid ? ` · ${class_teacher.ne_tid}` : class_teacher?.staff_identifier ? ` · ${class_teacher.staff_identifier}` : ''}
            </span>
          </div>
        </section>

        <footer className="sheet__foot">
          Generated {card.generated_at} · NE-EMIS official document · Financial data withheld
          from state authorities
        </footer>
      </article>
    </div>
  );
}
