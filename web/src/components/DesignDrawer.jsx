import { useDispatch, useSelector } from 'react-redux';
import {
  ACCENT_CHOICES,
  BLOCK_DEFS,
  FONT_CHOICES,
  selectActiveDesign,
  toggleDrawer,
  updateDraft,
} from '../features/design/designSlice';

/**
 * 'Design & Layout Settings' slide-out drawer (School Manager only).
 *
 * Every control edits the local draft, which the design engine applies to
 * :root CSS variables immediately — buttons, badges, progress bars and
 * borders recolour in real time. Nothing reaches other users until the
 * Publishing Control Bar's 'Push Live'.
 */
export default function DesignDrawer() {
  const dispatch = useDispatch();
  const open = useSelector((state) => state.design.drawerOpen);
  const design = useSelector(selectActiveDesign);

  const close = () => dispatch(toggleDrawer(false));

  return (
    <>
      {open && <div className="drawer-backdrop" onClick={close} aria-hidden="true" />}
      <aside className={`drawer ${open ? 'is-open' : ''}`} aria-hidden={!open} aria-label="Design and layout settings">
        <header className="drawer__head">
          <div>
            <h2 className="drawer__title">Design & Layout Settings</h2>
            <p className="drawer__sub">Changes preview instantly for you only — push live to publish.</p>
          </div>
          <button type="button" className="drawer__close" onClick={close} aria-label="Close design settings">✕</button>
        </header>

        <section className="drawer__section">
          <h3 className="drawer__heading">Global accent colour</h3>
          <p className="drawer__hint">Applies to buttons, badges, progress bars and borders simultaneously.</p>
          <div className="swatch-row" role="radiogroup" aria-label="Accent colour">
            {ACCENT_CHOICES.map((hex) => (
              <button
                key={hex}
                type="button"
                role="radio"
                aria-checked={design.accent === hex}
                className={`swatch ${design.accent === hex ? 'is-active' : ''}`}
                style={{ background: hex }}
                title={hex}
                onClick={() => dispatch(updateDraft({ accent: hex }))}
              >
                {design.accent === hex ? '✓' : ''}
              </button>
            ))}
          </div>
        </section>

        <section className="drawer__section">
          <h3 className="drawer__heading">Typography</h3>
          <div className="drawer__options">
            {FONT_CHOICES.map((font) => (
              <label key={font.id} className={`option-tile ${design.font === font.id ? 'is-active' : ''}`}>
                <input
                  type="radio"
                  name="font"
                  checked={design.font === font.id}
                  onChange={() => dispatch(updateDraft({ font: font.id }))}
                />
                <span className="option-tile__label" style={{ fontFamily: font.stack }}>{font.label}</span>
                <span className="option-tile__sample" style={{ fontFamily: font.stack }}>AaBbCc 0123</span>
              </label>
            ))}
          </div>
        </section>

        <section className="drawer__section">
          <h3 className="drawer__heading">Dashboard blocks</h3>
          <p className="drawer__hint">Show or hide blocks across student and dashboard pages in real time.</p>
          <div className="drawer__options">
            {BLOCK_DEFS.map((block) => {
              const visible = design.blocks?.[block.id] !== false;
              return (
                <label key={block.id} className="toggle-row">
                  <span className="toggle-row__label">{block.label}</span>
                  <input
                    type="checkbox"
                    checked={visible}
                    onChange={() => dispatch(updateDraft({ blocks: { [block.id]: !visible } }))}
                  />
                  <span className={`toggle ${visible ? 'is-on' : ''}`} aria-hidden="true" />
                </label>
              );
            })}
          </div>
        </section>
      </aside>
    </>
  );
}
