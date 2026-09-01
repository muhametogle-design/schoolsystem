import { Link, useLocation, useNavigate } from 'react-router-dom';

/**
 * Refinement 4 — Global history back button + visual breadcrumbs.
 *
 * Rendered on every sub-page, detail view and portal. The ← Back control
 * walks the browser history stack (`navigate(-1)`); when the tab was opened
 * directly on a deep link (no in-app history entry) it falls back to the
 * portal dashboard instead of leaving the app. Breadcrumbs describe the
 * active route, e.g. Dashboard > Student Directory > NG-10001.
 */

/** Human labels for static route segments across both portals. */
const SEGMENT_LABELS = {
  school: 'Dashboard',
  students: 'Student Directory',
  classes: 'Classes & Subjects',
  teachers: 'Staff Directory',
  attendance: 'Attendance',
  substitutions: 'Substitutions',
  syllabus: 'Syllabus Tracker',
  biometrics: 'Biometrics',
  billing: 'Billing',
  portal: 'My Teaching Day',
  'report-card': 'Report Card',
  state: 'State Dashboard',
  directory: 'School Directory',
  institutions: 'Institution Profile',
  lookup: 'Roll Number Lookup',
  backups: 'Encrypted Backups',
};

const ROLL_NUMBER = /^[A-Z]{2}-\d+$/;
const LEGACY_SID = /^NE-SID-/i;

function segmentLabel(segment, index, segments) {
  if (SEGMENT_LABELS[segment]) return SEGMENT_LABELS[segment];
  if (ROLL_NUMBER.test(segment) || LEGACY_SID.test(segment)) return `Profile ${segment}`;
  if (/^\d+$/.test(segment)) {
    const parent = segments[index - 1];
    if (parent === 'institutions') return `School #${segment}`;
    return `#${segment}`;
  }
  // Fallback: prettify any other dynamic slug.
  return segment.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function BackBar({ fallback = '/school' }) {
  const navigate = useNavigate();
  const location = useLocation();

  const segments = location.pathname.split('/').filter(Boolean);
  const crumbs = segments.map((segment, index) => ({
    label: segmentLabel(segment, index, segments),
    to: `/${segments.slice(0, index + 1).join('/')}`,
  }));

  const goBack = () => {
    // React Router records the history index on window.history.state; a deep
    // link opened in a fresh tab has idx 0/undefined — then go to the portal.
    const idx = window.history.state?.idx;
    if (typeof idx === 'number' && idx > 0) {
      navigate(-1);
    } else {
      navigate(fallback, { replace: true });
    }
  };

  return (
    <div className="back-bar no-print" role="navigation" aria-label="History and breadcrumbs">
      <button
        type="button"
        className="back-bar__button"
        onClick={goBack}
        title="Go back (falls back to the portal dashboard when there is no previous page)"
      >
        <span aria-hidden="true">←</span> Back
      </button>
      <ol className="breadcrumbs" aria-label="Breadcrumb">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={crumb.to} className="breadcrumbs__item">
              {index > 0 && (
                <span className="breadcrumbs__sep" aria-hidden="true">
                  &gt;
                </span>
              )}
              {isLast ? (
                <span className="breadcrumbs__current" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link className="breadcrumbs__link" to={crumb.to}>
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
