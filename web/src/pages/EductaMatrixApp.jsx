import React, { useState } from 'react';

export default function EductaMatrixApp() {
  // Global App States
  const [viewMode, setViewMode] = useState('student'); // 'student' | 'admin'
  const [isDarkMode, setIsDarkMode] = useState(false);
  
  // Student Portal State
  const [isStudentLoggedIn, setIsStudentLoggedIn] = useState(false);
  const [rollNumber, setRollNumber] = useState('');
  const [studentTab, setStudentTab] = useState('overview');

  // Admin Portal Filters State
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRegion, setSelectedRegion] = useState('All');

  // Mock Student Data Record
  const studentData = {
    name: "Ahmed Mohamed Farah",
    rollNumber: rollNumber || "NG-10023",
    school: "Nugaal High School",
    classGrade: "Form 3 (Class 11)",
    tuitionStatus: "Paid",
    attendanceRate: "96.4%",
    grades: [
      { subject: "Mathematics", midterm: "38/40", final: "54/60", total: "92%", grade: "A" },
      { subject: "Physics", midterm: "34/40", final: "50/60", total: "84%", grade: "B" },
      { subject: "Somali (Af-Somali)", midterm: "36/40", final: "58/60", total: "94%", grade: "A+" },
      { subject: "English", midterm: "32/40", final: "48/60", total: "80%", grade: "B" },
    ]
  };

  // Mock State Level Telemetry Data
  const stateTelemetry = {
    totalSchools: 412,
    activeStudents: 184200,
    tuitionCompliance: "91.8%",
    verificationRate: "98.2%",
    regions: ["All", "Nugaal", "Bari", "Mudug", "Sanaag", "Sool"],
    schools: [
      { id: "SCH-001", name: "Nugaal High School", region: "Nugaal", students: 1240, status: "Verified", compliance: "96%" },
      { id: "SCH-002", name: "Bosaaso Secondary", region: "Bari", students: 2100, status: "Verified", compliance: "92%" },
      { id: "SCH-003", name: "Galkacyo Central School", region: "Mudug", students: 1850, status: "Pending Audit", compliance: "84%" },
      { id: "SCH-004", name: "Erigavo Academy", region: "Sanaag", students: 940, status: "Verified", compliance: "89%" },
    ]
  };

  const filteredSchools = stateTelemetry.schools.filter(school => {
    const matchesSearch = school.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          school.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRegion = selectedRegion === 'All' || school.region === selectedRegion;
    return matchesSearch && matchesRegion;
  });

  const handleStudentLogin = (e) => {
    e.preventDefault();
    if (rollNumber.trim()) {
      setIsStudentLoggedIn(true);
    }
  };

  return (
    <div className={`min-h-screen ${isDarkMode ? 'dark bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'} font-sans flex flex-col transition-colors duration-200`}>
      
      {/* GLOBAL SYSTEM BAR (Environment Switcher) */}
      <nav className="bg-slate-900 text-slate-300 px-4 py-2 text-xs flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-white tracking-wide uppercase text-[10px] bg-blue-600 px-2 py-0.5 rounded">
            Educta Matrix OS
          </span>
          <span className="hidden sm:inline text-slate-400">Environment: Production (2026.1)</span>
        </div>

        <div className="flex items-center gap-2">
          {/* View Switcher */}
          <button 
            onClick={() => setViewMode(viewMode === 'student' ? 'admin' : 'student')}
            className="bg-slate-800 hover:bg-slate-700 text-white px-2.5 py-1 rounded border border-slate-700 transition-colors"
          >
            Switch to: {viewMode === 'student' ? 'State Admin Portal' : 'Student Portal'}
          </button>

          {/* Dark/Light Mode Switcher */}
          <button 
            onClick={() => setIsDarkMode(!isDarkMode)}
            className="bg-slate-800 hover:bg-slate-700 text-white px-2 py-1 rounded border border-slate-700"
          >
            {isDarkMode ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </nav>

      {/* PORTAL ROUTER */}
      {viewMode === 'student' ? (
        
        /* ------------------------------------------------------------- */
        /* MODULE 1: EDUCTA DIRECT (STUDENT MOBILE PORTAL)               */
        /* ------------------------------------------------------------- */
        <div className="flex-1 flex flex-col">
          {/* Student Header */}
          <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 py-3 sticky top-0 z-40 flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                E
              </div>
              <div>
                <h1 className="font-bold text-base leading-tight tracking-tight">Educta Direct</h1>
                <span className="text-xs text-slate-500 dark:text-slate-400">Student & Parent Portal</span>
              </div>
            </div>

            {isStudentLoggedIn && (
              <button 
                onClick={() => setIsStudentLoggedIn(false)}
                className="text-xs font-medium text-red-600 dark:text-red-400 hover:underline px-3 py-1 rounded-md bg-red-50 dark:bg-red-950/50"
              >
                Logout
              </button>
            )}
          </header>

          <main className="flex-1 max-w-md w-full mx-auto p-4 flex flex-col justify-center">
            {!isStudentLoggedIn ? (
              
              /* STUDENT LOGIN SCREEN */
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-6 my-auto shadow-lg">
                <div className="text-center space-y-1.5">
                  <h2 className="text-xl font-bold tracking-tight">Access Your Portal</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Enter your unique student roll number to view your examination results.
                  </p>
                </div>

                <form onSubmit={handleStudentLogin} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Student Roll Number
                    </label>
                    <input 
                      type="text" 
                      required
                      placeholder="e.g. NG-10023"
                      value={rollNumber}
                      onChange={(e) => setRollNumber(e.target.value.toUpperCase())}
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:border-blue-600 focus:ring-1 focus:ring-blue-600 text-center text-lg tracking-widest font-mono uppercase py-2.5 px-3.5"
                    />
                  </div>

                  <button 
                    type="submit" 
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg shadow-sm transition-colors text-base font-semibold"
                  >
                    View Portal Dashboard
                  </button>
                </form>

                <div className="border-t border-slate-100 dark:border-slate-800 pt-4 text-center">
                  <p className="text-xs text-slate-400">
                    Secured by Educta Matrix OS • QR Instant Authentication
                  </p>
                </div>
              </div>

            ) : (

              /* STUDENT DASHBOARD SCREEN */
              <div className="space-y-4 pb-12">
                {/* ID Card */}
                <div className="bg-gradient-to-br from-blue-600 to-blue-800 text-white border-none shadow-md rounded-xl p-5">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="text-xs uppercase tracking-wider text-blue-200 font-medium">Verified Student</span>
                      <h2 className="text-xl font-bold mt-0.5">{studentData.name}</h2>
                    </div>
                    <span className="bg-white/20 text-white font-mono px-2.5 py-1 rounded-md text-xs backdrop-blur-sm">
                      {studentData.rollNumber}
                    </span>
                  </div>
                  <div className="mt-4 pt-4 border-t border-white/15 flex justify-between text-sm">
                    <div>
                      <p className="text-blue-200 text-xs">School</p>
                      <p className="font-medium">{studentData.school}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-blue-200 text-xs">Class</p>
                      <p className="font-medium">{studentData.classGrade}</p>
                    </div>
                  </div>
                </div>

                {/* Quick Stats */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
                    <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Tuition Status</span>
                    <div className="mt-2">
                      <span className="bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 px-3 py-1 rounded-full text-xs font-semibold inline-flex items-center gap-1.5">
                        ● {studentData.tuitionStatus}
                      </span>
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
                    <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Attendance Rate</span>
                    <p className="text-lg font-bold text-slate-800 dark:text-slate-200 mt-1">{studentData.attendanceRate}</p>
                  </div>
                </div>

                {/* Tab Navigation */}
                <div className="flex bg-slate-200 dark:bg-slate-800 p-1 rounded-xl">
                  <button 
                    onClick={() => setStudentTab('overview')}
                    className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${studentTab === 'overview' ? 'bg-white dark:bg-slate-900 shadow-sm text-blue-600 dark:text-blue-400 font-semibold' : 'text-slate-600 dark:text-slate-400'}`}
                  >
                    Exam Results
                  </button>
                  <button 
                    onClick={() => setStudentTab('library')}
                    className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${studentTab === 'library' ? 'bg-white dark:bg-slate-900 shadow-sm text-blue-600 dark:text-blue-400 font-semibold' : 'text-slate-600 dark:text-slate-400'}`}
                  >
                    Reading Library
                  </button>
                </div>

                {/* Tab Content 1: Grades */}
                {studentTab === 'overview' && (
                  <div className="space-y-3">
                    <div className="flex justify-between items-center px-1">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Core Subject Breakdown</h3>
                      <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">Term 1 Results</span>
                    </div>

                    <div className="space-y-2">
                      {studentData.grades.map((item, index) => (
                        <div key={index} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-sm">
                          <div>
                            <h4 className="font-semibold text-sm">{item.subject}</h4>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                              Mid: {item.midterm} | Final: {item.final}
                            </p>
                          </div>
                          <div className="text-right flex items-center gap-3">
                            <p className="text-sm font-bold">{item.total}</p>
                            <span className="w-8 h-8 rounded-full bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 font-bold text-xs flex items-center justify-center border border-blue-200 dark:border-blue-800">
                              {item.grade}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="pt-2">
                      <button className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 rounded-lg shadow-sm transition-colors text-sm">
                        Download QR-Verified Report Card (PDF)
                      </button>
                    </div>
                  </div>
                )}

                {/* Tab Content 2: Reading Library */}
                {studentTab === 'library' && (
                  <div className="space-y-3">
                    <div className="flex justify-between items-center px-1">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Available Books</h3>
                      <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">Free Access</span>
                    </div>

                    <div className="space-y-2">
                      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 flex items-center justify-between shadow-sm">
                        <div>
                          <h4 className="font-semibold text-sm">Taariikhda Soomaaliya</h4>
                          <p className="text-xs text-slate-500">General History • PDF</p>
                        </div>
                        <button className="px-3 py-1.5 text-xs font-medium bg-slate-100 dark:bg-slate-800 hover:bg-blue-600 hover:text-white rounded-lg transition-colors">
                          Read
                        </button>
                      </div>

                      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 flex items-center justify-between shadow-sm">
                        <div>
                          <h4 className="font-semibold text-sm">Advanced Mathematics Guide</h4>
                          <p className="text-xs text-slate-500">Curriculum Textbook • PDF</p>
                        </div>
                        <button className="px-3 py-1.5 text-xs font-medium bg-slate-100 dark:bg-slate-800 hover:bg-blue-600 hover:text-white rounded-lg transition-colors">
                          Read
                        </button>
                      </div>
                    </div>
                  </div>
                )}

              </div>
            )}
          </main>
        </div>

      ) : (

        /* ------------------------------------------------------------- */
        /* MODULE 2: EDUCTA COMMAND (STATE SUPER ADMIN DASHBOARD)         */
        /* ------------------------------------------------------------- */
        <div className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
          
          {/* Admin Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase bg-blue-100 dark:bg-blue-950 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded font-bold">
                  State Education Office
                </span>
                <span className="text-xs text-slate-400">Live Telemetry</span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight mt-1">Educta Command Center</h1>
            </div>

            <div className="flex items-center gap-3">
              <button className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg shadow-sm transition-colors text-xs">
                + Register New School Tenant
              </button>
            </div>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase tracking-wider">Registered Schools</span>
              <p className="text-2xl font-bold mt-2">{stateTelemetry.totalSchools}</p>
              <span className="text-[11px] text-emerald-600 font-medium mt-1 inline-block">↑ 12 added this term</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase tracking-wider">Active Students</span>
              <p className="text-2xl font-bold mt-2">{stateTelemetry.activeStudents.toLocaleString()}</p>
              <span className="text-[11px] text-emerald-600 font-medium mt-1 inline-block">98.4% attendance index</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase tracking-wider">Tuition Compliance</span>
              <p className="text-2xl font-bold mt-2 text-emerald-600">{stateTelemetry.tuitionCompliance}</p>
              <span className="text-[11px] text-slate-400 mt-1 inline-block">Verified via Mobile Money</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase tracking-wider">Audit Rate</span>
              <p className="text-2xl font-bold mt-2">{stateTelemetry.verificationRate}</p>
              <span className="text-[11px] text-blue-600 dark:text-blue-400 font-medium mt-1 inline-block">QR verification active</span>
            </div>
          </div>

          {/* Filter & Data Section */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pb-2 border-b border-slate-100 dark:border-slate-800">
              <h3 className="text-base font-bold">Regional School Registry</h3>
              
              <div className="flex items-center gap-2 w-full sm:w-auto">
                {/* Search */}
                <input 
                  type="text" 
                  placeholder="Search school name or ID..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:border-blue-600 focus:ring-1 focus:ring-blue-600 text-xs py-1.5 px-3 w-full sm:w-64"
                />

                {/* Region Selector */}
                <select 
                  value={selectedRegion}
                  onChange={(e) => setSelectedRegion(e.target.value)}
                  className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:border-blue-600 focus:ring-1 focus:ring-blue-600 text-xs py-1.5 px-3 w-auto"
                >
                  {stateTelemetry.regions.map(region => (
                    <option key={region} value={region}>{region} Region</option>
                  ))}
                </select>
              </div>
            </div>

            {/* School Data Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    <th className="py-3 px-3">School ID</th>
                    <th className="py-3 px-3">School Name</th>
                    <th className="py-3 px-3">Region</th>
                    <th className="py-3 px-3">Enrolled Students</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3 text-right">Compliance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-sm">
                  {filteredSchools.length > 0 ? (
                    filteredSchools.map((school) => (
                      <tr key={school.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-3 font-mono text-xs text-slate-500">{school.id}</td>
                        <td className="py-3 px-3 font-semibold">{school.name}</td>
                        <td className="py-3 px-3 text-slate-500 dark:text-slate-400">{school.region}</td>
                        <td className="py-3 px-3 font-medium">{school.students.toLocaleString()}</td>
                        <td className="py-3 px-3">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold inline-flex items-center gap-1.5 ${school.status === 'Verified' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400' : 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400'}`}>
                            ● {school.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right font-bold text-slate-700 dark:text-slate-300">
                          {school.compliance}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400 text-xs">
                        No schools found matching search or region filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      )}

    </div>
  );
}
