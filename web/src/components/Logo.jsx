/**
 * Educta Matrix official emblem.
 *
 * Geometric brand mark: High-contrast matrix grid + graduation chevron + sovereign star.
 * Designed for crisp rendering from 20px to 160px across low-bandwidth displays.
 */
export default function Logo({ size = 40, withWordmark = true, subtitle, compact = false }) {
  const height = size;
  const width = size;

  return (
    <span className="logo" style={{ '--logo-size': `${height}px` }}>
      <svg
        width={width}
        height={height}
        viewBox="0 0 48 48"
        role="img"
        aria-label="Educta Matrix Emblem"
        className="logo__mark"
      >
        <defs>
          <linearGradient id="educta-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2563eb" />
            <stop offset="100%" stopColor="#0f172a" />
          </linearGradient>
          <linearGradient id="educta-accent" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#818cf8" />
          </linearGradient>
        </defs>

        {/* Matrix Shield Container */}
        <rect x="4" y="4" width="40" height="40" rx="10" fill="url(#educta-gradient)" />
        <rect x="5.5" y="5.5" width="37" height="37" rx="8.5" fill="none" stroke="#38bdf8" strokeWidth="1" opacity="0.4" />

        {/* Dynamic Matrix E Grid */}
        <path
          d="M15 15h18M15 24h13M15 33h18"
          stroke="#ffffff"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        <path
          d="M15 15v18"
          stroke="#38bdf8"
          strokeWidth="3.2"
          strokeLinecap="round"
        />

        {/* Sovereign Telemetry Node */}
        <circle cx="34" cy="24" r="3" fill="#38bdf8" />
      </svg>

      {withWordmark && (
        <span className="logo__text">
          <strong className="logo__title">Educta Matrix</strong>
          {!compact && (
            <span className="logo__subtitle">
              {subtitle ?? 'The Unified Operating System for Regional Education'}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
