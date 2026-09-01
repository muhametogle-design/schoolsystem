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

  // Modal State for Syllabus Unit Coverage
  const [activeModalSyllabus, setActiveModalSyllabus] = useState(null);

  // New Subject Form State (Manager CRUD)
  const [showAddSubjectForm, setShowAddSubjectForm] = useState(false);
  const [newSubject, setNewSubject] = useState({ classGrade: 'Class 11 (Form 3)', subject: '', teacherId: 'T-402', target: 80, deadline: '2026-11-15' });

  // Handle Authentication
  const handleLogin = (e) => {
    e.preventDefault();
    setAuthError('');

    if (loginRole === 'manager') {
      if (loginId === 'admin' && loginPin === 'admin123') {
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

  // Handle Teacher Marking Attendance
  const handleMarkAttendance = (subjectId, studentId, status) => {
    const key = `${subjectId}_2026-09-01`;
    setAttendanceRecords(prev => ({
      ...prev,
      [key]: {
        ...(prev[key] || {}),
        [studentId]: status
      }
    }));
  };

  // Add New Subject to Syllabus (Manager Action)
  const handleAddSubject = (e) => {
    e.preventDefault();
    const newEntry = {
      id: `SYL-${Date.now().toString().slice(-3)}`,
      ...newSubject,
      units: [{ id: 'U1', title: 'Chapter 1: Foundations', covered: false }]
    };
    setSyllabusList([...syllabusList, newEntry]);
    setShowAddSubjectForm(false);
  };

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
                <label className="text-xs uppercase font-semibold text-slate-400">
                  {loginRole === 'teacher' ? 'Staff ID' : 'Username'}
                </label>
                <input 
                  type="text" 
                  required
                  placeholder={loginRole === 'teacher' ? 'e.g. T-402' : 'admin'}
                  value={loginId}
                  onChange={(e) => setLoginId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white focus:border-blue-600 outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs uppercase font-semibold text-slate-400">
                  {loginRole === 'teacher' ? 'PIN Code' : 'Password'}
                </label>
                <input 
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
                  <label className="block text-xs text-slate-400 mb-1">Class Grade</label>
                  <select 
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
                  <label className="text-xs text-slate-400 mb-1">Subject Name</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="e.g. Chemistry"
                    value={newSubject.subject}
                    onChange={(e) => setNewSubject({ ...newSubject, subject: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 p-2 text-xs rounded text-white"
                  />
                </div>

                <div>
                  <label className="block text-xs text-slate-400 mb-1">Assigned Teacher ID</label>
                  <input 
                    type="text" 
                    required 
                    value={newSubject.teacherId}
                    onChange={(e) => setNewSubject({ ...newSubject, teacherId: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 p-2 text-xs rounded text-white"
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
                        onClick={() => setActiveModalSyllabus(item)}
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
          {activeModalSyllabus && (
            <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-xs text-blue-400 font-mono font-bold uppercase">{activeModalSyllabus.classGrade}</span>
                    <h3 className="text-lg font-bold">{activeModalSyllabus.subject} - Curriculum Units</h3>
                  </div>
                  <button 
                    onClick={() => setActiveModalSyllabus(null)}
                    className="text-slate-400 hover:text-white font-bold text-lg"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {activeModalSyllabus.units.map((unit) => (
                    <label 
                      key={unit.id} 
                      className="flex items-center gap-3 p-3 bg-slate-950 border border-slate-800 rounded-lg cursor-pointer hover:border-slate-700 transition-colors"
                    >
                      <input 
                        type="checkbox"
                        checked={unit.covered}
                        onChange={() => handleToggleTopic(activeModalSyllabus.id, unit.id)}
                        className="w-4 h-4 rounded accent-blue-600"
                      />
                      <span className={`text-xs font-medium ${unit.covered ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                        {unit.title}
                      </span>
                    </label>
                  ))}
                </div>

                <div className="border-t border-slate-800 pt-3 flex justify-end">
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
              Your Active Subject Assignments
            </h2>

            {currentUser.data.assignedSubjects.map((sub) => {
              const attendanceKey = `${sub.id}_2026-09-01`;
              const currentRosterState = attendanceRecords[attendanceKey] || {};

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
                    <h4 className="text-xs font-semibold text-slate-300">Mark Period Attendance:</h4>

                    <div className="divide-y divide-slate-800/60">
                      {INITIAL_STUDENTS.map((student) => {
                        const status = currentRosterState[student.id] || 'Not Marked';
                        return (
                          <div key={student.id} className="py-2.5 flex items-center justify-between text-xs">
                            <div>
                              <p className="font-bold text-slate-200">{student.name}</p>
                              <p className="text-[10px] text-slate-500 font-mono">{student.id}</p>
                            </div>

                            <div className="flex gap-1.5">
                              {['Present', 'Absent', 'Late'].map((st) => (
                                <button
                                  key={st}
                                  onClick={() => handleMarkAttendance(sub.id, student.id, st)}
                                  className={`px-3 py-1 rounded-md font-semibold text-[11px] transition-colors ${
                                    status === st 
                                      ? st === 'Present' ? 'bg-emerald-600 text-white' : st === 'Absent' ? 'bg-red-600 text-white' : 'bg-amber-600 text-white'
                                      : 'bg-slate-950 hover:bg-slate-800 text-slate-400 border border-slate-800'
                                  }`}
                                >
                                  {st}
                                </button>
                              ))}
                            </div>
                          </div>
                        );
                      })}
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
