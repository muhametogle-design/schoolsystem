import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Badge from '../components/Badge';
import { KpiCard } from '../components/Charts';
import {
  fetchClassLevels,
  fetchLiveAttendance,
  selectAttendanceTrend,
  selectClassLevels,
  selectLiveAttendance,
  setLiveClassLevel,
} from '../features/attendance/attendanceSlice';
import { fetchInstitutions, selectInstitutions } from '../features/schools/schoolSlice';

export default function StateDashboard() {
  const dispatch = useDispatch();
  const institutions = useSelector(selectInstitutions);
  const records = useSelector(selectLiveAttendance);
  const classLevels = useSelector(selectClassLevels);
  const [classLevel, setClassLevel] = useState('');
  const [schoolId, setSchoolId] = useState('');

  useEffect(() => {
    dispatch(fetchInstitutions());
    dispatch(fetchClassLevels());
  }, [dispatch]);

  useEffect(() => {
    dispatch(fetchLiveAttendance({ classLevel: classLevel || undefined, schoolId: schoolId || undefined }));
  }, [dispatch, classLevel, schoolId]);

  const present = records.filter((r) => r.status === 'Present').length;
  const absent = records.filter((r) => r.status === 'Absent').length;
  const pct = records.length ? Math.round((present / records.length) * 1000) / 10 : null;
  const redAlarms = institutions.filter((i) => i.accreditation_status !== 'Active').length;

  return (
    <div className="stack">
      <section className="kpi-grid">
        <KpiCard label="Registered Institutions" value={institutions.length} tone="brand" />
        <KpiCard
          label="Roster Entries Today"
          value={records.length}
          hint={classLevel ? `Filtered to ${classLevel}` : 'All classes'}
        />
        <KpiCard
          label="Present Today"
          value={pct != null ? `${pct}%` : '—'}
          hint={`${present} present · ${absent} absent`}
          tone={(pct ?? 0) >= 85 ? 'ok' : 'warn'}
        />
        <KpiCard
          label="Non-Active Institutions"
          value={redAlarms}
          hint="Accreditation flagged"
          tone={redAlarms > 0 ? 'danger' : 'ok'}
        />
      </section>

      <section className="card">
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Live Attendance Monitor</h2>
            <span className="card__hint">
              Read-only feed across every licensed institution
            </span>
          </div>
          <div className="toolbar">
            <select
              className="input"
              value={schoolId}
              onChange={(e) => setSchoolId(e.target.value)}
            >
              <option value="">All institutions</option>
              {institutions.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.school_name}
                </option>
              ))}
            </select>

            <select
              className="input"
              value={classLevel}
              onChange={(e) => {
                setClassLevel(e.target.value);
                dispatch(setLiveClassLevel(e.target.value || null));
              }}
            >
              <option value="">All classes</option>
              {classLevels.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
        </header>

        {records.length === 0 ? (
          <p className="empty">No roster entries recorded for this selection.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Institution</th>
                <th>Class</th>
                <th>NE-SID</th>
                <th>Student</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {records.slice(0, 200).map((r, idx) => (
                <tr key={`${r.national_student_id}-${idx}`}>
                  <td>{r.school_name}</td>
                  <td>{r.class}</td>
                  <td className="mono">{r.national_student_id}</td>
                  <td>{r.student}</td>
                  <td>
                    <Badge status={r.status}>{r.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
