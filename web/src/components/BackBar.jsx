import { useLocation, useNavigate, Link } from 'react-router-dom';

/**
 * Global navigation aid: sticky ← Back button + visual breadcrumbs.
 *
 * Back uses real browser history (navigate(-1)); when the tab has no history
 * stack (deep link, new tab) it falls back to the portal dashboard.
 */

const SEGMENT_LABELS = {
  school: 'Dashboard',
  state: 'Live Monitor',
  students: 'Student Directory',
  classes: 'Classes & Subjects',
  teachers: 'Teachers',
  attendance: 'Attendance',
  billing: 'Billing',
  syllabus: 'Syllabus Tracker',
  directory: 'School Directory',
  lookup: 'Roll Number Lookup',
  institutions: 'Institutions',
  'report-card': 'Report Card',
  'my-day': 'My Teaching Day',
};

export default function BackBar({ portal }) {
  const navigate = useNavigate();
  const location = useLocation();
  const home = portal === 'state' ? '/state' : '/school';

  const segments = location.pathname.split('/').filter(Boolean);
  // The portal root has no breadcrumb trail and needs no back affordance.
  if (segments.length <= 1) return null;

  const goBack = () => {
    // React Router v6 keeps an history index on state; idx>0 means there is a
    // real in-app stack to pop. Otherwise: graceful fallback to the dashboard.
    if (window.history.state && window.history.state.idx > 0) {
      navigate(-1);
    } else {
      navigate(home, { replace: true });
    }
  };

  const crumbs = segments.map((segment, index) => {
    const path = `/${segments.slice(0, index + 1).join('/')}`;
    const label = SEGMENT_LABELS[segment] ?? decodeURIComponent(segment);
    return { path, label, last: index === segments.length - 1 };
  });

  return (
    <div className="backbar" role="navigation" aria-label="Breadcrumb">
      <button type="button" className="backbar__btn" onClick={goBack}>
        <span aria-hidden="true">←</span> Back
      </button>
      <ol className="breadcrumbs">
        {crumbs.map((crumb) => (
          <li key={crumb.path} className="breadcrumbs__item">
            {crumb.last ? (
              <span className="breadcrumbs__current" aria-current="page">{crumb.label}</span>
            ) : (
              <Link to={crumb.path} className="breadcrumbs__link">{crumb.label}</Link>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
