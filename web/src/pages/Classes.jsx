import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { selectIsManager } from '../features/auth/authSlice';
import TeacherProfileModal from '../components/TeacherProfileModal';

const CLASS_LEVELS = Array.from({ length: 12 }, (_, index) => `Class ${index + 1}`);

function errorMessage(error) {
  return error?.message || 'Something went wrong. Please try again.';
}

/** School-side Class 1–12 curriculum, roster, and subject-teacher mapping. */
export default function Classes() {
  const isManager = useSelector(selectIsManager);
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [selectedClassId, setSelectedClassId] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [selectedTeacher, setSelectedTeacher] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [showAddClass, setShowAddClass] = useState(false);
  const [showAddSubject, setShowAddSubject] = useState(false);
  const [newClass, setNewClass] = useState({ class_level: 'Class 1', class_stream: 'A', room_number: '' });
  const [newSubject, setNewSubject] = useState({ class_level: 'Class 1', subject_code: '', subject_name: '', teacher_id: '' });

  const load = async () => {
    setLoading(true);
    try {
      const [classData, teacherData] = await Promise.all([
        api('/api/v1/school/classes'),
        api('/api/v1/school/teachers'),
      ]);
      setClasses(classData.classes ?? []);
      setTeachers(teacherData.teachers ?? []);
      if (!selectedClassId && classData.classes?.length) {
        await chooseClass(classData.classes[0].id);
      } else if (selectedClassId) {
        await loadBreakdown(selectedClassId);
      }
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  };

  const loadBreakdown = async (classId) => {
    const data = await api(`/api/v1/school/classes/${classId}/breakdown`);
    setBreakdown(data);
  };

  const chooseClass = async (classId) => {
    setSelectedClassId(classId);
    setError('');
    try {
      await loadBreakdown(classId);
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  };

  useEffect(() => {
    load();
    // Fetch on route entry; management mutations below refresh locally.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveAssignment = async (subjectId, teacherId) => {
    if (!teacherId || !selectedClassId) return;
    setSaving(true);
    setError('');
    try {
      await api(`/api/v1/school/classes/${selectedClassId}/subjects/${subjectId}/assignment`, {
        method: 'PUT',
        body: { teacher_id: Number(teacherId) },
      });
      await loadBreakdown(selectedClassId);
      setNotice('Subject teacher assignment saved. State academic views update automatically.');
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  const openTeacher = async (teacherId) => {
    try {
      const data = await api(`/api/v1/school/teachers/${teacherId}`);
      setSelectedTeacher(data.teacher);
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  };

  const createClass = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const created = await api('/api/v1/school/classes', {
        method: 'POST',
        body: { ...newClass, room_number: newClass.room_number || null },
      });
      setShowAddClass(false);
      setNewClass({ class_level: 'Class 1', class_stream: 'A', room_number: '' });
      await load();
      await chooseClass(created.id);
      setNotice(`${created.class_label} created with its class-level curriculum.`);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  const createSubject = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api('/api/v1/school/subjects', {
        method: 'POST',
        body: {
          ...newSubject,
          teacher_id: newSubject.teacher_id ? Number(newSubject.teacher_id) : null,
        },
      });
      setShowAddSubject(false);
      setNewSubject({ class_level: 'Class 1', subject_code: '', subject_name: '', teacher_id: '' });
      if (selectedClassId) await loadBreakdown(selectedClassId);
      setNotice('Subject added to every stream at that class level. Assign a teacher where needed.');
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  const editSubject = async (subject) => {
    const subjectName = window.prompt('Subject name', subject.subject_name);
    if (subjectName === null || !subjectName.trim()) return;
    const subjectCode = window.prompt('Subject code', subject.subject_code);
    if (subjectCode === null || !subjectCode.trim()) return;
    setSaving(true);
    try {
      await api(`/api/v1/school/subjects/${subject.id}`, {
        method: 'PATCH',
        body: { subject_name: subjectName.trim(), subject_code: subjectCode.trim() },
      });
      await loadBreakdown(selectedClassId);
      setNotice('Subject details updated.');
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Classes, subjects & teaching assignments</h2>
            <span className="card__hint">
              Select a Class 1–12 stream to see its enrolled students, roll numbers, and full curriculum.
            </span>
          </div>
          {isManager && (
            <div className="toolbar">
              <button className="btn" type="button" onClick={() => setShowAddSubject((value) => !value)}>
                {showAddSubject ? 'Cancel subject' : 'Add subject'}
              </button>
              <button className="btn btn--primary" type="button" onClick={() => setShowAddClass((value) => !value)}>
                {showAddClass ? 'Cancel class' : 'Add class stream'}
              </button>
            </div>
          )}
        </header>

        {error && <p className="alert alert--danger">{error}</p>}
        {notice && <p className="alert alert--ok">{notice}</p>}

        {showAddClass && (
          <form className="management-form" onSubmit={createClass}>
            <label className="field">
              <span className="field__label">Class level</span>
              <select className="input" value={newClass.class_level} onChange={(e) => setNewClass({ ...newClass, class_level: e.target.value })}>
                {CLASS_LEVELS.map((level) => <option key={level}>{level}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Stream</span>
              <input className="input" value={newClass.class_stream} required maxLength="50" onChange={(e) => setNewClass({ ...newClass, class_stream: e.target.value })} placeholder="A" />
            </label>
            <label className="field">
              <span className="field__label">Room</span>
              <input className="input" value={newClass.room_number} onChange={(e) => setNewClass({ ...newClass, room_number: e.target.value })} placeholder="R-7B" />
            </label>
            <button className="btn btn--primary" disabled={saving}>Create class</button>
          </form>
        )}

        {showAddSubject && (
          <form className="management-form management-form--subject" onSubmit={createSubject}>
            <label className="field">
              <span className="field__label">Class level</span>
              <select className="input" value={newSubject.class_level} onChange={(e) => setNewSubject({ ...newSubject, class_level: e.target.value })}>
                {CLASS_LEVELS.map((level) => <option key={level}>{level}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Subject code</span>
              <input className="input" value={newSubject.subject_code} required onChange={(e) => setNewSubject({ ...newSubject, subject_code: e.target.value })} placeholder="ICT" />
            </label>
            <label className="field">
              <span className="field__label">Subject name</span>
              <input className="input" value={newSubject.subject_name} required onChange={(e) => setNewSubject({ ...newSubject, subject_name: e.target.value })} placeholder="Information Technology" />
            </label>
            <label className="field">
              <span className="field__label">Initial teacher</span>
              <select className="input" value={newSubject.teacher_id} onChange={(e) => setNewSubject({ ...newSubject, teacher_id: e.target.value })}>
                <option value="">Assign later</option>
                {teachers.filter((teacher) => teacher.is_active).map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}
              </select>
            </label>
            <button className="btn btn--primary" disabled={saving}>Add subject</button>
          </form>
        )}

        {loading ? (
          <p className="empty">Loading class structure…</p>
        ) : (
          <div className="class-picker" aria-label="Class streams">
            {classes.map((klass) => (
              <button
                key={klass.id}
                type="button"
                className={`class-picker__item ${selectedClassId === klass.id ? 'is-active' : ''}`}
                onClick={() => chooseClass(klass.id)}
              >
                <strong>{klass.class_label}</strong>
                <span>{klass.student_count} students · {klass.room_number ?? 'Room not set'}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      {breakdown && (
        <section className="card">
          <header className="card__head card__head--row">
            <div>
              <h2 className="card__title">{breakdown.class.class_label}</h2>
              <span className="card__hint">
                {breakdown.class.student_count} enrolled students · {breakdown.subjects.length} subjects · {breakdown.unassigned_subject_count} unassigned
              </span>
            </div>
            {breakdown.unassigned_subject_count > 0 && <span className="alert-inline alert-inline--warn">Some subjects need a teacher</span>}
          </header>

          <div className="grid grid--2">
            <div className="class-breakdown__section">
              <h3>Enrolled students & roll numbers</h3>
              {breakdown.students.length === 0 ? <p className="empty">No active students enrolled in this class.</p> : (
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Roll number</th><th>Student</th></tr></thead>
                    <tbody>{breakdown.students.map((student) => <tr key={student.id}><td className="mono">{student.roll_number}</td><td><Link className="student-name-link" to={`/school/students/${encodeURIComponent(student.roll_number ?? student.national_student_id)}`}>{student.name}</Link></td></tr>)}</tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="class-breakdown__section">
              <h3>Subjects & assigned teachers</h3>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Subject</th><th>Teacher</th>{isManager && <th>Assign</th>}</tr></thead>
                  <tbody>
                    {breakdown.subjects.map((subject) => (
                      <tr key={subject.id}>
                        <td><strong>{subject.subject_name}</strong><br /><span className="mono">{subject.subject_code}</span></td>
                        <td>
                          {subject.teacher ? (
                            <button type="button" className="link-button" onClick={() => openTeacher(subject.teacher.id)}>{subject.teacher.name}</button>
                          ) : <span className="muted">Unassigned</span>}
                          {isManager && <button type="button" className="link-button link-button--quiet" onClick={() => editSubject(subject)}>Edit subject</button>}
                        </td>
                        {isManager && (
                          <td>
                            <select
                              className="input input--compact"
                              value={subject.teacher?.id ?? ''}
                              disabled={saving}
                              aria-label={`Assign teacher for ${subject.subject_name}`}
                              onChange={(event) => saveAssignment(subject.id, event.target.value)}
                            >
                              <option value="">Choose teacher…</option>
                              {teachers.filter((teacher) => teacher.is_active).map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}
                            </select>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      )}

      <TeacherProfileModal teacher={selectedTeacher} onClose={() => setSelectedTeacher(null)} />
    </div>
  );
}
