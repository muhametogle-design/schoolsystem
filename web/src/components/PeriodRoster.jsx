import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import Badge from './Badge';

const todayISO = () => new Date().toISOString().slice(0, 10);
const STATUSES = ['Present', 'Absent', 'Late', 'Excused'];

/**
 * Quick 'Mark Present / Absent / Late' roster for one timetable period.
 *
 * Used by the Teacher Dashboard and the teacher attendance view. The backend
 * enforces the timetable matrix: marking is only accepted for classes the
 * signed-in teacher is assigned to.
 */
export default function PeriodRoster({ classId, classLevel, date = todayISO(), onSaved }) {
  const [students, setStudents] = useState([]);
  const [statuses, setStatuses] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [groups, attendance] = await Promise.all([
        api(`/api/v1/school/students/by-class`),
        api(`/api/v1/school/attendance?class_id=${classId}&date=${date}`),
      ]);
      const roster = (groups.classes ?? [])
        .flatMap((group) => group.students ?? [])
        .filter((student) => student.current_class_id === classId);
      setStudents(roster);
      const base = {};
      roster.forEach((student) => {
        base[student.id] = attendance.statuses?.[student.id] ?? 'Present';
      });
      setStatuses(base);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [classId, date]);

  useEffect(() => {
    load();
  }, [load]);

  const mark = async (studentId, status) => {
    const next = { ...statuses, [studentId]: status };
    setStatuses(next);
    setSaving(true);
    setError(null);
    try {
      await api('/api/v1/school/attendance', {
        method: 'POST',
        body: {
          date,
          class_id: classId,
          entries: students.map((student) => ({ student_id: student.id, status: next[student.id] ?? 'Present' })),
        },
      });
      setSavedAt(new Date().toLocaleTimeString());
      onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="empty">Loading roster…</p>;
  if (error && students.length === 0) return <p className="alert alert--danger">{error}</p>;
  if (students.length === 0) return <p className="empty">No active students enrolled in {classLevel ?? 'this class'}.</p>;

  return (
    <div className="period-roster">
      {error && <p className="alert alert--danger">{error}</p>}
      <div className="table-scroll">
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
            {students.map((student) => {
              const current = statuses[student.id] ?? 'Present';
              return (
                <tr key={student.id}>
                  <td className="mono">{student.roll_number ?? student.ne_sid}</td>
                  <td>{student.full_legal_name}</td>
                  <td><Badge status={current}>{current}</Badge></td>
                  <td>
                    <div className="status-picker">
                      {STATUSES.map((status) => (
                        <button
                          key={status}
                          type="button"
                          className={`chip ${current === status ? 'is-active' : ''}`}
                          disabled={saving}
                          onClick={() => mark(student.id, status)}
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
      </div>
      {savedAt && <p className="period-roster__saved">Roster saved · {savedAt}</p>}
    </div>
  );
}
