import { useDispatch, useSelector } from 'react-redux';
import {
  ACCENT_PALETTE,
  BLOCK_DEFS,
  FONT_PRESETS,
  selectDraft,
  selectDrawerOpen,
  selectIsDirty,
  setAccent,
  setDrawerOpen,
  setFont,
  toggleBlock,
} from '../features/design/designSlice';
import { selectIsManager } from '../features/auth/authSlice';

/**
 * Refinement 7 — slide-out "Design & Layout Settings" sidebar drawer.
 *
 * Triggered from the header navigation. Managers edit; every other role gets
 * a read-only tour of the live theme. Each control rewires root CSS variables
 * through the design draft, so accent, typography and block visibility all
 * respond in the same click.
 */
export default function DesignDrawer() {
  const dispatch = useDispatch();
  const open = useSelector(selectDrawerOpen);
  const draft = useSelector(selectDraft);
  const dirty = useSelector(selectIsDirty);
  const isManager = useSelector(selectIsManager);

  if (!open) return null;
  const close = () => dispatch(setDrawerOpen(false));

  return (
    <div className="drawer-backdrop design-drawer-backdrop" role="presentation" onMouseDown={close}>
      <aside
        className="drawer design-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Design and Layout Settings"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="card__head card__head--row">
          <div>
            <h2 className="card__title">Design &amp; Layout Settings</h2>
            <span className="card__hint">
              {isManager
                ? 'Preview instantly — nothing reaches users until Push Live.'
                : 'Read-only view — only school managers can change the design system.'}
            </span>
          </div>
          <button type="button" className="btn btn--sm btn--ghost" onClick={close} aria-label="Close design settings">
            Close
          </button>
        </header>

        {!isManager && (
          <p className="alert alert--muted" role="note">
            🔒 The design system is managed by your school administrator.
          </p>
        )}

        {/* ---------------------- Global theme & colour ---------------------- */}
        <section className="design-section">
          <h3 className="design-section__title">Global Theme &amp; Colour System</h3>
          <p className="design-section__hint">
            One click re-skins buttons, badges, progress bars and borders across the whole platform.
          </p>
          <div className="swatch-grid" role="radiogroup" aria-label="Global accent colour">
            {ACCENT_PALETTE.map((colour) => {
              const selected = draft.accent === colour.hex;
              return (
                <button
                  key={colour.hex}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={!isManager}
                  className={`swatch-option ${selected ? 'is-selected' : ''}`}
                  onClick={() => dispatch(setAccent(colour.hex))}
                >
                  <span className="swatch-option__dot" style={{ background: colour.hex }} aria-hidden="true" />
                  <span className="swatch-option__name">{colour.name}</span>
                  <span className="swatch-option__hex mono">{colour.hex}</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* ------------------------- Typography control ---------------------- */}
        <section className="design-section">
          <h3 className="design-section__title">Typography Control</h3>
          <div className="font-options" role="radiogroup" aria-label="Typography preset">
            {FONT_PRESETS.map((preset) => {
              const selected = draft.font === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={!isManager}
                  className={`font-option font-option--${preset.id} ${selected ? 'is-selected' : ''}`}
                  onClick={() => dispatch(setFont(preset.id))}
                >
                  <span className="font-option__name">{preset.name}</span>
                  <span className="font-option__sample">{preset.sample}</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* ---------------------- Block & layout management ------------------ */}
        <section className="design-section">
          <h3 className="design-section__title">Block &amp; Layout Management</h3>
          <p className="design-section__hint">
            Show or hide dashboard blocks in real time — the dashboard re-flows instantly.
          </p>
          <ul className="block-toggles">
            {BLOCK_DEFS.map((block) => {
              const on = draft.blocks[block.id] !== false;
              return (
                <li key={block.id} className="block-toggle">
                  <span className="block-toggle__body">
                    <strong>{block.name}</strong>
                    <span className="block-toggle__hint">{block.hint}</span>
                  </span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={on}
                    aria-label={`${on ? 'Hide' : 'Show'} ${block.name}`}
                    disabled={!isManager}
                    className={`switch ${on ? 'is-on' : ''}`}
                    onClick={() => dispatch(toggleBlock(block.id))}
                  >
                    <span className="switch__thumb" aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        <footer className="design-drawer__foot">
          {isManager ? (
            <p className="muted">
              {dirty
                ? '● Unpublished draft — use the Publishing Control Bar to Save Progress or Push Live.'
                : 'All changes are in sync with the live production theme.'}
            </p>
          ) : (
            <p className="muted">These settings reflect the theme your school manager published.</p>
          )}
        </footer>
      </aside>
    </div>
  );
}
