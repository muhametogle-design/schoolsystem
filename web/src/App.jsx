import { useEffect } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { clearError, fetchMe, selectUser } from './features/auth/authSlice';
import Login from './pages/Login';
import Layout from './components/Layout';
import SchoolDashboard from './pages/SchoolDashboard';
import Students from './pages/Students';
import StudentDetails from './pages/StudentDetails';
import ReportCard from './pages/ReportCard';
import Attendance from './pages/Attendance';
import Classes from './pages/Classes';
import Teachers from './pages/Teachers';
import Billing from './pages/Billing';
import StateDashboard from './pages/StateDashboard';
import InstitutionOverview from './pages/InstitutionOverview';
import SchoolDirectory from './pages/SchoolDirectory';
import StudentLookup from './pages/StudentLookup';
import Substitutions from './pages/Substitutions';
import Syllabus from './pages/Syllabus';
import Biometrics from './pages/Biometrics';
import Backups from './pages/Backups';
import TeacherDashboard from './pages/TeacherDashboard';
import DataSaverToggle from './components/DataSaverToggle';
import { useDataSaverDetection } from './hooks/useDataSaver';

const STATE_ROLES = new Set(['state_admin', 'inspector', 'state_inspector']);
const isStateUser = (user) => STATE_ROLES.has(user?.role);

/** Routes only tenant ERP users may open. */
function SchoolOnly({ children }) {
  const user = useSelector(selectUser);
  if (!user) return <Navigate to="/" replace />;
  if (isStateUser(user)) return <Navigate to="/state" replace />;
  return children;
}

/** Teaching staff stay in their restricted portal (refinement 2). */
function TeacherOnly({ children }) {
  const user = useSelector(selectUser);
  if (!user) return <Navigate to="/" replace />;
  if (user.role !== 'teacher') return <Navigate to="/school" replace />;
  return children;
}

/** Routes only State Admins and Inspectors may open. */
function StateOnly({ children }) {
  const user = useSelector(selectUser);
  if (!user) return <Navigate to="/" replace />;
  if (!isStateUser(user)) return <Navigate to="/school" replace />;
  return children;
}

/** Backups are a platform operation reserved to the State Admin. */
function StateAdminOnly({ children }) {
  const user = useSelector(selectUser);
  if (!user) return <Navigate to="/" replace />;
  if (user.role !== 'state_admin') return <Navigate to="/state" replace />;
  return children;
}

/** Financial pages are private to the tenant School Admin role. */
function ManagerOnly({ children }) {
  const user = useSelector(selectUser);
  if (!user) return <Navigate to="/" replace />;
  if (user.role !== 'school_manager') return <Navigate to="/school" replace />;
  return children;
}

export default function App() {
  const user = useSelector(selectUser);
  const bootstrapped = useSelector((state) => state.auth.bootstrapped);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  // Module 3: track device network signals for the low-bandwidth Data Saver.
  useDataSaverDetection();

  useEffect(() => {
    // Probe on every fresh app load. This restores an HttpOnly cookie-backed
    // session when localStorage is unavailable, while the auth slice leaves a
    // no-token mobile user free to sign in immediately.
    dispatch(fetchMe());
  }, [dispatch]);

  useEffect(() => {
    const onExpired = () => navigate('/', { replace: true });
    window.addEventListener('ne-emis:session-expired', onExpired);
    return () => window.removeEventListener('ne-emis:session-expired', onExpired);
  }, [navigate]);

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);

  if (!bootstrapped) {
    return <div className="boot"><span className="boot__label">Verifying session…</span></div>;
  }

  const landing = isStateUser(user) ? '/state' : user.role === 'teacher' ? '/school/portal' : '/school';
  return (
    <Routes>
      <Route path="/" element={user ? <Navigate to={landing} replace /> : <Login />} />

      <Route element={<SchoolOnly><Layout portal="school" /></SchoolOnly>}>
        {/* Teachers are redirected to their restricted portal dashboard. */}
        <Route path="/school" element={user?.role === 'teacher' ? <Navigate to="/school/portal" replace /> : <SchoolDashboard />} />
        <Route path="/school/portal" element={<TeacherOnly><TeacherDashboard /></TeacherOnly>} />
        <Route path="/school/students" element={<Students />} />
        <Route path="/school/students/:neSid" element={<StudentDetails />} />
        <Route path="/school/classes" element={<Classes />} />
        <Route path="/school/teachers" element={<Teachers />} />
        <Route path="/school/attendance" element={<Attendance />} />
        <Route path="/school/substitutions" element={<Substitutions />} />
        <Route path="/school/syllabus" element={<Syllabus />} />
        <Route path="/school/biometrics" element={<Biometrics />} />
        <Route path="/school/billing" element={<ManagerOnly><Billing /></ManagerOnly>} />
        {/* Canonical report-card path from the brief. */}
        <Route path="/students/:neSid/report-card" element={<ReportCard />} />
      </Route>

      {/* Print route — rendered without application chrome. */}
      <Route path="/school/students/:neSid/report-card" element={<SchoolOnly><ReportCard /></SchoolOnly>} />

      <Route element={<StateOnly><Layout portal="state" /></StateOnly>}>
        <Route path="/state" element={<StateDashboard />} />
        <Route path="/state/directory" element={<SchoolDirectory />} />
        <Route path="/state/institutions/:schoolId" element={<InstitutionOverview />} />
        <Route path="/state/lookup" element={<StudentLookup />} />
        <Route path="/state/backups" element={<StateAdminOnly><Backups /></StateAdminOnly>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
