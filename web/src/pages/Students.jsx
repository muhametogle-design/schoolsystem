import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Accordion from '../components/Accordion';
import Badge from '../components/Badge';
import StudentForm from '../components/StudentForm';
import {
  fetchStudentsByClass,
  selectClasses,
  selectTotalStudents,
} from '../features/students/studentSlice';
import { selectIsManager, selectIsTeacher } from '../features/auth/authSlice';

export default function Students() {
  const dispatch = useDispatch();
  const classes = useSelector(selectClasses);
  const total = useSelector(selectTotalStudents);
  const isManager = useSelector(selectIsManager);
  const isTeacher = useSelector(selectIsTeacher);

  const [query, setQuery] = useState('');
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = () => dispatch(fetchStudentsByClass({ q: query }));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch]);

  const onCreated = () => load();

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Student Register</h2>
            <span className="card__hint">
              {total} active learners grouped by class — Class 1 to Class 12
            </span>
          </div>
          <div className="toolbar">
            <input
              className="input input--search"
              placeholder="Search name or roll number…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') load();
              }}
            />
            <button type="button" className="btn btn--ghost" onClick={load}>
              Search
            </button>
            {(isManager || isTeacher) && (
              <button type="button" className="btn btn--primary" onClick={() => setDrawerOpen(true)}>
                Create New Student
              </button>
            )}
          </div>
        </header>

        <div className="accordion-group">
          {classes.map((group) => (
            <Accordion
              key={group.class_level}
              title={group.class_level}
              meta={`${group.student_count} enrolled`}
              defaultOpen={group.student_count > 0 && group.class_level === 'Class 1'}
            >
              {group.student_count === 0 ? (
                <p className="empty">No students enrolled in {group.class_level}.</p>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Roll no.</th>
                      <th>Student</th>
                      <th>Age</th>
                      <th>Gender</th>
                      <th>Fee standing</th>
                      <th>Guardian</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {group.students.map((student) => (
                      <tr key={student.ne_sid}>
                        <td className="mono">{student.roll_number ?? student.ne_sid}</td>
                        <td>
                          <Link
                            className="student-name-link"
                            to={`/school/students/${student.ne_sid}`}
                            aria-label={`Open full profile for ${student.full_legal_name}`}
                          >
                            {student.full_legal_name}
                          </Link>
                        </td>
                        <td>{student.age ?? '—'}</td>
                        <td>{student.gender ?? '—'}</td>
                        <td>
                          <Badge status={student.fee_status}>
                            {student.fee_status?.replace(/_/g, ' ')}
                          </Badge>
                        </td>
                        <td>{student.guardian?.name ?? '—'}</td>
                        <td className="table__actions">
                          <Link
                            className="btn btn--small"
                            to={`/school/students/${student.ne_sid}`}
                          >
                            Open profile
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Accordion>
          ))}

          {classes.length === 0 && <p className="empty">No class tracks found for this school.</p>}
        </div>
      </section>

      {drawerOpen && (
        <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)}>
          <aside className="drawer" onClick={(e) => e.stopPropagation()}>
            <StudentForm
              mode="drawer"
              title="Create New Student"
              onClose={() => setDrawerOpen(false)}
              onCreated={onCreated}
            />
          </aside>
        </div>
      )}
    </div>
  );
}
