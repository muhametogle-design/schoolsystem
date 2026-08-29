import { useEffect } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { clearError, selectUser } from './features/auth/authSlice';
import Login from './pages/Login';
import Layout from './components/Layout';
import SchoolDashboard from './pages/SchoolDashboard';
import Students from './pages/Students';
import StudentDetails from './pages/StudentDetails';
import ReportCard from './pages/ReportCard';
import Attendance from './pages/Attendance';
import StateDashboard from './pages/StateDashboard';
import InstitutionOverview from './pages/InstitutionOverview';
import StudentLookup from './pages/StudentLookup';

/** Routes only the tenant ERP roles may open. */
function SchoolOnly({ children }) {
  const user = useSelector(selectUser);
  if (!user) return <Navigate to="/" replace />;
  if (user.role === 'state_inspector') return <Navigate to="/state" replace />;
  return children;
}

/** Routes only a state inspector may open. */
function StateOnly({ children }) {
  const user = useSelector(selectUser);
  if (!user) return <Navigate to="/" replace />;
  if (user.role !== 'state_inspector') return <Navigate to="/school" replace />;
  return children;
}

export default function App() {
  const user = useSelector(selectUser);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  useEffect(() => {
    const onExpired = () => navigate('/', { replace: true });
    window.addEventListener('ne-emis:session-expired', onExpired);
    return () => window.removeEventListener('ne-emis:session-expired', onExpired);
  }, [navigate]);

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);

  return (
    <Routes>
      <Route path="/" element={user ? <Navigate to={user.role === 'state_inspector' ? '/state' : '/school'} replace /> : <Login />} />

      <Route
        element={
          <SchoolOnly>
            <Layout portal="school" />
          </SchoolOnly>
        }
      >
        <Route path="/school" element={<SchoolDashboard />} />
        <Route path="/school/students" element={<Students />} />
        <Route path="/school/students/:neSid" element={<StudentDetails />} />
        <Route path="/school/attendance" element={<Attendance />} />
      </Route>

      {/* Print route — rendered without the app chrome so the card is page-clean. */}
      <Route
        path="/school/students/:neSid/report-card"
        element={
          <SchoolOnly>
            <ReportCard />
          </SchoolOnly>
        }
      />

      <Route
        element={
          <StateOnly>
            <Layout portal="state" />
          </StateOnly>
        }
      >
        <Route path="/state" element={<StateDashboard />} />
        <Route path="/state/institutions/:schoolId" element={<InstitutionOverview />} />
        <Route path="/state/lookup" element={<StudentLookup />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
