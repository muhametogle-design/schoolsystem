import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import {
  clearNotice,
  fetchStudent,
  selectSelectedStudent,
  updateStudent,
} from '../features/students/studentSlice';
import { fetchClasses, selectClasses } from '../features/schools/schoolSlice';
import { selectIsManager, selectIsTeacher } from '../features/auth/authSlice';

const FEE_OPTIONS = ['PAID', 'PENDING', 'NOT_PAID', 'SCHOLARSHIP'];

export default function StudentDetails() {
  const { neSid } = useParams();
  const dispatch = useDispatch();
  const student = useSelector(selectSelectedStudent);
  const classes = useSelector(selectClasses);
  const { saving, error, notice } = useSelector((state) => state.students);
  const canEdit = useSelector(selectIsManager) || useSelector(selectIsTeacher);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    dispatch(fetchStudent(neSid));
    dispatch(fetchClasses());
  }, [dispatch, neSid]);

  useEffect(() => {
    if (student) {
      setDraft({
        first_name: student.first_name ?? '',
        last_name: student.last_name ?? '',
        current_class_id: student.current_class_id ?? '',
        date_of_birth: student.date_of_birth ?? '',
        gender: student.gender ?? '',
        guardian_name: student.guardian?.name ?? '',
        guardian_relationship: student.guardian?.relationship ?? '',
        guardian_phone: student.guardian?.phone ?? '',
        guardian_email: student.guardian?.email ?? '',
        emergency_contact_phone: student.guardian?.emergency_phone ?? '',
        physical_address: student.physical_address ?? '',
        fee_status: student.fee_status ?? 'NOT_PAID',
      });
    }
  }, [student]);

  if (!student) {
    return (
      <section className="card">
        <p className="empty">Loading student profile…</p>
      </section>
    );
  }

  const set = (key) => (event) => setDraft((d) => ({ ...d, [key]: event.target.value }));

  const save = async (event) => {
    event.preventDefault();
    const payload = {
      ...draft,
      current_class_id: draft.current_class_id ? Number(draft.current_class_id) : null,
      date_of_birth: draft.date_of_birth || null,
      gender: draft.gender || null,
    };
    const result = await dispatch(updateStudent({ neSid, payload }));
    if (updateStudent.fulfilled.match(result)) setEditing(false);
  };

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">{student.full_legal_name}</h2>
            <span className="card__hint mono">Roll number: {student.roll_number ?? student.ne_sid}</span>
          </div>
          <div className="toolbar">
            <Link className="btn btn--ghost" to={`/school/students/${student.ne_sid}/report-card`}>
              Print Report Card
            </Link>
            {canEdit && !editing && (
              <button type="button" className="btn btn--primary" onClick={() => setEditing(true)}>
                Edit details
              </button>
            )}
          </div>
        </header>

        {notice && <p className="alert alert--ok">{notice}</p>}
        {error && <p className="alert alert--danger">{error}</p>}

        {!editing ? (
          <div className="detail-grid">
            <div className="detail-block">
              <h3 className="detail-block__title">Identity</h3>
              <dl className="detail-list">
                <div>
                  <dt>Full legal name</dt>
                  <dd>{student.full_legal_name}</dd>
                </div>
                <div>
                  <dt>Roll number</dt>
                  <dd className="mono">{student.roll_number ?? student.ne_sid}</dd>
                </div>
                <div>
                  <dt>Age</dt>
                  <dd>{student.age != null ? `${student.age} years` : '—'}</dd>
                </div>
                <div>
                  <dt>Date of birth</dt>
                  <dd>{student.date_of_birth ?? '—'}</dd>
                </div>
                <div>
                  <dt>Gender</dt>
                  <dd>{student.gender ?? '—'}</dd>
                </div>
              </dl>
            </div>

            <div className="detail-block">
              <h3 className="detail-block__title">Enrolment</h3>
              <dl className="detail-list">
                <div>
                  <dt>Class level</dt>
                  <dd>{student.class_label ?? '—'}</dd>
                </div>
                <div>
                  <dt>Enrolled on</dt>
                  <dd>{student.enrollment_date ?? '—'}</dd>
                </div>
                <div>
                  <dt>Fee standing</dt>
                  <dd>
                    <Badge status={student.fee_status}>
                      {student.fee_status?.replace(/_/g, ' ')}
                    </Badge>
                  </dd>
                </div>
                <div>
                  <dt>Attendance</dt>
                  <dd>
                    {student.attendance?.attendance_pct != null
                      ? `${student.attendance.attendance_pct}% (${student.attendance.days_present}/${student.attendance.days_recorded})`
                      : '—'}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="detail-block">
              <h3 className="detail-block__title">Physical address</h3>
              <p className="detail-address">{student.physical_address ?? 'No address on file'}</p>
            </div>

            <div className="detail-block">
              <h3 className="detail-block__title">Parent / Guardian</h3>
              <div className="contact-card">
                <span className="contact-card__name">{student.guardian?.name ?? '—'}</span>
                <span className="contact-card__rel">
                  {student.guardian?.relationship ?? 'Relationship not recorded'}
                </span>
                <dl className="detail-list detail-list--tight">
                  <div>
                    <dt>Phone</dt>
                    <dd>{student.guardian?.phone ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Email</dt>
                    <dd>{student.guardian?.email ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Emergency</dt>
                    <dd>{student.guardian?.emergency_phone ?? '—'}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
        ) : (
          <form className="student-form student-form--inline" onSubmit={save}>
            <div className="student-form__grid">
              <label className="field">
                <span className="field__label">First name</span>
                <input className="input" value={draft.first_name} onChange={set('first_name')} required />
              </label>
              <label className="field">
                <span className="field__label">Last name</span>
                <input className="input" value={draft.last_name} onChange={set('last_name')} required />
              </label>
              <label className="field">
                <span className="field__label">Class</span>
                <select
                  className="input"
                  value={draft.current_class_id}
                  onChange={set('current_class_id')}
                >
                  <option value="">Unassigned</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.class_level} {c.class_stream}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field__label">Date of birth</span>
                <input
                  className="input"
                  type="date"
                  value={draft.date_of_birth}
                  onChange={set('date_of_birth')}
                />
              </label>
              <label className="field">
                <span className="field__label">Gender</span>
                <select className="input" value={draft.gender} onChange={set('gender')}>
                  <option value="">Not recorded</option>
                  <option>Male</option>
                  <option>Female</option>
                  <option>Other</option>
                </select>
              </label>
              <label className="field">
                <span className="field__label">Fee status</span>
                <select className="input" value={draft.fee_status} onChange={set('fee_status')}>
                  {FEE_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field field--wide">
                <span className="field__label">Physical address</span>
                <input
                  className="input"
                  value={draft.physical_address}
                  onChange={set('physical_address')}
                />
              </label>
              <label className="field">
                <span className="field__label">Guardian name</span>
                <input
                  className="input"
                  value={draft.guardian_name}
                  onChange={set('guardian_name')}
                />
              </label>
              <label className="field">
                <span className="field__label">Relationship</span>
                <input
                  className="input"
                  value={draft.guardian_relationship}
                  onChange={set('guardian_relationship')}
                />
              </label>
              <label className="field">
                <span className="field__label">Guardian phone</span>
                <input
                  className="input"
                  value={draft.guardian_phone}
                  onChange={set('guardian_phone')}
                />
              </label>
              <label className="field">
                <span className="field__label">Guardian email</span>
                <input
                  className="input"
                  type="email"
                  value={draft.guardian_email}
                  onChange={set('guardian_email')}
                />
              </label>
              <label className="field">
                <span className="field__label">Emergency contact</span>
                <input
                  className="input"
                  value={draft.emergency_contact_phone}
                  onChange={set('emergency_contact_phone')}
                />
              </label>
            </div>

            <footer className="student-form__foot">
              <button type="submit" className="btn btn--primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => {
                  setEditing(false);
                  dispatch(clearNotice());
                }}
              >
                Cancel
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
  );
}
