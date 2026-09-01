import { useDataSaver } from '../hooks/useDataSaver';

/**
 * Module 2+3 — progress meter that degrades to raw text in Data Saver mode.
 *
 * Normal mode: filled progress bar + percentage.
 * Data saver:  "34 of 90 units — 37.8%" (no bar graphic to render/paint).
 */
export default function ProgressMeter({ value, max = 100, unit = '%', label }) {
  const saver = useDataSaver();
  const pct = max ? Math.min(100, (value / max) * 100) : 0;

  if (saver) {
    return (
      <span className="meter-text">
        {label && <span className="meter-text__label">{label}</span>}
        <strong className="mono">{pct.toFixed(1)}{unit}</strong>
      </span>
    );
  }

  return (
    <span className="meter" title={label}>
      <span className="meter__track" aria-hidden="true">
        <span
          className={`meter__fill meter__fill--${pct >= 100 ? 'done' : 'open'}`}
          style={{ width: `${pct}%` }}
        />
      </span>
      <strong className="meter__value mono">{pct.toFixed(1)}{unit}</strong>
    </span>
  );
}
