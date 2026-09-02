import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  discardDraft,
  publishUiConfig,
  saveDraft,
  selectActiveDesign,
  toggleMobileSim,
  clearDesignNotice,
} from '../features/design/designSlice';

/**
 * Sticky Publishing Control Bar (School Managers).
 *
 *   Save Progress     — persists the draft locally, live users unaffected.
 *   Test Mobile View  — 375px device-frame simulator for pre-publish checks.
 *   Push Live         — confirmation dialog, then syncs to the production API.
 */
export default function PublishBar() {
  const dispatch = useDispatch();
  const { dirty, mobileSim, publishing, notice, error } = useSelector((state) => state.design);
  const design = useSelector(selectActiveDesign);
  const [confirming, setConfirming] = useState(false);

  const pushLive = async () => {
    setConfirming(false);
    await dispatch(publishUiConfig(design));
  };

  return (
    <>
      <div className="publishbar" role="toolbar" aria-label="Publishing controls">
        <div className="publishbar__status">
          <span className={`publishbar__dot ${dirty ? 'is-dirty' : ''}`} aria-hidden="true" />
          <span className="publishbar__label">
            {dirty ? 'Unpublished design changes' : 'Design in sync with live'}
          </span>
          {(notice || error) && (
            <button
              type="button"
              className={`publishbar__note ${error ? 'is-error' : ''}`}
              onClick={() => dispatch(clearDesignNotice())}
              title="Dismiss"
            >
              {error ?? notice}
            </button>
          )}
        </div>
        <div className="publishbar__actions">
          <button type="button" className="btn btn--small" onClick={() => dispatch(saveDraft())} disabled={!dirty}>
            Save Progress
          </button>
          {dirty && (
            <button type="button" className="btn btn--small btn--ghost" onClick={() => dispatch(discardDraft())}>
              Discard
            </button>
          )}
          <button
            type="button"
            className={`btn btn--small ${mobileSim ? 'btn--primary' : ''}`}
            onClick={() => dispatch(toggleMobileSim())}
            aria-pressed={mobileSim}
          >
            {mobileSim ? 'Exit Mobile View' : 'Test Mobile View'}
          </button>
          <button
            type="button"
            className="btn btn--small btn--primary"
            onClick={() => setConfirming(true)}
            disabled={publishing}
          >
            {publishing ? 'Publishing…' : 'Push Live'}
          </button>
        </div>
      </div>

      {confirming && (
        <div className="modal-backdrop" onClick={() => setConfirming(false)}>
          <div className="modal modal--narrow" onClick={(event) => event.stopPropagation()}>
            <h2 className="card__title">Push design live?</h2>
            <p className="drawer__hint">
              The accent colour, typography and block layout will sync to the production
              database and apply to every student and teacher session immediately.
            </p>
            <ul className="publish-summary">
              <li><span className="swatch swatch--inline" style={{ background: design.accent }} /> Accent {design.accent}</li>
              <li>Typography: {design.font === 'sans' ? 'System Sans-Serif' : design.font === 'serif' ? 'Classic Serif' : 'Monospace Technical'}</li>
              <li>
                Visible blocks:{' '}
                {Object.entries(design.blocks ?? {}).filter(([, v]) => v).map(([k]) => k).join(', ') || 'none'}
              </li>
            </ul>
            <div className="toolbar toolbar--end">
              <button type="button" className="btn btn--ghost" onClick={() => setConfirming(false)}>Cancel</button>
              <button type="button" className="btn btn--primary" onClick={pushLive}>Confirm — Push Live</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
