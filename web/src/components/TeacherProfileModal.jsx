import { useEffect } from 'react';

/**
 * Reusable, keyboard-friendly detailed teaching-profile view. The assignments
 * list is authoritative: it comes from the class/subject/teacher mapping API,
 * not from historical grade entries.
 */
export default function TeacherProfileModal({ teacher, onClose }) {
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  if (!teacher) return null;
  const assignments = teacher.assignments ?? teacher.assigned_subjects ?? [];
  const schedule = teacher.classroom_schedule ?? [];

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="modal teacher-profile-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="teacher-profile-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="card__head card__head--row">
          <div>
            <h2 id="teacher-profile-title" className="card__title">{teacher.name}</h2>
            <span className="card__hint">
              {teacher.designation ?? 'Teacher'} · <span className="mono">{teacher.ne_tid ?? teacher.staff_identifier ?? '—'}</span>
            </span>
          </div>
          <button type="button" className="btn btn--small" onClick={onClose} aria-label="Close teacher profile">
            Close
          </button>
        </header>

        <div className="detail-grid">
          <div className="detail-block">
            <h3 className="detail-block__title">Contact</h3>
            <dl className="detail-list">
              <div><dt>Email</dt><dd>{teacher.email ?? '—'}</dd></div>
              <div><dt>Phone</dt><dd>{teacher.phone ?? '—'}</dd></div>
              <div><dt>Status</dt><dd>{teacher.is_active === false ? 'Inactive' : 'Active'}</dd></div>
            </dl>
          </div>
          <div className="detail-block">
            <h3 className="detail-block__title">Qualifications</h3>
            <p className="detail-address">{teacher.qualifications ?? '—'}</p>
          </div>
          {teacher.bio && (
            <div className="detail-block detail-block--wide">
              <h3 className="detail-block__title">Professional profile</h3>
              <p className="detail-address">{teacher.bio}</p>
            </div>
          )}
        </div>

        <section className="teacher-profile-modal__section">
          <h3>Class-specific subject assignments</h3>
          {assignments.length === 0 ? (
            <p className="empty">No class/subject assignments are currently recorded.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Class</th><th>Subject</th><th>Code</th></tr>
                </thead>
                <tbody>
                  {assignments.map((assignment) => (
                    <tr key={assignment.assignment_id ?? `${assignment.class_id}-${assignment.subject_id ?? assignment.subject_code}`}>
                      <td>{assignment.class_label ?? `${assignment.class_level} ${assignment.class_stream ?? ''}`}</td>
                      <td>{assignment.subject_name}</td>
                      <td className="mono">{assignment.subject_code ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="teacher-profile-modal__section">
          <h3>Homeroom responsibilities</h3>
          {schedule.length === 0 ? (
            <p className="empty">No homeroom class assigned.</p>
          ) : (
            <ul className="pill-list">
              {schedule.map((klass) => (
                <li className="pill" key={klass.class_id}>
                  {klass.class_label ?? `${klass.class_level} ${klass.class_stream}`}
                  <span className="pill__meta">{klass.room_number ?? '—'}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>
    </div>
  );
}
