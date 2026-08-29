/**
 * NE-EMIS official emblem.
 *
 * Hand-built inline SVG so the brand mark ships with the bundle — no icon
 * package, no external request. The shield geometry is deliberately simple
 * (three chevrons + a star) so it stays legible from 24px to 120px.
 */
export default function Logo({ size = 40, withWordmark = true, subtitle, compact = false }) {
  const height = size;
  const width = size * (compact ? 1 : 1);

  return (
    <span className="logo" style={{ '--logo-size': `${height}px` }}>
      <svg
        width={width}
        height={height}
        viewBox="0 0 48 56"
        role="img"
        aria-label="NE-EMIS emblem"
        className="logo__mark"
      >
        <defs>
          <linearGradient id="neemis-shield" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1d4ed8" />
            <stop offset="100%" stopColor="#0b2545" />
          </linearGradient>
        </defs>

        {/* Shield */}
        <path
          d="M24 1.5 45 8.5v20.2c0 12.4-8.6 21.9-21 25.8C11.6 50.6 3 41.1 3 28.7V8.5L24 1.5Z"
          fill="url(#neemis-shield)"
        />
        <path
          d="M24 4.2 42.2 10.3V28.7c0 11-7.6 19.5-18.2 23-10.7-3.5-18.2-12-18.2-23V10.3L24 4.2Z"
          fill="none"
          stroke="#f5c542"
          strokeWidth="1.1"
          opacity="0.85"
        />

        {/* Three ascending chevrons — growth through Class 1 to 12 */}
        <path d="M13 34.5 20 27l7 7.5" fill="none" stroke="#f5c542" strokeWidth="2.6"
              strokeLinecap="round" strokeLinejoin="round" />
        <path d="M13 27.5 20 20l7 7.5" fill="none" stroke="#ffffff" strokeWidth="2.6"
              strokeLinecap="round" strokeLinejoin="round" opacity="0.92" />
        <path d="M13 20.5 20 13l7 7.5" fill="none" stroke="#7fd1a8" strokeWidth="2.6"
              strokeLinecap="round" strokeLinejoin="round" />

        {/* Authority star */}
        <path
          d="M24 41.5l1.9 3.9 4.3.6-3.1 3 .8 4.3-3.9-2.1-3.9 2.1.8-4.3-3.1-3 4.3-.6Z"
          fill="#f5c542"
        />
      </svg>

      {withWordmark && (
        <span className="logo__text">
          <strong className="logo__title">NE-EMIS</strong>
          {!compact && (
            <span className="logo__subtitle">
              {subtitle ?? 'Education Management Information System'}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
