/**
 * Status representation is pure CSS + text — the design brief calls for zero
 * icon imports, so every state is conveyed by colour, border and wording.
 */

const TONE_BY_STATUS = {
  // Fee / payment statuses
  PAID: 'ok',
  PENDING: 'warn',
  NOT_PAID: 'danger',
  SCHOLARSHIP: 'info',
  OUTSTANDING: 'warn',

  // Attendance
  Present: 'ok',
  Absent: 'danger',
  Late: 'warn',
  Excused: 'muted',

  // Accreditation / compliance
  Active: 'ok',
  COMPLIANT: 'ok',
  SUSPENDED: 'danger',
  'RED ALARM': 'danger',

  // Publication valve
  PUBLISHED: 'ok',
  DRAFT: 'muted',
};

export default function Badge({ status, tone, children, title }) {
  const resolvedTone = tone ?? TONE_BY_STATUS[status] ?? 'muted';
  return (
    <span className={`badge badge--${resolvedTone}`} title={title}>
      {children ?? status}
    </span>
  );
}

/** Small square swatch used in chart legends (replaces a legend icon). */
export function Swatch({ colour }) {
  return <span className="swatch" style={{ background: colour }} aria-hidden="true" />;
}
