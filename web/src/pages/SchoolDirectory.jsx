import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { api } from '../api/client';
import { selectIsStateAdmin } from '../features/auth/authSlice';
import { useAcademicStructureUpdates } from '../hooks/useAcademicStructureUpdates';

const EMPTY_SCHOOL = {
  school_name: '',
  state_license_number: '',
  school_code: '',
  proprietor_name: '',
  contact_phone: '',
  contact_email: '',
  physical_address: '',
  manager_first_name: '',
  manager_last_name: '',
  manager_email: '',
  manager_password: '',
  streams: 'A',
};

function detail(error) {
  return error?.message || 'Unable to load the school directory.';
}

/** State-wide active school directory and State Admin tenant provisioning. */
export default function SchoolDirectory() {
  const isStateAdmin = useSelector(selectIsStateAdmin);
  const [schools, setSchools] = useState([]);
  const [form, setForm] = useState(EMPTY_SCHOOL);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await api('/api/v1/state/institutions');
      setSchools(data.institutions ?? []);
    } catch (loadError) {
      setError(detail(loadError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useAcademicStructureUpdates(() => load());

  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const suggestCode = async () => {
    if (!form.school_name.trim()) return;
    try {
      const response = await api(`/api/v1/state/school-code-suggestion?school_name=${encodeURIComponent(form.school_name.trim())}`);
      setForm((current) => ({ ...current, school_code: response.school_code }));
    } catch (suggestError) {
      // The backend repeats all validation on submit; keep this as a convenience.
      setError(detail(suggestError));
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const response = await api('/api/v1/state/schools', {
        method: 'POST',
        body: {
          ...form,
          school_code: form.school_code.trim() || null,
          proprietor_name: form.proprietor_name.trim() || null,
          contact_phone: form.contact_phone.trim() || null,
          contact_email: form.contact_email.trim() || null,
          physical_address: form.physical_address.trim() || null,
          streams: form.streams.split(',').map((stream) => stream.trim()).filter(Boolean),
        },
      });
      setForm(EMPTY_SCHOOL);
      setShowCreate(false);
      setNotice(`${response.school_name} was provisioned as ${response.school_code}: Class 1–12, 10 subjects per level, 8 setup teachers, assignments, and roll sequence are ready. The School Manager can complete private billing setup in the tenant workspace.`);
      await load();
    } catch (saveError) {
      setError(detail(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">School directory</h2>
            <span className="card__hint">Academic-only visibility across active private-school tenants. Open a school to inspect staff, classes, subjects, and roll-number rosters.</span>
          </div>
          {isStateAdmin && <button className="btn btn--primary" type="button" onClick={() => setShowCreate((value) => !value)}>{showCreate ? 'Cancel' : 'Add school'}</button>}
        </header>
        {error && <p className="alert alert--danger">{error}</p>}
        {notice && <p className="alert alert--ok">{notice}</p>}

        {showCreate && (
          <form className="school-create-form" onSubmit={submit}>
            <header className="school-create-form__head"><h3>Provision new school tenant</h3><span>State Admin only</span></header>
            <div className="student-form__grid">
              <label className="field"><span className="field__label">School name</span><input className="input" value={form.school_name} onChange={set('school_name')} onBlur={suggestCode} required /></label>
              <label className="field"><span className="field__label">State licence number</span><input className="input" value={form.state_license_number} onChange={set('state_license_number')} required placeholder="SOL/PS/2026/006" /></label>
              <label className="field"><span className="field__label">Two-letter school code</span><input className="input" value={form.school_code} onChange={set('school_code')} maxLength="2" placeholder="Auto" /><span className="field__hint">Auto-assigned if blank; used in student roll numbers.</span></label>
              <label className="field"><span className="field__label">Streams</span><input className="input" value={form.streams} onChange={set('streams')} required placeholder="A, B" /><span className="field__hint">Comma-separated; each gets Class 1–12.</span></label>
              <label className="field"><span className="field__label">Proprietor</span><input className="input" value={form.proprietor_name} onChange={set('proprietor_name')} /></label>
              <label className="field"><span className="field__label">School phone</span><input className="input" value={form.contact_phone} onChange={set('contact_phone')} /></label>
              <label className="field"><span className="field__label">School email</span><input className="input" type="email" value={form.contact_email} onChange={set('contact_email')} /></label>
              <label className="field field--wide"><span className="field__label">Address</span><textarea className="input" rows="2" value={form.physical_address} onChange={set('physical_address')} /></label>
              <label className="field"><span className="field__label">Manager first name</span><input className="input" value={form.manager_first_name} onChange={set('manager_first_name')} required /></label>
              <label className="field"><span className="field__label">Manager last name</span><input className="input" value={form.manager_last_name} onChange={set('manager_last_name')} required /></label>
              <label className="field"><span className="field__label">Manager email</span><input className="input" type="email" value={form.manager_email} onChange={set('manager_email')} required /></label>
              <label className="field"><span className="field__label">Manager initial password</span><input className="input" type="password" minLength="8" value={form.manager_password} onChange={set('manager_password')} required /></label>
            </div>
            <div className="student-form__foot"><button className="btn btn--primary" disabled={saving}>{saving ? 'Provisioning…' : 'Provision complete tenant'}</button></div>
          </form>
        )}

        {loading ? <p className="empty">Loading registered schools…</p> : (
          <div className="directory-grid">
            {schools.map((school) => (
              <Link className="directory-card" key={school.id} to={`/state/institutions/${school.id}`}>
                <div className="directory-card__head"><span className="code-badge">{school.school_code}</span><strong>{school.school_name}</strong></div>
                <span>{school.state_license_number}</span>
                <span>{school.physical_address ?? 'Address not recorded'}</span>
                <div className="directory-card__meta"><span>{school.student_count} students</span><span>{school.teacher_count} teachers</span><span>{school.accreditation_status}</span></div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
