import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { api } from '../api/client';
import { selectIsManager } from '../features/auth/authSlice';
import TeacherProfileModal from '../components/TeacherProfileModal';

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  phone: '',
  designation: 'Teacher',
  qualifications: '',
  bio: '',
  is_active: true,
};

function message(error) {
  return error?.message || 'Unable to save this teacher.';
}

/** Teacher directory with School Admin CRUD and authoritative assignments. */
export default function Teachers() {
  const isManager = useSelector(selectIsManager);
  const [teachers, setTeachers] = useState([]);
  const [selectedTeacher, setSelectedTeacher] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    try {
      const data = await api('/api/v1/school/teachers');
      setTeachers(data.teachers ?? []);
    } catch (loadError) {
      setError(message(loadError));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setForm((current) => ({ ...current, [key]: value }));
  };

  const beginCreate = () => {
    setError('');
    setNotice('');
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const beginEdit = (teacher) => {
    setError('');
    setNotice('');
    setEditingId(teacher.id);
    setForm({
      first_name: teacher.first_name ?? '',
      last_name: teacher.last_name ?? '',
      email: teacher.email ?? '',
      password: '',
      phone: teacher.phone ?? '',
      designation: teacher.designation ?? 'Teacher',
      qualifications: teacher.qualifications ?? '',
      bio: teacher.bio ?? '',
      is_active: teacher.is_active !== false,
    });
    setShowForm(true);
  };

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = { ...form };
      if (editingId && !payload.password) delete payload.password;
      const response = await api(
        editingId ? `/api/v1/school/teachers/${editingId}` : '/api/v1/school/teachers',
        { method: editingId ? 'PATCH' : 'POST', body: payload },
      );
      setShowForm(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await load();
      setNotice(editingId ? 'Teacher profile updated.' : `Teacher added: ${response.teacher.name}`);
    } catch (saveError) {
      setError(message(saveError));
    } finally {
      setSaving(false);
    }
  };

  const openTeacher = async (teacherId) => {
    try {
      const data = await api(`/api/v1/school/teachers/${teacherId}`);
      setSelectedTeacher(data.teacher);
    } catch (loadError) {
      setError(message(loadError));
    }
  };

  const removeTeacher = async (teacher) => {
    if (!window.confirm(`Remove ${teacher.name}? Their curriculum assignments will be marked unassigned.`)) return;
    try {
      await api(`/api/v1/school/teachers/${teacher.id}`, { method: 'DELETE' });
      if (selectedTeacher?.id === teacher.id) setSelectedTeacher(null);
      await load();
      setNotice(`${teacher.name} was removed. Reassign any now-vacant subjects from Classes.`);
    } catch (deleteError) {
      setError(message(deleteError));
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Teacher management</h2>
            <span className="card__hint">
              Teacher profiles and their class-specific subject assignments. Select a name for the complete profile.
            </span>
          </div>
          {isManager && <button type="button" className="btn btn--primary" onClick={beginCreate}>Add teacher</button>}
        </header>

        {error && <p className="alert alert--danger">{error}</p>}
        {notice && <p className="alert alert--ok">{notice}</p>}

        {showForm && (
          <form className="teacher-form" onSubmit={submit}>
            <header className="teacher-form__head">
              <h3>{editingId ? 'Edit teacher' : 'Add teacher'}</h3>
              <button type="button" className="btn btn--small" onClick={() => setShowForm(false)}>Cancel</button>
            </header>
            <div className="student-form__grid">
              <label className="field"><span className="field__label">First name</span><input className="input" value={form.first_name} onChange={set('first_name')} required /></label>
              <label className="field"><span className="field__label">Last name</span><input className="input" value={form.last_name} onChange={set('last_name')} required /></label>
              <label className="field"><span className="field__label">Email</span><input className="input" type="email" value={form.email} onChange={set('email')} required /></label>
              <label className="field"><span className="field__label">{editingId ? 'New password (optional)' : 'Initial password'}</span><input className="input" type="password" value={form.password} minLength="8" onChange={set('password')} required={!editingId} /></label>
              <label className="field"><span className="field__label">Phone</span><input className="input" value={form.phone} onChange={set('phone')} /></label>
              <label className="field"><span className="field__label">Designation</span><input className="input" value={form.designation} onChange={set('designation')} /></label>
              <label className="field field--wide"><span className="field__label">Qualifications</span><textarea className="input" rows="2" value={form.qualifications} onChange={set('qualifications')} /></label>
              <label className="field field--wide"><span className="field__label">Professional profile</span><textarea className="input" rows="3" value={form.bio} onChange={set('bio')} /></label>
              {editingId && <label className="field field--checkbox"><input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> <span>Active staff account</span></label>}
            </div>
            <div className="student-form__foot"><button className="btn btn--primary" disabled={saving}>{saving ? 'Saving…' : editingId ? 'Save changes' : 'Create teacher'}</button></div>
          </form>
        )}

        {teachers.length === 0 ? (
          <p className="empty">No teacher profiles registered yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Teacher</th><th>Staff ID</th><th>Assignments</th><th>Status</th>{isManager && <th>Actions</th>}</tr></thead>
              <tbody>
                {teachers.map((teacher) => (
                  <tr key={teacher.id}>
                    <td>
                      <button type="button" className="link-button" onClick={() => openTeacher(teacher.id)}>{teacher.name}</button>
                      <br /><span className="muted">{teacher.designation ?? 'Teacher'}</span>
                    </td>
                    <td className="mono">{teacher.ne_tid ?? teacher.staff_identifier ?? '—'}</td>
                    <td>{teacher.assignment_count ?? teacher.assignments?.length ?? 0} class-subject slots</td>
                    <td><span className={teacher.is_active ? 'status-dot status-dot--ok' : 'status-dot status-dot--muted'}>{teacher.is_active ? 'Active' : 'Inactive'}</span></td>
                    {isManager && <td className="table__actions"><button type="button" className="btn btn--small" onClick={() => beginEdit(teacher)}>Edit</button>{' '}<button type="button" className="btn btn--small btn--danger" onClick={() => removeTeacher(teacher)}>Remove</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <TeacherProfileModal
        teacher={selectedTeacher}
        onClose={() => setSelectedTeacher(null)}
        onTeacherChange={(updated) => {
          setSelectedTeacher(updated);
          setTeachers((current) =>
            current.map((row) => (row.id === updated.id ? { ...row, photo_data: updated.photo_data } : row))
          );
        }}
      />
    </div>
  );
}
