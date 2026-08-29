import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { createStudent } from '../features/students/studentSlice';
import { fetchClasses, selectClasses } from '../features/schools/schoolSlice';

const EMPTY = {
  first_name: '',
  last_name: '',
  current_class_id: '',
  date_of_birth: '',
  gender: '',
  guardian_name: '',
  guardian_relationship: '',
  guardian_phone: '',
  guardian_email: '',
  physical_address: '',
  fee_status: 'NOT_PAID',
};

const FEE_OPTIONS = ['PAID', 'PENDING', 'NOT_PAID', 'SCHOLARSHIP'];

/**
 * Registration form. Rendered inside a drawer on the Students page and inside
 * a modal on the Attendance / Marks sheets so teachers can register a learner
 * without leaving the grading sheet.
 */
export default function StudentForm({ mode = 'drawer', title, onClose, onCreated }) {
  const dispatch = useDispatch();
  const classes = useSelector(selectClasses);
  const [values, setValues] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (classes.length === 0) dispatch(fetchClasses());
  }, [classes.length, dispatch]);

  const set = (key) => (event) => setValues((v) => ({ ...v, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const payload = {
      ...values,
      current_class_id: Number(values.current_class_id),
      date_of_birth: values.date_of_birth || null,
      gender: values.gender || null,
    };

    const result = await dispatch(createStudent(payload));
    setSaving(false);

    if (createStudent.fulfilled.match(result)) {
      setValues(EMPTY);
      if (onCreated) onCreated(result.payload);
      if (onClose) onClose();
    } else {
      setError(result.error.message);
    }
  };

  return (
    <form className={`student-form student-form--${mode}`} onSubmit={submit}>
      <header className="student-form__head">
        <h2>{title ?? 'Register New Student'}</h2>
        {onClose && (
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Close
          </button>
        )}
      </header>

      <div className="student-form__grid">
        <label className="field">
          <span className="field__label">First name</span>
          <input className="input" value={values.first_name} onChange={set('first_name')} required />
        </label>
        <label className="field">
          <span className="field__label">Last name</span>
          <input className="input" value={values.last_name} onChange={set('last_name')} required />
        </label>

        <label className="field">
          <span className="field__label">Class</span>
          <select
            className="input"
            value={values.current_class_id}
            onChange={set('current_class_id')}
            required
          >
            <option value="">Select class…</option>
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
            value={values.date_of_birth}
            onChange={set('date_of_birth')}
          />
        </label>

        <label className="field">
          <span className="field__label">Gender</span>
          <select className="input" value={values.gender} onChange={set('gender')}>
            <option value="">Not recorded</option>
            <option>Male</option>
            <option>Female</option>
            <option>Other</option>
          </select>
        </label>

        <label className="field">
          <span className="field__label">Fee status</span>
          <select className="input" value={values.fee_status} onChange={set('fee_status')}>
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
            value={values.physical_address}
            onChange={set('physical_address')}
            placeholder="House no., district, city"
          />
        </label>

        <label className="field">
          <span className="field__label">Guardian name</span>
          <input
            className="input"
            value={values.guardian_name}
            onChange={set('guardian_name')}
          />
        </label>

        <label className="field">
          <span className="field__label">Relationship</span>
          <input
            className="input"
            value={values.guardian_relationship}
            onChange={set('guardian_relationship')}
            placeholder="Mother, Father, Uncle…"
          />
        </label>

        <label className="field">
          <span className="field__label">Guardian phone</span>
          <input className="input" value={values.guardian_phone} onChange={set('guardian_phone')} />
        </label>

        <label className="field">
          <span className="field__label">Guardian email</span>
          <input
            className="input"
            type="email"
            value={values.guardian_email}
            onChange={set('guardian_email')}
          />
        </label>
      </div>

      {error && <p className="alert alert--danger">{error}</p>}

      <footer className="student-form__foot">
        <button type="submit" className="btn btn--primary" disabled={saving}>
          {saving ? 'Registering…' : 'Register student'}
        </button>
        <span className="student-form__note">
          An immutable NE-SID is issued automatically on save.
        </span>
      </footer>
    </form>
  );
}
