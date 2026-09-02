import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Logo from './Logo';
import Badge from './Badge';
import BackBar from './BackBar';
import DesignDrawer from './DesignDrawer';
import PublishBar from './PublishBar';
import { logout, selectIsManager, selectIsStateAdmin, selectUser } from '../features/auth/authSlice';
import { fetchInstitutions, selectInstitutions } from '../features/schools/schoolSlice';
import {
  applyDesignToDom,
  fetchUiConfig,
  selectActiveDesign,
  toggleDrawer,
} from '../features/design/designSlice';

const SCHOOL_NAV = [
  { to: '/school', label: 'Dashboard', end: true },
  { to: '/school/students', label: 'Students' },
  { to: '/school/classes', label: 'Classes & subjects' },
  { to: '/school/syllabus', label: 'Syllabus tracker' },
  { to: '/school/teachers', label: 'Teachers' },
  { to: '/school/attendance', label: 'Attendance' },
  { to: '/school/billing', label: 'Billing', managerOnly: true },
];

const STATE_NAV = [
  { to: '/state', label: 'Live monitor', end: true },
  { to: '/state/directory', label: 'School directory' },
  { to: '/state/lookup', label: 'Roll number lookup' },
];

export default function Layout({ portal }) {
  const user = useSelector(selectUser);
  const isStateAdmin = useSelector(selectIsStateAdmin);
  const isManager = useSelector(selectIsManager);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const institutions = useSelector(selectInstitutions);
  const design = useSelector(selectActiveDesign);
  const mobileSim = useSelector((state) => state.design.mobileSim);
  const [navOpen, setNavOpen] = useState(false);
  const isState = portal === 'state';
  const nav = (isState ? STATE_NAV : SCHOOL_NAV).filter((item) => !item.managerOnly || user?.role === 'school_manager');

  useEffect(() => {
    if (isState) dispatch(fetchInstitutions());
    else dispatch(fetchUiConfig()); // published tenant design for every school role
  }, [isState, dispatch]);

  // DESIGN ENGINE: one config → :root CSS variables → whole-site restyle.
  useEffect(() => {
    applyDesignToDom(isState ? undefined : design);
  }, [design, isState]);

  // Auto-close the mobile nav after route changes.
  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  const onSignOut = async () => {
    await dispatch(logout());
    navigate('/', { replace: true });
  };

  const stateRoleLabel = isStateAdmin ? 'STATE ADMIN' : 'INSPECTOR PORTAL';
  const roleBadge = isState
    ? stateRoleLabel
    : user?.role === 'school_manager'
      ? 'SCHOOL ADMIN'
      : 'TEACHING STAFF';

  return (
    <div className={`shell shell--${portal} ${navOpen ? 'shell--nav-open' : ''}`}>
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
          <div className="topbar__lead">
            <button
              type="button"
              className="hamburger"
              aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
              aria-expanded={navOpen}
              onClick={() => setNavOpen((open) => !open)}
            >
              <span /><span /><span />
            </button>
            <div>
              <h1 className="topbar__title">{isState ? 'State Education Authority' : user?.school_name ?? 'School Portal'}</h1>
              <p className="topbar__sub">{isState ? (isStateAdmin ? 'Tenant provisioning, roll-number oversight & academic visibility' : 'Read-only academic oversight across licensed schools') : 'Tenant ERP · students, staff, curriculum, attendance and private billing'}</p>
            </div>
          </div>
          <div className="topbar__right">
            {!isState && isManager && (
              <button
                type="button"
                className="btn btn--small"
                onClick={() => dispatch(toggleDrawer(true))}
                title="Design & Layout Settings"
              >
                🎨 Design
              </button>
            )}
            <Badge status="Active">{roleBadge}</Badge>
          </div>
        </header>

        <div className={`content-viewport ${mobileSim ? 'content-viewport--sim' : ''}`}>
          {mobileSim && (
            <p className="sim-caption">Mobile preview · 375px — how students & teachers see this page</p>
          )}
          <div className={mobileSim ? 'device-frame' : undefined}>
            <div className="content">
              <BackBar portal={portal} />
              <Outlet />
            </div>
          </div>
        </div>
      </main>

      {!isState && isManager && <DesignDrawer />}
      {!isState && isManager && <PublishBar />}
    </div>
  );
}
