import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import {
  clearTeacher,
  fetchInstitution,
  fetchTeacher,
  selectInstitution,
  selectTeacher,
} from '../features/schools/schoolSlice';

export default function InstitutionOverview() {
  const { schoolId } = useParams();
  const dispatch = useDispatch();
  const institution = useSelector(selectInstitution);
  const teacher = useSelector(selectTeacher);
  const { activeTeacherId } = useSelector((state) => state.schools);

  useEffect(() => {
    dispatch(fetchInstitution(schoolId));
    dispatch(clearTeacher());
  }, [dispatch, schoolId]);

  if (!institution) {
    return (
      <section className="card">
        <p className="empty">Loading institution…</p>
      </section>
    );
  }

  const { principal } = institution;

  return (
    <div className="stack">
      <section className="card">
        <header className="card__head">
          <h2 className="card__title">{institution.school_name}</h2>
          <span className="card__hint">
            Licence {institution.state_license_number} · {institution.physical_address}
          </span>
        </header>

        <div className="kpi-grid">
          <KpiCard label="Students" value={institution.total_students} tone="brand" />
          <KpiCard label="Teachers" value={institution.total_teachers} tone="info" />
          <KpiCard label="Class tracks" value={institution.total_classes} />
          <KpiCard
            label="Accreditation"
            value={institution.accreditation_status}
            tone={institution.accreditation_status === 'Active' ? 'ok' : 'danger'}
          />
        </div>
      </section>

      <section className="card">
        <header className="card__head">
          <h2 className="card__title">Manager / Principal Profile</h2>
          <span className="card__hint">Registered officer of record</span>
        </header>

        {principal ? (
          <div className="detail-grid">
            <div className="detail-block">
              <h3 className="detail-block__title">Identity</h3>
              <dl className="detail-list">
                <div>
                  <dt>Name</dt>
                  <dd>{principal.name}</dd>
                </div>
                <div>
                  <dt>NE-MID</dt>
                  <dd className="mono">{principal.ne_mid ?? '—'}</dd>
                </div>
                <div>
                  <dt>Designation</dt>
                  <dd>{principal.designation ?? '—'}</dd>
                </div>
              </dl>
            </div>

            <div className="detail-block">
              <h3 className="detail-block__title">Direct contact</h3>
              <dl className="detail-list">
                <div>
                  <dt>Phone</dt>
                  <dd>{principal.phone ?? '—'}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{principal.email ?? '—'}</dd>
                </div>
              </dl>
            </div>

            <div className="detail-block">
              <h3 className="detail-block__title">Qualifications</h3>
              <p className="detail-address">{principal.qualifications ?? '—'}</p>
            </div>
          </div>
        ) : (
          <p className="empty">No principal registered for this institution.</p>
        )}
      </section>

      <section className="card">
        <header className="card__head">
          <h2 className="card__title">Teacher Roster</h2>
          <span className="card__hint">
            {institution.total_teachers} teaching staff — select a name for full details
          </span>
        </header>

        <ul className="roster">
          {institution.teacher_roster.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                className={`roster__item ${activeTeacherId === t.id ? 'is-active' : ''}`}
                onClick={() => dispatch(fetchTeacher(t.id))}
              >
                <span className="roster__name">{t.name}</span>
                <span className="roster__meta mono">{t.ne_tid ?? '—'}</span>
                <Badge status="Active">{t.designation ?? 'Teacher'}</Badge>
              </button>
            </li>
          ))}
          {institution.teacher_roster.length === 0 && (
            <li className="empty">No teaching staff registered.</li>
          )}
        </ul>

        {teacher && (
          <div className="teacher-card">
            <h3>{teacher.name}</h3>
            <dl className="detail-list">
              <div>
                <dt>NE-TID</dt>
                <dd className="mono">{teacher.ne_tid ?? '—'}</dd>
              </div>
              <div>
                <dt>Phone</dt>
                <dd>{teacher.phone ?? '—'}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{teacher.email ?? '—'}</dd>
              </div>
              <div>
                <dt>Qualifications</dt>
                <dd>{teacher.qualifications ?? '—'}</dd>
              </div>
            </dl>

            <div className="teacher-card__cols">
              <div>
                <h4>Assigned subjects</h4>
                <ul className="pill-list">
                  {teacher.assigned_subjects.length === 0 && <li className="empty">Not recorded</li>}
                  {teacher.assigned_subjects.map((s) => (
                    <li key={`${s.subject_code}-${s.class_level}`} className="pill">
                      {s.subject_name}
                      <span className="pill__meta">{s.class_level}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h4>Classroom schedule</h4>
                <ul className="pill-list">
                  {teacher.classroom_schedule.length === 0 && (
                    <li className="empty">No homeroom assigned</li>
                  )}
                  {teacher.classroom_schedule.map((c) => (
                    <li key={c.class_id} className="pill">
                      {c.class_level} {c.class_stream}
                      <span className="pill__meta">{c.room_number ?? '—'}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
