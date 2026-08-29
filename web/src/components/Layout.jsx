import { useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import Logo from './Logo';
import Badge from './Badge';
import { logout, selectUser } from '../features/auth/authSlice';
import {
  fetchInstitutions,
  selectInstitutions,
} from '../features/schools/schoolSlice';

const SCHOOL_NAV = [
  { to: '/school', label: 'Dashboard', end: true },
  { to: '/school/students', label: 'Students' },
  { to: '/school/attendance', label: 'Attendance' },
];

const STATE_NAV = [
  { to: '/state', label: 'Live Monitor', end: true },
  { to: '/state/lookup', label: 'NE-SID Lookup' },
];

export default function Layout({ portal }) {
  const user = useSelector(selectUser);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const institutions = useSelector(selectInstitutions);

  const isState = portal === 'state';
  const nav = isState ? STATE_NAV : SCHOOL_NAV;

  useEffect(() => {
    if (isState) dispatch(fetchInstitutions());
  }, [isState, dispatch]);

  const onSignOut = async () => {
    await dispatch(logout());
    navigate('/', { replace: true });
  };

  return (
    <div className={`shell shell--${portal}`}>
      <aside className="sidebar">
        <div className="sidebar__brand">
          <Logo size={38} subtitle={isState ? 'Regional State Authority' : undefined} />
        </div>

        <nav className="sidebar__nav">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `navlink ${isActive ? 'is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {isState && (
          <div className="sidebar__section">
            <h2 className="sidebar__heading">Institutional Directory</h2>
            <ul className="institution-list">
              {institutions.map((inst) => (
                <li key={inst.id}>
                  <NavLink
                    to={`/state/institutions/${inst.id}`}
                    className={({ isActive }) =>
                      `institution ${isActive ? 'is-active' : ''}`
                    }
                  >
                    <span className="institution__name">{inst.school_name}</span>
                    <span className="institution__meta">
                      {inst.student_count} students · {inst.teacher_count} teachers
                    </span>
                  </NavLink>
                </li>
              ))}
              {institutions.length === 0 && (
                <li className="institution institution--empty">No institutions registered</li>
              )}
            </ul>
          </div>
        )}

        <div className="sidebar__foot">
          <div className="user-chip">
            <span className="user-chip__name">{user?.first_name} {user?.last_name}</span>
            <span className="user-chip__role">{user?.role?.replace(/_/g, ' ')}</span>
          </div>
          <button type="button" className="btn btn--ghost btn--block" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1 className="topbar__title">
              {isState ? 'State Education Authority' : user?.school_name ?? 'School Portal'}
            </h1>
            <p className="topbar__sub">
              {isState
                ? 'Regional compliance monitoring & institutional oversight'
                : 'Tenant ERP · attendance, assessment and billing'}
            </p>
          </div>
          <div className="topbar__right">
            <Badge status={user?.role === 'state_inspector' ? 'Active' : 'Active'}>
              {user?.role === 'state_inspector'
                ? 'STATE PORTAL'
                : user?.role === 'school_manager'
                  ? 'SCHOOL ADMIN'
                  : 'TEACHING STAFF'}
            </Badge>
          </div>
        </header>

        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
