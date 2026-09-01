import { useDispatch, useSelector } from 'react-redux';
import Modal from './Modal';
import {
  ACCENT_PALETTE,
  FONT_PRESETS,
  BLOCK_DEFS,
  publishDesignConfig,
  saveDraftLocal,
  selectConfirmPublish,
  selectDraft,
  selectIsDirty,
  selectLive,
  selectMobilePreview,
  selectPublishStatus,
  setConfirmPublish,
  setMobilePreview,
} from '../features/design/designSlice';
import { selectIsManager } from '../features/auth/authSlice';

/**
 * Refinement 8 — sticky Publishing Control Bar (School Managers only).
 *
 *   Save Progress    draft → localStorage; safe, private, survives reloads.
 *   Test Mobile View realistic 375px device frame rendering the live app.
 *   Push Live        confirmation dialog → production sync of theme variables
 *                    and layout configuration to the live database/API.
 */
export default function PublishBar() {
  const dispatch = useDispatch();
  const isManager = useSelector(selectIsManager);
  const draft = useSelector(selectDraft);
  const live = useSelector(selectLive);
  const dirty = useSelector(selectIsDirty);
  const publishStatus = useSelector(selectPublishStatus);
  const confirming = useSelector(selectConfirmPublish);
  const mobilePreview = useSelector(selectMobilePreview);

  if (!isManager) return null;

  const publishing = publishStatus === 'publishing';

  return (
    <>
      <div className="publish-bar no-print" role="region" aria-label="Publishing controls">
        <span className="publish-bar__status">
          <span className={`publish-bar__dot ${dirty ? 'is-dirty' : ''}`} aria-hidden="true" />
          {dirty ? (
            <>Unpublished draft changes</>
          ) : (
            <>
              In sync{live?.published_at ? ` — live since ${live.published_at.slice(0, 16).replace('T', ' ')}` : ' with defaults'}
            </>
          )}
        </span>

        <span className="publish-bar__actions">
          <button
            type="button"
            className="btn btn--sm btn--ghost"
            onClick={() => dispatch(saveDraftLocal())}
            title="Keep this draft on this device without showing it to other users"
          >
            💾 Save Progress
          </button>
          <button
            type="button"
            className={`btn btn--sm ${mobilePreview ? 'btn--primary' : 'btn--ghost'}`}
            onClick={() => dispatch(setMobilePreview(!mobilePreview))}
            aria-pressed={mobilePreview}
            title="Open the 375px mobile viewport simulator"
          >
            📱 Test Mobile View
          </button>
          <button
            type="button"
            className="btn btn--sm btn--primary"
            onClick={() => dispatch(setConfirmPublish(true))}
            disabled={!dirty && !live}
            title="Sync the draft theme to the live production database"
          >
            🚀 Push Live
          </button>
        </span>
      </div>

      {confirming && (
        <Modal title="Push design system live?" onClose={() => dispatch(setConfirmPublish(false))}>
          <p className="muted">
            This syncs the layout configuration, theme variables and dashboard blocks below to the
            live production database. Every student, teacher and manager will see them on their
            next page load. Nothing else in the school record is touched.
          </p>
          <dl className="publish-summary">
            <div>
              <dt>Accent colour</dt>
              <dd>
                <span
                  className="publish-summary__swatch"
                  style={{ background: draft.accent }}
                  aria-hidden="true"
                />
                {ACCENT_PALETTE.find((c) => c.hex === draft.accent)?.name ?? draft.accent}{' '}
                <span className="mono">{draft.accent}</span>
              </dd>
            </div>
            <div>
              <dt>Typography</dt>
              <dd>{FONT_PRESETS.find((f) => f.id === draft.font)?.name ?? draft.font}</dd>
            </div>
            <div>
              <dt>Dashboard blocks</dt>
              <dd>
                {BLOCK_DEFS.map((block) => (
                  <span key={block.id} className={`publish-summary__block ${draft.blocks[block.id] === false ? 'is-off' : ''}`}>
                    {draft.blocks[block.id] === false ? '✕' : '✓'} {block.name}
                  </span>
                ))}
              </dd>
            </div>
          </dl>
          <footer className="modal__foot">
            <button type="button" className="btn btn--ghost" onClick={() => dispatch(setConfirmPublish(false))} disabled={publishing}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={publishing}
              onClick={() => dispatch(publishDesignConfig(draft))}
            >
              {publishing ? 'Pushing…' : 'Confirm — Push Live'}
            </button>
          </footer>
        </Modal>
      )}
    </>
  );
}
