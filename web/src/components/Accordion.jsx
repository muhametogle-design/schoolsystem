import { useState } from 'react';

/**
 * Collapsible section used for Class 1-12 tracks and, nested, for subjects
 * (Grade 10 -> Mathematics -> student list).
 *
 * The disclosure state is intentionally local — accordions are presentational,
 * so keeping it out of Redux avoids re-rendering the whole dashboard.
 */
export default function Accordion({
  title,
  meta,
  right,
  defaultOpen = false,
  onOpen,
  children,
  level = 1,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = `acc-${Math.random().toString(36).slice(2, 9)}`;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    // Let the page lazy-load the section body the first time it is expanded.
    if (next && onOpen) onOpen();
  };

  return (
    <section className={`accordion accordion--level${level} ${open ? 'is-open' : ''}`}>
      <h3 className="accordion__heading">
        <button
          type="button"
          className="accordion__trigger"
          aria-expanded={open}
          aria-controls={id}
          onClick={toggle}
        >
          <span className="accordion__caret" aria-hidden="true">
            {open ? '▾' : '▸'}
          </span>
          <span className="accordion__title">{title}</span>
          {meta != null && <span className="accordion__meta">{meta}</span>}
          <span className="accordion__spacer" />
          {right && (
            <span className="accordion__right" onClick={(e) => e.stopPropagation()}>
              {right}
            </span>
          )}
        </button>
      </h3>
      <div className="accordion__panel" id={id} hidden={!open}>
        {open && children}
      </div>
    </section>
  );
}
