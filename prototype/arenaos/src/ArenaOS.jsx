import React, { useState } from 'react';

// Mock Database State
const INITIAL_TEACHERS = [
  {
    id: 'T-402',
    pin: '1234',
    name: 'Ms. Fadumo Hassan',
    department: 'STEM',
    assignedSubjects: [
      { id: 'SUB-101', name: 'Mathematics', classGrade: 'Class 11 (Form 3)', period: 'Period 3 (10:00 AM)' },
      { id: 'SUB-102', name: 'Physics', classGrade: 'Class 11 (Form 3)', period: 'Period 5 (01:00 PM)' }
    ]
  },
  {
    id: 'T-409',
    pin: '5678',
    name: 'Mr. Jama Farah',
    department: 'Humanities',
    assignedSubjects: [
      { id: 'SUB-201', name: 'Somali Literature', classGrade: 'Class 8', period: 'Period 1 (08:00 AM)' }
    ]
  }
];

const INITIAL_SYLLABUS = [
  {
    id: 'SYL-101',
    classGrade: 'Class 11 (Form 3)',
    subject: 'Mathematics',
    teacherId: 'T-402',
    target: 85,
    deadline: '2026-10-15',
    units: [
      { id: 'U1', title: 'Quadratic Equations & Functions', covered: true },
      { id: 'U2', title: 'Polynomial Theorems & Division', covered: true },
      { id: 'U3', title: 'Introductory Calculus & Limits', covered: false },
      { id: 'U4', title: 'Trigonometric Identities', covered: false }
    ]
  },
  {
    id: 'SYL-102',
    classGrade: 'Class 11 (Form 3)',
    subject: 'Physics',
    teacherId: 'T-402',
    target: 80,
    deadline: '2026-10-20',
    units: [
      { id: 'U1', title: 'Kinematics in 2D', covered: true },
      { id: 'U2', title: 'Newtonian Dynamics & Friction', covered: true },
      { id: 'U3', title: 'Work, Energy, and Power', covered: false }
    ]
  },
  {
    id: 'SYL-201',
    classGrade: 'Class 8',
    subject: 'Somali Literature',
    teacherId: 'T-409',
    target: 90,
    deadline: '2026-11-01',
    units: [
      { id: 'U1', title: 'Classical Somali Poetry & Meter', covered: true },
      { id: 'U2', title: 'Modern Prose & Storytelling', covered: true }
    ]
  }
];

const INITIAL_STUDENTS = [
  { id: 'NG-10023', name: 'Ahmed Mohamed Farah', classGrade: 'Class 11 (Form 3)' },
  { id: 'NG-10045', name: 'Fartun Ali Roble', classGrade: 'Class 11 (Form 3)' },
  { id: 'NG-10089', name: 'Hassan Abdi Nur', classGrade: 'Class 11 (Form 3)' }
];

// [prototype-fix 3] The attendance register was keyed to a literal '2026-09-01'
// in two places (the writer and the reader), so the demo silently rotted the day
// it was authored. One derived key for today keeps both sides in step. The real
// pages read the date from a picker and pass it to /api/…/roster.
const SESSION_DATE = new Date().toISOString().slice(0, 10);

// [prototype-fix 9] Every label in the pasted markup floated free of its input
// (no htmlFor/id pair) and the Subject Name label was missing Tailwind's `block`
// class the others have — an unnoticed copy/paste divergence. Pairing labels with
// controls fixes the accessibility gap and lets the behavioural tests drive the
// form the way a screen reader does.
const AUTH_FIELD_IDS = { identifier: 'auth-identifier', secret: 'auth-secret' };

// [prototype-fix 6] Four taps, matching web/src/pages/TeacherDashboard.jsx.
const ATTENDANCE_STATUSES = ['Present', 'Absent', 'Late', 'Excused'];

const statusActiveClass = (st) =>
  st === 'Present'
    ? 'bg-emerald-600 text-white'
    : st === 'Absent'
    ? 'bg-red-600 text-white'
    : st === 'Late'
    ? 'bg-amber-600 text-white'
    : 'bg-sky-600 text-white';

