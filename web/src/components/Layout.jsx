import { useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Logo from './Logo';
import Badge from './Badge';
import DataSaverToggle from './DataSaverToggle';
import BackBar from './BackBar';
import DesignDrawer from './DesignDrawer';
import PublishBar from './PublishBar';
import MobilePreviewFrame from './MobilePreviewFrame';
import { logout, selectIsStateAdmin, selectUser } from '../features/auth/authSlice';
import { fetchInstitutions, selectInstitutions } from '../features/schools/schoolSlice';
import { selectSaverActive, selectSaverReason } from '../features/ui/uiSlice';
import {
  fetchDesignConfig,
  selectMobilePreview,
  setDrawerOpen,
} from '../features/design/designSlice';

const SCHOOL_NAV = [
  { to: '/school', label: 'Dashboard', end: true },
  { to: '/school/students', label: 'Students' },
  { to: '/school/classes', label: 'Classes & subjects' },
  { to: '/school/teachers', label: 'Teachers' },
  { to: '/school/attendance', label: 'Attendance' },
  { to: '/school/substitutions', label: 'Substitutions' },
  { to: '/school/syllabus', label: 'Syllabus tracker' },
  { to: '/school/biometrics', label: 'Biometrics' },
  { to: '/school/billing', label: 'Billing', managerOnly: true },
];

/**
 * Refinements 2-3 — teaching staff get a deliberately short nav. Department
 * Heads additionally hold syllabus authority (refinement 1: Log Topic
 * Covered), so their nav exposes the tracker too.
 */
const TEACHER_NAV = [
  { to: '/school/portal', label: 'My teaching day', end: true },
  { to: '/school/syllabus', label: 'Syllabus tracker', deptHeadOnly: true },
];

const STATE_NAV = [
  { to: '/state', label: 'Live monitor', end: true },
  { to: '/state/directory', label: 'School directory' },
  { to: '/state/lookup', label: 'Roll number lookup' },
  { to: '/state/backups', label: 'Encrypted backups', stateAdminOnly: true },
];

export default function Layout({ portal }) {
  const user = useSelector(selectUser);
  const isStateAdmin = useSelector(selectIsStateAdmin);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const institutions = useSelector(selectInstitutions);
  const saverActive = useSelector(selectSaverActive);
  const saverReason = useSelector(selectSaverReason);
  const mobilePreview = useSelector(selectMobilePreview);
  const isState = portal === 'state';
  const nav = (isState ? STATE_NAV : user?.role === 'teacher' ? TEACHER_NAV : SCHOOL_NAV).filter(
    (item) =>
      (!item.managerOnly || user?.role === 'school_manager') &&
      (!item.stateAdminOnly || user?.role === 'state_admin') &&
      (!item.deptHeadOnly || user?.is_department_head === true)
  );

  useEffect(() => {
    if (isState) dispatch(fetchInstitutions());
    else dispatch(fetchDesignConfig()); // Refinement 7-8: hydrate the live theme
  }, [isState, dispatch]);

  const onSignOut = async () => {
    await dispatch(logout());
    navigate('/', { replace: true });
  };

  const stateRoleLabel = isStateAdmin ? 'STATE ADMIN' : 'INSPECTOR PORTAL';
  return (
    <div className={`shell shell--${portal}`}>
      <aside className="sidebar">
        <div className="sidebar__brand"><Logo size={38} subtitle={isState ? 'Regional State Authority' : undefined} /></div>
        <nav className="sidebar__nav" aria-label="Primary navigation">
          {nav.map((item) => <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `navlink ${isActive ? 'is-active' : ''}`}>{item.label}</NavLink>)}
        </nav>

        {isState && (
          <div className="sidebar__section">
            <h2 className="sidebar__heading">Active school directory</h2>
            <ul className="institution-list">
              {institutions.map((institution) => (
                <li key={institution.id}>
                  <NavLink to={`/state/institutions/${institution.id}`} className={({ isActive }) => `institution ${isActive ? 'is-active' : ''}`}>
                    <span className="institution__name"><span className="institution__code">{institution.school_code}</span>{institution.school_name}</span>
                    <span className="institution__meta">{institution.student_count} students · {institution.teacher_count} teachers</span>
                  </NavLink>
                </li>
              ))}
              {institutions.length === 0 && <li className="institution institution--empty">No institutions registered</li>}
            </ul>
          </div>
        )}

        <div className="sidebar__foot">
          <div className="user-chip"><span className="user-chip__name">{user?.first_name} {user?.last_name}</span><span className="user-chip__role">{user?.role?.replace(/_/g, ' ')}</span></div>
          <button type="button" className="btn btn--ghost btn--block" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1 className="topbar__title">{isState ? 'State Education Authority' : user?.school_name ?? 'School Portal'}</h1>
            <p className="topbar__sub">{isState ? (isStateAdmin ? 'Tenant provisioning, roll-number oversight & academic visibility' : 'Read-only academic oversight across licensed schools') : 'Tenant ERP · students, staff, curriculum, attendance and private billing'}</p>
          </div>
          <div className="topbar__right">
            <button
              type="button"
              className="design-trigger"
              onClick={() => dispatch(setDrawerOpen(true))}
              title="Open Design & Layout Settings"
            >
              🎨 <span className="design-trigger__label">Design</span>
            </button>
            <DataSaverToggle />
            <Badge status="Active">{isState ? stateRoleLabel : user?.role === 'school_manager' ? 'SCHOOL ADMIN' : 'TEACHING STAFF'}</Badge>
          </div>
        </header>
        {/* Refinement 4 — global history back button + route breadcrumbs. */}
        <BackBar fallback={isState ? '/state' : user?.role === 'teacher' ? '/school/portal' : '/school'} />
        {saverActive && (
          <p className="saver-banner" role="status">
            Data Saver active{isState ? '' : ''}{saverReason && saverReason !== 'Manually enabled' ? ` — ${saverReason}` : ''}. Animations, gradients and chart graphics are replaced with raw text metrics for faster loading on 2G/3G.
          </p>
        )}
        <div className={`content ${!isState && user?.role === 'school_manager' ? 'content--with-publish-bar' : ''}`}><Outlet /></div>
      </main>

      {/* Refinement 7 — slide-out design system drawer (header triggered). */}
      <DesignDrawer />
      {/* Refinement 8 — sticky publishing controls for School Managers. */}
      {!isState && <PublishBar />}
      {/* Refinement 8 — 375px viewport simulator. */}
      {mobilePreview && <MobilePreviewFrame />}
    </div>
  );
}
