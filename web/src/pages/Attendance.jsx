import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Accordion from '../components/Accordion';
import Badge from '../components/Badge';
import StudentForm from '../components/StudentForm';
import { fetchStudentsByClass, selectClasses } from '../features/students/studentSlice';
import { fetchSubjects, selectSubjects } from '../features/schools/schoolSlice';
import {
  fetchAttendance,
  saveAttendance,
  selectAttendanceRecords,
  submitRoster,
} from '../features/attendance/attendanceSlice';
import { selectIsTeacher, selectIsManager } from '../features/auth/authSlice';

const todayISO = () => new Date().toISOString().slice(0, 10);

/**
 * Attendance sheet.
 *
 * Structure follows the brief: Class 1-12 accordion -> subject accordion ->
 * student list. Attendance itself is recorded per student per day (the backend
 * roster is class-scoped), so the subject level organises the sheet the way a
 * subject teacher works through it.
 */
export default function Attendance() {
  const dispatch = useDispatch();
  const classGroups = useSelector(selectClasses);
  const subjects = useSelector(selectSubjects);
  const records = useSelector(selectAttendanceRecords);
  const { saving, notice, error } = useSelector((state) => state.attendance);
  const isTeacher = useSelector(selectIsTeacher);
  const isManager = useSelector(selectIsManager);

  const [date, setDate] = useState(todayISO());
  const [openClass, setOpenClass] = useState(null);
  const [quickAdd, setQuickAdd] = useState(false);

  useEffect(() => {
    dispatch(fetchStudentsByClass());
  }, [dispatch]);

  const selectedGroup = useMemo(
    () => classGroups.find((g) => g.class_level === openClass) ?? null,
    [classGroups, openClass]
  );

  useEffect(() => {
    if (openClass) {
      dispatch(fetchSubjects({ classLevel: openClass }));
    }
  }, [openClass, dispatch]);

  const classId = selectedGroup?.students?.[0]?.current_class_id ?? null;

  useEffect(() => {
    if (classId) dispatch(fetchAttendance({ date, classId }));
  }, [classId, date, dispatch]);

  const setStatus = (studentId, status) => {
    const entries = selectedGroup.students.map((s) => ({
      student_id: s.id,
      status: records[s.id] ?? 'Present',
    }));
    const next = entries.map((e) => (e.student_id === studentId ? { ...e, status } : e));
    dispatch(saveAttendance({ date, classId, entries: next }));
  };

  const submit = () => dispatch(submitRoster({ date }));

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Daily Attendance Roster</h2>
            <span className="card__hint">
              Submit before the 12:00 deadline to stay compliant
            </span>
          </div>
          <div className="toolbar">
            <input
              className="input"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
            {isManager && (
              <button type="button" className="btn btn--primary" onClick={submit}>
                Submit daily roster
              </button>
            )}
          </div>
        </header>

        {notice && <p className="alert alert--ok">{notice}</p>}
        {error && <p className="alert alert--danger">{error}</p>}

        <div className="accordion-group">
          {classGroups.map((group) => (
            <Accordion
              key={group.class_level}
              title={group.class_level}
              meta={`${group.student_count} enrolled`}
              defaultOpen={openClass === group.class_level}
              onOpen={() => setOpenClass(group.class_level)}
              right={
                isTeacher && (
                  <button
                    type="button"
                    className="btn btn--small"
                    onClick={() => {
                      setOpenClass(group.class_level);
                      setQuickAdd(true);
                    }}
                  >
                    Quick Add Student
                  </button>
                )
              }
            >
              {group.student_count === 0 ? (
                <p className="empty">No students enrolled in {group.class_level}.</p>
              ) : (
                <div className="accordion-group accordion-group--nested">
                  {(group.class_level === openClass ? subjects : []).map((subject) => (
                    <Accordion
                      key={subject.id}
                      level={2}
                      title={subject.subject_name}
                      meta={`${group.student_count} students`}
                    >
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Roll no.</th>
                            <th>Student</th>
                            <th>Status</th>
                            <th>Mark</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.students.map((student) => {
                            const current = records[student.id] ?? 'Present';
                            return (
                              <tr key={student.ne_sid}>
                                <td className="mono">{student.roll_number ?? student.ne_sid}</td>
                                <td>{student.full_legal_name}</td>
                                <td>
                                  <Badge status={current}>{current}</Badge>
                                </td>
                                <td>
                                  <div className="status-picker">
                                    {['Present', 'Absent', 'Late', 'Excused'].map((status) => (
                                      <button
                                        key={status}
                                        type="button"
                                        className={`chip ${current === status ? 'is-active' : ''}`}
                                        disabled={saving}
                                        onClick={() => setStatus(student.id, status)}
                                      >
                                        {status}
                                      </button>
                                    ))}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </Accordion>
                  ))}

                  {group.class_level !== openClass && (
                    <p className="empty">
                      Expand {group.class_level} to load its subjects and begin marking.
                    </p>
                  )}
                </div>
              )}
            </Accordion>
          ))}
        </div>
      </section>

      {quickAdd && (
        <div className="modal-backdrop" onClick={() => setQuickAdd(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <StudentForm
              mode="modal"
              title="Quick Add Student"
              onClose={() => setQuickAdd(false)}
              onCreated={() => dispatch(fetchStudentsByClass())}
            />
          </div>
        </div>
      )}
    </div>
  );
}
