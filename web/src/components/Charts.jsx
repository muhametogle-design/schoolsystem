/**
 * Chart primitives built from plain divs and inline SVG.
 *
 * No charting dependency and no icon set: bars, fills and a single SVG
 * polyline cover the KPI cards, distribution charts and trends the brief asks
 * for, and they print cleanly for the report card.
 */

export function KpiCard({ label, value, hint, tone = 'neutral' }) {
  return (
    <article className={`kpi kpi--${tone}`}>
      <span className="kpi__label">{label}</span>
      <strong className="kpi__value">{value ?? '—'}</strong>
      {hint && <span className="kpi__hint">{hint}</span>}
    </article>
  );
}

/** Horizontal bars: label, bar, value. Used for distributions and rosters. */
export function BarList({ items, max, unit = '' }) {
  const ceiling = max ?? Math.max(1, ...items.map((i) => i.value ?? 0));
  return (
    <ul className="bar-list">
      {items.map((item) => {
        const pct = ceiling ? Math.min(100, ((item.value ?? 0) / ceiling) * 100) : 0;
        return (
          <li key={item.label} className="bar-list__row">
            <span className="bar-list__label" title={item.label}>
              {item.label}
            </span>
            <span className="bar-list__track">
              <span
                className="bar-list__fill"
                style={{ width: `${pct}%`, background: item.colour ?? 'var(--brand-600)' }}
              />
            </span>
            <span className="bar-list__value">
              {item.value ?? 0}
              {unit}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Vertical daily trend rendered as an SVG polyline over a bar column set. */
export function TrendChart({ points, height = 140, targetLabel = 'Attendance %' }) {
  if (!points || points.length === 0) {
    return <p className="empty">No attendance recorded in this window.</p>;
  }

  const width = 620;
  const padding = { top: 12, right: 8, bottom: 26, left: 34 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const values = points.map((p) => p.value ?? 0);
  const step = plotW / Math.max(1, points.length);
  const barW = Math.max(4, Math.min(22, step * 0.55));

  const coords = points.map((p, i) => ({
    x: padding.left + step * (i + 0.5),
    y: padding.top + plotH - ((p.value ?? 0) / 100) * plotH,
    ...p,
  }));

  const polyline = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');

  return (
    <svg
      className="trend"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={targetLabel}
      preserveAspectRatio="none"
    >
      {/* gridlines at 0 / 50 / 100 */}
      {[0, 50, 100].map((v) => {
        const y = padding.top + plotH - (v / 100) * plotH;
        return (
          <g key={v}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y}
              y2={y}
              stroke="var(--grid)"
              strokeWidth="1"
            />
            <text x={4} y={y + 4} className="trend__axis">
              {v}
            </text>
          </g>
        );
      })}

      {coords.map((c, i) => (
        <rect
          key={i}
          x={c.x - barW / 2}
          y={c.y}
          width={barW}
          height={Math.max(0, padding.top + plotH - c.y)}
          fill="var(--brand-200)"
          rx="2"
        />
      ))}

      <polyline points={polyline} fill="none" stroke="var(--brand-700)" strokeWidth="2.2" />

      {coords.map((c, i) => (
        <circle key={`p${i}`} cx={c.x} cy={c.y} r="2.6" fill="var(--brand-700)">
          <title>{`${c.label}: ${c.value}%`}</title>
        </circle>
      ))}

      {coords.map((c, i) =>
        i % Math.ceil(points.length / 7) === 0 ? (
          <text key={`l${i}`} x={c.x} y={height - 8} className="trend__axis" textAnchor="middle">
            {c.label}
          </text>
        ) : null
      )}
    </svg>
  );
}

/** Segmented single-bar composition, e.g. the tuition status mix. */
export function StackedBar({ segments, total }) {
  const computed = segments.reduce((acc, s) => acc + s.value, 0);
  const sum = total ?? (computed || 1);
  return (
    <div className="stacked">
      <div className="stacked__bar">
        {segments.map((s) => (
          <span
            key={s.label}
            className="stacked__segment"
            style={{ width: `${(s.value / sum) * 100}%`, background: s.colour }}
            title={`${s.label}: ${s.value}`}
          />
        ))}
      </div>
      <ul className="stacked__legend">
        {segments.map((s) => (
          <li key={s.label}>
            <span className="swatch" style={{ background: s.colour }} aria-hidden="true" />
            {s.label}
            <strong>{s.value}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
