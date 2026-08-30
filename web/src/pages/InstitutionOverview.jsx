import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import TeacherProfileModal from '../components/TeacherProfileModal';
import { api } from '../api/client';
import { selectIsStateAdmin } from '../features/auth/authSlice';
import {
  clearTeacher,
  fetchInstitution,
  fetchTeacher,
  selectInstitution,
  selectTeacher,
} from '../features/schools/schoolSlice';
import { useAcademicStructureUpdates } from '../hooks/useAcademicStructureUpdates';

function toError(error) {
  return error?.message || 'Unable to load the academic breakdown.';
}

/** Read-only cross-school academic view for State Admin and Inspector. */
export default function InstitutionOverview() {
  const { schoolId } = useParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const institution = useSelector(selectInstitution);
  const teacher = useSelector(selectTeacher);
  const isStateAdmin = useSelector(selectIsStateAdmin);
  const [classBreakdown, setClassBreakdown] = useState(null);
  const [sequence, setSequence] = useState(null);
  const [nextValue, setNextValue] = useState('');
  const [showSchoolEditor, setShowSchoolEditor] = useState(false);
  const [schoolForm, setSchoolForm] = useState(null);
  const [savingSchool, setSavingSchool] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refreshInstitution = () => dispatch(fetchInstitution(schoolId));

  useEffect(() => {
    refreshInstitution();
    dispatch(clearTeacher());
    setClassBreakdown(null);
    setSequence(null);
    setShowSchoolEditor(false);
    setSchoolForm(null);
    setError('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, schoolId]);

  useEffect(() => {
    if (!isStateAdmin) return;
    api(`/api/v1/state/schools/${schoolId}/roll-sequence`)
      .then((data) => {
        setSequence(data);
        setNextValue(String(data.next_value));
      })
      .catch((loadError) => setError(toError(loadError)));
  }, [isStateAdmin, schoolId]);

  useEffect(() => {
    if (!institution || showSchoolEditor) return;
    setSchoolForm({
      school_name: institution.school_name ?? '',
      state_license_number: institution.state_license_number ?? '',
      school_code: institution.school_code ?? '',
      proprietor_name: institution.proprietor_name ?? '',
      contact_phone: institution.contact_phone ?? '',
      contact_email: institution.contact_email ?? '',
      physical_address: institution.physical_address ?? '',
      accreditation_status: institution.accreditation_status ?? 'Active',
    });
  }, [institution, showSchoolEditor]);

  useAcademicStructureUpdates((event) => {
    if (String(event.school_id) !== String(schoolId)) return;
    refreshInstitution();
    if (classBreakdown?.class?.id) {
      api(`/api/v1/state/institutions/${schoolId}/classes/${classBreakdown.class.id}/breakdown`)
        .then(setClassBreakdown)
        .catch(() => {});
    }
  });

  const chooseClass = async (classId) => {
    setError('');
    try {
      const data = await api(`/api/v1/state/institutions/${schoolId}/classes/${classId}/breakdown`);
      setClassBreakdown(data);
    } catch (loadError) {
      setError(toError(loadError));
    }
  };

  const updateSequence = async (event) => {
    event.preventDefault();
    setError('');
    try {
      const data = await api(`/api/v1/state/schools/${schoolId}/roll-sequence`, {
        method: 'PATCH',
        body: { next_value: Number(nextValue) },
      });
      setSequence(data);
      setNextValue(String(data.next_value));
      setNotice(`Next roll number is now ${data.next_roll_number}. Existing issued roll numbers remain immutable.`);
    } catch (saveError) {
      setError(toError(saveError));
    }
  };

  const setSchoolField = (field) => (event) => {
    setSchoolForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const updateSchool = async (event) => {
    event.preventDefault();
    if (!schoolForm) return;
    setSavingSchool(true);
    setError('');
    try {
      const response = await api(`/api/v1/state/schools/${schoolId}`, {
        method: 'PATCH',
        body: {
          school_name: schoolForm.school_name.trim(),
          state_license_number: schoolForm.state_license_number.trim(),
          school_code: schoolForm.school_code.trim() || null,
          proprietor_name: schoolForm.proprietor_name.trim() || null,
          contact_phone: schoolForm.contact_phone.trim() || null,
          contact_email: schoolForm.contact_email.trim() || null,
          physical_address: schoolForm.physical_address.trim() || null,
          accreditation_status: schoolForm.accreditation_status,
        },
      });
      setNotice(`${response.school_name} was updated. Public academic directory information is now synchronized.`);
      setShowSchoolEditor(false);
      await refreshInstitution();
    } catch (saveError) {
      setError(toError(saveError));
    } finally {
      setSavingSchool(false);
    }
  };

  if (!institution) {
    return <section className="card"><p className="empty">Loading institution…</p></section>;
  }

  const { principal } = institution;
  return (
    <div className="stack">
      <section className="card">
        <header className="card__head">
          <div className="institution-title-row"><span className="code-badge">{institution.school_code}</span><h2 className="card__title">{institution.school_name}</h2></div>
          <span className="card__hint">Licence {institution.state_license_number} · {institution.physical_address}</span>
        </header>
        <div className="kpi-grid">
          <KpiCard label="Students" value={institution.total_students} tone="brand" />
          <KpiCard label="Teachers" value={institution.total_teachers} tone="info" />
          <KpiCard label="Class streams" value={institution.total_classes} />
          <KpiCard label="Accreditation" value={institution.accreditation_status} tone={institution.accreditation_status === 'Active' ? 'ok' : 'danger'} />
        </div>
      </section>

      {error && <p className="alert alert--danger">{error}</p>}
      {notice && <p className="alert alert--ok">{notice}</p>}

      {isStateAdmin && (
        <section className="card state-admin-card">
          <header className="card__head card__head--row">
            <div><h2 className="card__title">School identity management</h2><span className="card__hint">State Admin public school configuration only. Private billing contacts stay in the School Manager workspace.</span></div>
            <button type="button" className="btn btn--secondary" onClick={() => setShowSchoolEditor((value) => !value)}>{showSchoolEditor ? 'Cancel' : 'Edit school'}</button>
          </header>
          {showSchoolEditor && schoolForm && (
            <form className="school-create-form state-school-form" onSubmit={updateSchool}>
              <div className="student-form__grid">
                <label className="field"><span className="field__label">School name</span><input className="input" value={schoolForm.school_name} onChange={setSchoolField('school_name')} required /></label>
                <label className="field"><span className="field__label">State licence number</span><input className="input" value={schoolForm.state_license_number} onChange={setSchoolField('state_license_number')} required /></label>
                <label className="field"><span className="field__label">Two-letter code</span><input className="input" value={schoolForm.school_code} onChange={setSchoolField('school_code')} maxLength="2" required /><span className="field__hint">Locked after the first student roll is issued.</span></label>
                <label className="field"><span className="field__label">Accreditation</span><select className="input" value={schoolForm.accreditation_status} onChange={setSchoolField('accreditation_status')}><option>Active</option><option>Probation</option><option>Suspended</option></select></label>
                <label className="field"><span className="field__label">Proprietor</span><input className="input" value={schoolForm.proprietor_name} onChange={setSchoolField('proprietor_name')} /></label>
                <label className="field"><span className="field__label">School phone</span><input className="input" value={schoolForm.contact_phone} onChange={setSchoolField('contact_phone')} /></label>
                <label className="field"><span className="field__label">School email</span><input className="input" type="email" value={schoolForm.contact_email} onChange={setSchoolField('contact_email')} /></label>
                <label className="field field--wide"><span className="field__label">Address</span><textarea className="input" rows="2" value={schoolForm.physical_address} onChange={setSchoolField('physical_address')} /></label>
              </div>
              <div className="student-form__foot"><button className="btn btn--primary" disabled={savingSchool}>{savingSchool ? 'Saving…' : 'Save public school details'}</button></div>
            </form>
          )}
        </section>
      )}

      {isStateAdmin && sequence && (
        <section className="card state-admin-card">
          <header className="card__head"><h2 className="card__title">Roll number oversight</h2><span className="card__hint">State Admin control. This is the next unissued roll number, not a student record.</span></header>
          <form className="sequence-form" onSubmit={updateSequence}>
            <span className="sequence-form__prefix">{sequence.school_code}-</span>
            <input className="input" type="number" min="1" value={nextValue} onChange={(event) => setNextValue(event.target.value)} required />
            <button className="btn btn--primary">Update next sequence</button>
          </form>
        </section>
      )}

      <section className="card">
        <header className="card__head"><h2 className="card__title">Manager / Principal profile</h2><span className="card__hint">Registered officer of record</span></header>
        {principal ? (
          <div className="detail-grid">
            <div className="detail-block"><h3 className="detail-block__title">Identity</h3><dl className="detail-list"><div><dt>Name</dt><dd>{principal.name}</dd></div><div><dt>Staff ID</dt><dd className="mono">{principal.ne_mid ?? '—'}</dd></div><div><dt>Designation</dt><dd>{principal.designation ?? '—'}</dd></div></dl></div>
            <div className="detail-block"><h3 className="detail-block__title">Direct contact</h3><dl className="detail-list"><div><dt>Phone</dt><dd>{principal.phone ?? '—'}</dd></div><div><dt>Email</dt><dd>{principal.email ?? '—'}</dd></div></dl></div>
            <div className="detail-block"><h3 className="detail-block__title">Qualifications</h3><p className="detail-address">{principal.qualifications ?? '—'}</p></div>
          </div>
        ) : <p className="empty">No principal registered for this institution.</p>}
      </section>

      <section className="card">
        <header className="card__head"><h2 className="card__title">Teachers</h2><span className="card__hint">Select a teacher for profile, homeroom, and class-specific subject assignments.</span></header>
        <ul className="roster">
          {institution.teacher_roster.map((person) => (
            <li key={person.id}>
              <button type="button" className="roster__item" onClick={() => dispatch(fetchTeacher(person.id))}>
                <span className="roster__name">{person.name}</span>
                <span className="roster__meta mono">{person.ne_tid ?? '—'} · {person.assignment_count ?? 0} assignments</span>
                <Badge status="Active">{person.designation ?? 'Teacher'}</Badge>
              </button>
            </li>
          ))}
          {institution.teacher_roster.length === 0 && <li className="empty">No teaching staff registered.</li>}
        </ul>
      </section>

      <section className="card">
        <header className="card__head"><h2 className="card__title">Class 1–12 academic breakdown</h2><span className="card__hint">Choose a stream to view student roll numbers and the full subject-teacher roster.</span></header>
        <div className="class-picker">
          {(institution.classes ?? []).map((klass) => (
            <button key={klass.id} type="button" className={`class-picker__item ${classBreakdown?.class?.id === klass.id ? 'is-active' : ''}`} onClick={() => chooseClass(klass.id)}>
              <strong>{klass.class_label}</strong><span>{klass.student_count} students · {klass.room_number ?? 'Room not set'}</span>
            </button>
          ))}
        </div>
        {classBreakdown && (
          <div className="state-class-breakdown">
            <h3>{classBreakdown.class.class_label}</h3>
            <div className="grid grid--2">
              <div><h4>Enrolled students</h4>{classBreakdown.students.length === 0 ? <p className="empty">No active students.</p> : <div className="table-wrap"><table className="table"><thead><tr><th>Roll number</th><th>Student</th></tr></thead><tbody>{classBreakdown.students.map((student) => <tr key={student.id}><td className="mono">{student.roll_number}</td><td><button type="button" className="link-button" onClick={() => navigate(`/state/lookup?roll=${encodeURIComponent(student.roll_number)}`)} aria-label={`Open ${student.name} full profile`}>{student.name}</button></td></tr>)}</tbody></table></div>}</div>
              <div><h4>All subjects & teachers</h4><div className="table-wrap"><table className="table"><thead><tr><th>Subject</th><th>Assigned teacher</th></tr></thead><tbody>{classBreakdown.subjects.map((subject) => <tr key={subject.id}><td>{subject.subject_name}<br /><span className="mono">{subject.subject_code}</span></td><td>{subject.teacher ? <button className="link-button" type="button" onClick={() => dispatch(fetchTeacher(subject.teacher.id))}>{subject.teacher.name}</button> : <span className="muted">Unassigned</span>}</td></tr>)}</tbody></table></div></div>
            </div>
          </div>
        )}
      </section>

      <TeacherProfileModal teacher={teacher} onClose={() => dispatch(clearTeacher())} />
    </div>
  );
}