export default function ArenaOS() {
  // Authentication State
  const [currentUser, setCurrentUser] = useState(null); // null | { role: 'manager' | 'teacher', data: object }
  const [loginId, setLoginId] = useState('');
  const [loginPin, setLoginPin] = useState('');
  const [loginRole, setLoginRole] = useState('teacher'); // 'teacher' | 'manager'
  const [authError, setAuthError] = useState('');

  // Domain Data States
  const [syllabusList, setSyllabusList] = useState(INITIAL_SYLLABUS);
  const [attendanceRecords, setAttendanceRecords] = useState({}); // { 'SUB-101_2026-09-01': { 'NG-10023': 'Present' } }

  // [prototype-fix 1] The modal used to hold a *copy* of the row
  // (setActiveModalSyllabus(item)), so every unit toggle re-rendered the card
  // list behind it while the checklist kept rendering the frozen snapshot and
  // the boxes snapped back. Storing the id and deriving the live row fixes it.
  const [activeModalSyllabusId, setActiveModalSyllabus] = useState(null);

  // New Subject Form State (Manager CRUD)
  const [showAddSubjectForm, setShowAddSubjectForm] = useState(false);
  const [newSubject, setNewSubject] = useState({ classGrade: 'Class 11 (Form 3)', subject: '', teacherId: 'T-402', target: 80, deadline: '2026-11-15' });

  // Handle Authentication
  const handleLogin = (e) => {
    e.preventDefault();
    setAuthError('');

    if (loginRole === 'manager') {
      // [prototype-fix 7] Same trim/case-insensitive treatment the teacher branch
      // already got, so a stray space or "Admin" doesn't look like a bad password.
      if (loginId.trim().toUpperCase() === 'ADMIN' && loginPin === 'admin123') {
        setCurrentUser({ role: 'manager', data: { name: 'School Manager (Admin)' } });
        return;
      }
      setAuthError('Invalid Manager Credentials. Try admin / admin123');
    } else {
      const teacher = INITIAL_TEACHERS.find(t => t.id.toUpperCase() === loginId.trim().toUpperCase() && t.pin === loginPin);
      if (teacher) {
        setCurrentUser({ role: 'teacher', data: teacher });
      } else {
        setAuthError('Invalid Staff ID or PIN. Try T-402 / 1234');
      }
    }
  };

  const handleLogout = () => {
    setCurrentUser(null);
    setLoginId('');
    setLoginPin('');
    setAuthError('');
    // [prototype-fix 10] The role tab and the open CRUD form survived logout, so
    // a manager signing out and then trying a teacher account landed on the
    // *Manager* tab and got "Invalid Manager Credentials" for valid staff IDs.
    // Reset to the default tab (as the real Login.jsx does) and close the form.
    setLoginRole('teacher');
    setShowAddSubjectForm(false);
  };

  // Toggle Topic Covered Checkbox (Manager Action)
  const handleToggleTopic = (syllabusId, unitId) => {
    setSyllabusList(prev => prev.map(item => {
      if (item.id === syllabusId) {
        const updatedUnits = item.units.map(u => u.id === unitId ? { ...u, covered: !u.covered } : u);
        return { ...item, units: updatedUnits };
      }
      return item;
    }));
  };

  // Calculate percentage covered based on units
  const calculateProgress = (units) => {
    if (!units || units.length === 0) return 0;
    const coveredCount = units.filter(u => u.covered).length;
    return Math.round((coveredCount / units.length) * 100);
  };

  // [prototype-fix 8] Managers could previously never grow a plan's unit list —
  // a new subject arrived with one hard-coded "Chapter 1" and no way to add the
  // rest, which made the 0% progress bar a dead end.
  const handleAddUnit = (syllabusId) => {
    setSyllabusList((prev) =>
      prev.map((item) => {
        if (item.id !== syllabusId) return item;
        const nextNumber = item.units.length + 1;
        return {
          ...item,
          units: [...item.units, { id: `U${nextNumber}`, title: `Chapter ${nextNumber}: Untitled Unit`, covered: false }],
        };
      })
    );
  };

  // [prototype-fix 4] Attendance is now recorded for the same day the roster is
  // read from, instead of a frozen literal.
  const handleMarkAttendance = (subjectId, studentId, status) => {
    const key = `${subjectId}_${SESSION_DATE}`;
    setAttendanceRecords(prev => ({
      ...prev,
      [key]: {
        ...(prev[key] || {}),
        [studentId]: status
      }
    }));
  };

  const handleMarkAllPresent = (subjectId, roster) => {
    const key = `${subjectId}_${SESSION_DATE}`;
    setAttendanceRecords((prev) => ({
      ...prev,
      [key]: { ...(prev[key] || {}), ...Object.fromEntries(roster.map((s) => [s.id, 'Present'])) },
    }));
  };

  // [prototype-fix 4] `target` and `deadline` were already in `newSubject` state
  // but had no inputs, so every created row silently inherited 80 / 2026-11-15.
  // Add New Subject to Syllabus (Manager Action)
  const handleAddSubject = (e) => {
    e.preventDefault();
    // [prototype-fix 5] Date.now().toString().slice(-3) reused ids constantly
    // (three rolling digits), which made React keys collide and the modal target
    // the wrong row. Monotonic suffix over the live list instead.
    const nextNumber = syllabusList.reduce((max, item) => {
      const parsed = Number.parseInt(String(item.id).replace(/\D/g, ''), 10);
      return Number.isNaN(parsed) ? max : Math.max(max, parsed);
    }, 0);
    const newEntry = {
      ...newSubject,
      id: `SYL-${100 + nextNumber + 1}`,
      units: [{ id: 'U1', title: 'Chapter 1: Foundations', covered: false }],
    };
    setSyllabusList([...syllabusList, newEntry]);
    setNewSubject({ classGrade: 'Class 11 (Form 3)', subject: '', teacherId: 'T-402', target: 80, deadline: '2026-11-15' });
    setShowAddSubjectForm(false);
  };

  // [prototype-fix 1] The open modal must read the live row, not a snapshot.
  const activeSyllabus = activeModalSyllabusId
    ? syllabusList.find((item) => item.id === activeModalSyllabusId) ?? null
    : null;

  // [prototype-fix 8] A subject a manager creates must show up on the assigned
  // teacher's restricted portal, otherwise "CRUD" only ever moved the manager's
  // own board. The real app persists the assignment row; here we derive the view.
  const teacherSubjects =
    currentUser && currentUser.role === 'teacher'
      ? (() => {
          const owned = syllabusList.filter((item) => item.teacherId === currentUser.data.id);
          const seen = new Set(currentUser.data.assignedSubjects.map((s) => `${s.name}|${s.classGrade}`));
          const extra = owned
            .filter((item) => !seen.has(`${item.subject}|${item.classGrade}`))
            .map((item, index) => ({
              id: item.id,
              name: item.subject,
              classGrade: item.classGrade,
              period: `Unscheduled period ${index + 1}`,
            }));
          return [...currentUser.data.assignedSubjects, ...extra];
        })()
      : [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col">
      
      {/* GLOBAL HEADER */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex justify-between items-center sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 font-bold px-2.5 py-1 rounded text-xs text-white tracking-widest uppercase">
            ARENA OS
          </div>
          <span className="font-semibold text-sm text-slate-200">School Operations System</span>
        </div>

        {currentUser && (
          <div className="flex items-center gap-4 text-xs">
            <span className="bg-slate-800 text-slate-300 px-3 py-1.5 rounded-full border border-slate-700">
              Logged in as: <strong className="text-white">{currentUser.data.name}</strong> ({currentUser.role.toUpperCase()})
            </span>
            <button 
              onClick={handleLogout} 
              className="bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-lg transition-colors font-medium"
            >
              Logout
            </button>
          </div>
        )}
      </header>

      {/* BODY CONTENT */}
      {!currentUser ? (
        
        /* ------------------------------------------------------------------ */
        /* AUTHENTICATION PORTAL                                              */
        /* ------------------------------------------------------------------ */
        <main className="flex-1 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl max-w-md w-full space-y-6 shadow-2xl">
            <div className="text-center space-y-1">
              <h1 className="text-2xl font-bold tracking-tight">System Login</h1>
              <p className="text-slate-400 text-xs">Access your role-restricted portal</p>
            </div>

            {/* Role Switcher */}
            <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800">
              <button 
                onClick={() => setLoginRole('teacher')}
                className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${loginRole === 'teacher' ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
              >
                Teacher Portal
              </button>
              <button 
                onClick={() => setLoginRole('manager')}
                className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${loginRole === 'manager' ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
              >
                School Manager
              </button>
            </div>

            {authError && (
              <div className="bg-red-950/60 border border-red-800 text-red-300 text-xs p-3 rounded-lg text-center">
                {authError}
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1">
                <label htmlFor={AUTH_FIELD_IDS.identifier} className="text-xs uppercase font-semibold text-slate-400">
                  {loginRole === 'teacher' ? 'Staff ID' : 'Username'}
                </label>
                <input 
                  id={AUTH_FIELD_IDS.identifier}
                  type="text" 
                  required
                  placeholder={loginRole === 'teacher' ? 'e.g. T-402' : 'admin'}
                  value={loginId}
                  onChange={(e) => setLoginId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white focus:border-blue-600 outline-none"
                />
              </div>

              <div className="space-y-1">
                <label htmlFor={AUTH_FIELD_IDS.secret} className="text-xs uppercase font-semibold text-slate-400">
                  {loginRole === 'teacher' ? 'PIN Code' : 'Password'}
                </label>
                <input 
                  id={AUTH_FIELD_IDS.secret}
                  type="password" 
                  required
                  placeholder={loginRole === 'teacher' ? '••••' : '••••••••'}
                  value={loginPin}
                  onChange={(e) => setLoginPin(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white focus:border-blue-600 outline-none"
                />
              </div>

              <button 
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-lg transition-colors text-sm shadow-lg shadow-blue-600/20"
              >
                Authenticate & Access Dashboard
              </button>
            </form>

            <div className="border-t border-slate-800/80 pt-4 text-center text-slate-500 text-[11px]">
              Demo Credentials: Teacher (T-402 / 1234) • Manager (admin / admin123)
            </div>
          </div>
        </main>

      ) : currentUser.role === 'manager' ? (

        /* ------------------------------------------------------------------ */
        /* MANAGER DASHBOARD: EDITABLE SYLLABUS & CURRICULUM MANAGEMENT        */
        /* ------------------------------------------------------------------ */
        <main className="flex-1 max-w-6xl w-full mx-auto p-6 space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-800 pb-4">
            <div>
              <h1 className="text-xl font-bold tracking-tight">Syllabus & Curriculum Administration</h1>
              <p className="text-slate-400 text-xs">Full CRUD management of syllabus targets and topic completion for Classes 1–12.</p>
            </div>

            <button 
              onClick={() => setShowAddSubjectForm(!showAddSubjectForm)}
              className="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition-colors flex items-center gap-2"
            >
              {showAddSubjectForm ? 'Close Form' : '＋ Add Subject Syllabus'}
            </button>
          </div>

          {/* Add Subject Modal / Form */}
          {showAddSubjectForm && (
            <form onSubmit={handleAddSubject} className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-4 animate-fadeIn">
              <h3 className="font-bold text-sm text-blue-400 border-b border-slate-800 pb-2">Create New Subject Syllabus Entry</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label htmlFor="new-subject-class" className="block text-xs text-slate-400 mb-1">Class Grade</label>
                  <select 
                    id="new-subject-class"
                    value={newSubject.classGrade}
                    onChange={(e) => setNewSubject({ ...newSubject, classGrade: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 p-2 text-xs rounded text-white"
                  >
                    <option value="Class 8">Class 8</option>
                    <option value="Class 11 (Form 3)">Class 11 (Form 3)</option>
                    <option value="Class 12 (Form 4)">Class 12 (Form 4)</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="new-subject-name" className="block text-xs text-slate-400 mb-1">Subject Name</label>
                  <input 
                    id="new-subject-name"
                    type="text" 
                    required 
                    placeholder="e.g. Chemistry"
                    value={newSubject.subject}
                    onChange={(e) => setNewSubject({ ...newSubject, subject: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 p-2 text-xs rounded text-white"
                  />
                </div>

                <div>
                  <label htmlFor="new-subject-teacher" className="block text-xs text-slate-400 mb-1">Assigned Teacher ID</label>
                  <input 
                    id="new-subject-teacher"
                    type="text" 
                    required 
                    value={newSubject.teacherId}
                    onChange={(e) => setNewSubject({ ...newSubject, teacherId: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 p-2 text-xs rounded text-white"
                  />
                </div>

                <div>
                  <label htmlFor="new-subject-target" className="block text-xs text-slate-400 mb-1">Target Benchmark %</label>
                  <input 
                    id="new-subject-target"
                    type="number" 
                    min="0"
                    max="100"
                    required 
                    value={newSubject.target}
                    onChange={(e) => setNewSubject({ ...newSubject, target: Math.min(100, Math.max(0, Number(e.target.value) || 0)) })}
                    className="w-full bg-slate-950 border border-slate-800 p-2 text-xs rounded text-white"
                  />
                </div>

                <div>
                  <label htmlFor="new-subject-deadline" className="block text-xs text-slate-400 mb-1">Deadline</label>
                  <input 
                    id="new-subject-deadline"
                    type="date" 
                    required 
                    value={newSubject.deadline}
                    onChange={(e) => setNewSubject({ ...newSubject, deadline: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 p-2 text-xs rounded text-white [color-scheme:dark]"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <button 
                  type="submit" 
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs px-4 py-2 rounded"
                >
                  Save Subject Entry
                </button>
              </div>
            </form>
          )}

          {/* Syllabus Cards List */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {syllabusList.map((item) => {
              const currentProgress = calculateProgress(item.units);
              return (
                <div key={item.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="text-[10px] font-bold font-mono uppercase bg-blue-950 text-blue-400 border border-blue-800 px-2 py-0.5 rounded">
                          {item.classGrade}
                        </span>
                        <h2 className="text-lg font-bold mt-1">{item.subject}</h2>
                        <p className="text-xs text-slate-400">Assigned Staff ID: {item.teacherId}</p>
                      </div>

                      <button 
                        onClick={() => setActiveModalSyllabus(item.id)}
                        className="bg-slate-800 hover:bg-slate-700 text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-700 text-blue-400"
                      >
                        📝 Log Topics
                      </button>
                    </div>

                    {/* Progress Stats */}
                    <div className="space-y-1 pt-2">
                      <div className="flex justify-between text-xs font-semibold">
                        <span>Curriculum Progress: {currentProgress}%</span>
                        <span className="text-slate-400">Target Benchmark: {item.target}%</span>
                      </div>
                      <div className="w-full bg-slate-950 h-2.5 rounded-full overflow-hidden border border-slate-800">
                        <div 
                          className={`h-full transition-all duration-300 ${currentProgress >= item.target ? 'bg-emerald-500' : 'bg-amber-500'}`}
                          style={{ width: `${currentProgress}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-slate-800/80 pt-3 flex justify-between items-center text-xs text-slate-400">
                    <span>Deadline: {item.deadline}</span>
                    <span className="font-semibold text-slate-300">{item.units.length} Units Configured</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* LOG TOPIC COVERED MODAL */}
          {activeSyllabus && (
            <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-xs text-blue-400 font-mono font-bold uppercase">{activeSyllabus.classGrade}</span>
                    <h3 className="text-lg font-bold">{activeSyllabus.subject} - Curriculum Units</h3>
                    {/* [prototype-fix 1] Live progress now ticks inside the modal itself. */}
                    <p className="text-xs text-slate-400 mt-0.5">
                      {calculateProgress(activeSyllabus.units)}% covered · target {activeSyllabus.target}% · {activeSyllabus.units.length} units
                    </p>
                  </div>
                  <button 
                    onClick={() => setActiveModalSyllabus(null)}
                    className="text-slate-400 hover:text-white font-bold text-lg"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {activeSyllabus.units.map((unit) => (
                    <label 
                      key={unit.id} 
                      className="flex items-center gap-3 p-3 bg-slate-950 border border-slate-800 rounded-lg cursor-pointer hover:border-slate-700 transition-colors"
                    >
                      <input 
                        type="checkbox"
                        checked={unit.covered}
                        onChange={() => handleToggleTopic(activeSyllabus.id, unit.id)}
                        className="w-4 h-4 rounded accent-blue-600"
                      />
                      <span className={`text-xs font-medium ${unit.covered ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                        {unit.title}
                      </span>
                    </label>
                  ))}
                </div>

                <div className="border-t border-slate-800 pt-3 flex items-center justify-between gap-2">
                  {/* [prototype-fix 8] Grow the topic list without leaving the modal. */}
                  <button
                    onClick={() => handleAddUnit(activeSyllabus.id)}
                    className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-blue-400 font-semibold text-xs px-3 py-2 rounded-lg"
                  >
                    ＋ Add Unit
                  </button>
                  <button 
                    onClick={() => setActiveModalSyllabus(null)}
                    className="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs px-5 py-2 rounded-lg"
                  >
                    Save & Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>

      ) : (

        /* ------------------------------------------------------------------ */
        /* TEACHER DASHBOARD: RESTRICTED ATTENDANCE MARKING ENGINE             */
        /* ------------------------------------------------------------------ */
        <main className="flex-1 max-w-5xl w-full mx-auto p-6 space-y-6">
          <div className="border-b border-slate-800 pb-4">
            <h1 className="text-xl font-bold tracking-tight">Teacher Subject Portal</h1>
            <p className="text-slate-400 text-xs mt-0.5">
              Strictly restricted to assigned timetable periods for <strong>{currentUser.data.name}</strong>.
            </p>
          </div>

          {/* PRIVACY GUARD BANNER */}
          <div className="bg-blue-950/40 border border-blue-800/50 p-3 rounded-xl text-xs text-blue-300 flex items-center justify-between">
            <span>🛡️ <strong>RBAC Privacy Shield Active:</strong> Access to other teacher records or unassigned class schedules is strictly blocked.</span>
          </div>

          {/* ASSIGNED SUBJECT SCHEDULE & ATTENDANCE ROSTER */}
          <div className="space-y-6">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Your Active Subject Assignments ({teacherSubjects.length})
            </h2>

            {teacherSubjects.map((sub) => {
              const attendanceKey = `${sub.id}_${SESSION_DATE}`;
              const currentRosterState = attendanceRecords[attendanceKey] || {};
              // [prototype-fix 6] Only this class's roll may be marked — the mock
              // previously listed all three Form 3 students under the Class 8
              // subject too. The real endpoint scopes the roster server-side by
              // class + subject + period and refuses foreign slots.
              const roster = INITIAL_STUDENTS.filter((s) => s.classGrade === sub.classGrade);
              const tally = ATTENDANCE_STATUSES.map((st) => ({
                status: st,
                count: roster.filter((s) => currentRosterState[s.id] === st).length,
              }));
              const marked = tally.reduce((sum, t) => sum + t.count, 0);

              return (
                <div key={sub.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-sm">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="text-xs font-mono font-bold text-blue-400 uppercase">{sub.classGrade}</span>
                      <h3 className="text-lg font-bold mt-0.5">{sub.name}</h3>
                      <p className="text-xs text-slate-400 mt-0.5">Assigned Period: {sub.period}</p>
                    </div>

                    <span className="bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono text-[10px] font-bold px-2.5 py-1 rounded-full">
                      ● Active Period Session
                    </span>
                  </div>

                  {/* Student Attendance Roster */}
                  <div className="space-y-2 border-t border-slate-800 pt-3">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <h4 className="text-xs font-semibold text-slate-300">Mark Period Attendance:</h4>

                      <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                        {tally.map((t) => (
                          <span key={t.status} className="bg-slate-950 border border-slate-800 rounded px-2 py-0.5">
                            {t.status}: <strong className="text-slate-200">{t.count}</strong>
                          </span>
                        ))}
                        <span className="text-slate-500">
                          {marked}/{roster.length} on {SESSION_DATE}
                        </span>
                      </div>
                    </div>

                    {roster.length > 0 && (
                      <div className="flex justify-end">
                        <button
                          onClick={() => handleMarkAllPresent(sub.id, roster)}
                          className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300"
                        >
                          ✓ Mark all present
                        </button>
                      </div>
                    )}

                    <div className="divide-y divide-slate-800/60">
                      {roster.length === 0 ? (
                        <p className="py-3 text-xs text-slate-500">
                          No enrolled students match {sub.classGrade} in the mock roll, so there is
                          nothing to mark — the real portal loads this class's roster from the API.
                        </p>
                      ) : (
                        roster.map((student) => {
                          const status = currentRosterState[student.id] || 'Not Marked';
                          return (
                            <div key={student.id} className="py-2.5 flex items-center justify-between text-xs">
                              <div>
                                <p className="font-bold text-slate-200">{student.name}</p>
                                <p className="text-[10px] text-slate-500 font-mono">{student.id}</p>
                              </div>

                              <div className="flex gap-1.5">
                                {ATTENDANCE_STATUSES.map((st) => (
                                  <button
                                    key={st}
                                    onClick={() => handleMarkAttendance(sub.id, student.id, st)}
                                    className={`px-3 py-1 rounded-md font-semibold text-[11px] transition-colors ${
                                      status === st
                                        ? statusActiveClass(st)
                                        : 'bg-slate-950 hover:bg-slate-800 text-slate-400 border border-slate-800'
                                    }`}
                                  >
                                    {st}
                                  </button>
                                ))}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </main>
      )}

    </div>
  );
}
