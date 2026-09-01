import { useEffect } from 'react';

/**
 * Shared dialog shell (refinement 1 UI). Escape closes, backdrop click closes,
 * focus lands on the panel for keyboard users.
 */
export default function Modal({ title, onClose, wide = false, children }) {
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className={`modal ${wide ? 'modal--wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="card__head card__head--row">
          <h2 className="card__title">{title}</h2>
          <button type="button" className="btn btn--sm btn--ghost" onClick={onClose} aria-label="Close dialog">
            Close
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
