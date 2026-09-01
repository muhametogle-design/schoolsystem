import { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { setMobilePreview } from '../features/design/designSlice';

/**
 * Refinement 8 — "Test Mobile View" viewport simulator.
 *
 * Renders the genuinely-responsive app inside a realistic 375×667 handset
 * frame via a same-origin <iframe>. Because the iframe viewport really is
 * 375 CSS pixels wide, every fluid-grid and mobile breakpoint in styles.css
 * engages exactly as it would on a physical phone — student pages, teacher
 * rosters, pickers and all. The session cookie/token is origin-scoped, so the
 * preview boots already signed in.
 */
export default function MobilePreviewFrame() {
  const dispatch = useDispatch();
  const close = () => dispatch(setMobilePreview(false));

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const previewUrl = `${window.location.pathname}${window.location.search}`;

  return (
    <div className="device-overlay" role="dialog" aria-modal="true" aria-label="Mobile viewport simulator">
      <div className="device-overlay__head">
        <span className="device-overlay__title">
          📱 Test Mobile View — <span className="mono">375×667</span> viewport
        </span>
        <span className="device-overlay__hint">
          Live render: every mobile breakpoint and stacked layout is real.
        </span>
        <button type="button" className="btn btn--sm btn--ghost" onClick={close}>
          ✕ Exit simulator
        </button>
      </div>

      <div className="device-stage">
        <div className="device-frame" role="presentation">
          <span className="device-frame__notch" aria-hidden="true" />
          <div className="device-frame__chrome">
            <span className="device-frame__url mono">{previewUrl}</span>
          </div>
          <iframe
            className="device-frame__screen"
            title="Mobile preview of the current page"
            src={previewUrl}
          />
          <span className="device-frame__home" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
