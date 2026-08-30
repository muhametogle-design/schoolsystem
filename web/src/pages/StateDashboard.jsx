import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import {
  fetchClassLevels,
  fetchLiveAttendance,
  selectClassLevels,
  selectLiveAttendance,
  setLiveClassLevel,
} from '../features/attendance/attendanceSlice';
import { selectIsStateAdmin } from '../features/auth/authSlice';
import { fetchInstitutions, selectInstitutions } from '../features/schools/schoolSlice';
import { useAcademicStructureUpdates } from '../hooks/useAcademicStructureUpdates';

/** State-wide, academic-only live attendance monitor. */
export default function StateDashboard() {
  const dispatch = useDispatch();
  const institutions = useSelector(selectInstitutions);
  const records = useSelector(selectLiveAttendance);
  const classLevels = useSelector(selectClassLevels);
  const isStateAdmin = useSelector(selectIsStateAdmin);
  const [classLevel, setClassLevel] = useState('');
  const [schoolId, setSchoolId] = useState('');

  const reload = () => {
    dispatch(fetchInstitutions());
    dispatch(fetchClassLevels());
    dispatch(fetchLiveAttendance({ classLevel: classLevel || undefined, schoolId: schoolId || undefined }));
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    dispatch(fetchLiveAttendance({ classLevel: classLevel || undefined, schoolId: schoolId || undefined }));
  }, [dispatch, classLevel, schoolId]);

  useAcademicStructureUpdates(() => reload());

  const present = records.filter((record) => record.status === 'Present').length;
  const absent = records.filter((record) => record.status === 'Absent').length;
  const pct = records.length ? Math.round((present / records.length) * 1000) / 10 : null;
  const nonCompliant = institutions.filter((institution) => institution.accreditation_status !== 'Active').length;

  return (
    <div className="stack">
      <section className="kpi-grid">
        <KpiCard label="Registered institutions" value={institutions.length} tone="brand" />
        <KpiCard label="Roster entries today" value={records.length} hint={classLevel ? `Filtered to ${classLevel}` : 'All classes'} />
        <KpiCard label="Present today" value={pct != null ? `${pct}%` : '—'} hint={`${present} present · ${absent} absent`} tone={(pct ?? 0) >= 85 ? 'ok' : 'warn'} />
        <KpiCard label="Non-active institutions" value={nonCompliant} hint="Accreditation flagged" tone={nonCompliant > 0 ? 'danger' : 'ok'} />
      </section>

      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Live attendance monitor</h2>
            <span className="card__hint">Read-only feed across every licensed institution. Private billing information is never included.</span>
          </div>
          <div className="toolbar">
            {isStateAdmin && <Link className="btn btn--primary" to="/state/directory">Add or manage schools</Link>}
            <select className="input" value={schoolId} onChange={(event) => setSchoolId(event.target.value)}>
              <option value="">All institutions</option>
              {institutions.map((institution) => <option key={institution.id} value={institution.id}>{institution.school_code} · {institution.school_name}</option>)}
            </select>
            <select className="input" value={classLevel} onChange={(event) => { setClassLevel(event.target.value); dispatch(setLiveClassLevel(event.target.value || null)); }}>
              <option value="">All classes</option>
              {classLevels.map((level) => <option key={level} value={level}>{level}</option>)}
            </select>
          </div>
        </header>

        {records.length === 0 ? <p className="empty">No roster entries recorded for this selection.</p> : (
          <div className="table-wrap"><table className="table"><thead><tr><th>Institution</th><th>Class</th><th>Roll no.</th><th>Student</th><th>Status</th></tr></thead><tbody>{records.slice(0, 200).map((record, index) => <tr key={`${record.roll_number ?? record.national_student_id}-${index}`}><td>{record.school_name}</td><td>{record.class}</td><td className="mono">{record.roll_number ?? record.national_student_id}</td><td>{record.student}</td><td><Badge status={record.status}>{record.status}</Badge></td></tr>)}</tbody></table></div>
        )}
      </section>
    </div>
  );
}
