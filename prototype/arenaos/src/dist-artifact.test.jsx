import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/dom';
import { JSDOM } from 'jsdom';

/**
 * Guards the `npm run build` artefacts in dist/ — the files a phone actually
 * opens. src/ArenaOS.test.jsx covers the source; three things can only be
 * caught here:
 *
 *  1. an inline <script> body truncated by the HTML parser. That is why the
 *     vendored React files are loaded with src="" and never pasted inline:
 *     react-dom.production.min.js embeds `<script>` plus a closing tag inside
 *     one of its own string literals (its own defence against this hazard).
 *  2. a bare `useState` surviving the ES-module strip. esbuild rewrites JSX to
 *     React.createElement but leaves hook calls alone, so the bundle rendered
 *     an empty root until stripModule() rebinding landed — the boot test below
 *     is what keeps it from regressing silently.
 *  3. the emitted bundle failing to boot outside Vite's transform pipeline.
 *
 * These tests read dist/, so run `npm run build` before `npm test`.
 */

const dist = (f) => readFileSync(`dist/${f}`, 'utf8');

describe('dist/ArenaOS.html', () => {
  it('parses as a document with no truncated script bodies', () => {
    const html = dist('ArenaOS.html');
    const doc = new JSDOM(html).window.document;
    const scripts = [...doc.querySelectorAll('script')];

    expect(scripts.length).toBeGreaterThanOrEqual(3);
    expect(scripts.filter((s) => s.getAttribute('src')).length).toBeGreaterThanOrEqual(2);
    for (const s of scripts) {
      if (s.getAttribute('src')) {
        expect(s.getAttribute('src')).toMatch(/^\.\/ArenaOS\./);
      } else {
        // jsdom never runs these, so an inline body survives as source. Had the
        // parser cut it short, everything after it would have been re-parsed as
        // markup and the script count would no longer balance.
        expect(s.textContent.length).toBeGreaterThan(1000);
        expect(s.textContent).toContain('ReactDOM.createRoot');
      }
    }
    expect((html.match(/<script\b/g) || []).length).toBe((html.match(/<\/script>/g) || []).length);
    expect(doc.querySelector('link[rel="stylesheet"]')?.getAttribute('href')).toBe(
      './ArenaOS.styles.css'
    );
  });

  it('ships a stylesheet carrying the utilities the markup uses', () => {
    const css = dist('ArenaOS.styles.css');
    for (const cls of ['.bg-slate-950', '.bg-slate-900', '.max-w-6xl', '.animate-fadeIn']) {
      expect(css).toContain(cls);
    }
  });

  it('vendors React/ReactDOM byte-for-byte, so nothing was escaped or truncated', () => {
    const pkg = (name, file) =>
      readFileSync(`node_modules/${name}/umd/${file}`, 'utf8');
    expect(dist('ArenaOS.vendor.react.js')).toBe(pkg('react', 'react.production.min.js'));
    expect(dist('ArenaOS.vendor.react-dom.js')).toBe(pkg('react-dom', 'react-dom.production.min.js'));
  });
});

describe('dist/ArenaOS.app.js', () => {
  it('boots in a plain browser page and runs the fixed flows', async () => {
    // The UMD files reach the globals exactly as a browser delivers them. Run
    // inside vitest's own jsdom: React's scheduler needs MessageChannel, which
    // a bare vm context does not provide, so a second jsdom instance would hang
    // with an empty root for reasons that have nothing to do with the product.
    const umd = (file) =>
      new Function('window', 'self', 'global', 'module', 'exports', 'define', dist(file));
    for (const f of ['ArenaOS.vendor.react.js', 'ArenaOS.vendor.react-dom.js']) {
      umd(f)(globalThis, globalThis, globalThis, undefined, undefined, undefined);
    }
    expect(typeof globalThis.ReactDOM.createRoot).toBe('function');

    const bundle = dist('ArenaOS.app.js');
    expect(bundle).toContain('const useState = React.useState;'); // the fix-2 regression guard

    const container = document.createElement('div');
    container.id = 'root';
    document.body.appendChild(container);
    // The bundle mounts itself; production React only flushes deterministically
    // under act(), so drive it through the exported component instead of the
    // file's own mount line.
    const body = bundle.replace(/ReactDOM\.createRoot\([\s\S]*$/, 'globalThis.__ArenaOS = ArenaOS;');
    new Function(body)();
    expect(typeof globalThis.__ArenaOS).toBe('function');

    // The UMD React is a *production* build: act() and flushSync are absent from
    // it, so we rely on its scheduler (MessageChannel exists in this jsdom) and
    // wait for each state change, exactly like a browser test would.
    const root = globalThis.ReactDOM.createRoot(container);
    root.render(globalThis.React.createElement(globalThis.__ArenaOS));

    const q = (sel, scope = container) => [...scope.querySelectorAll(sel)];
    const text = () => container.textContent || '';
    const button = (re, scope = container) =>
      [...scope.querySelectorAll('button')].find((b) => re.test(b.textContent));
    const labelControl = (re) => {
      const label = q('label').find((l) => re.test(l.textContent));
      const el = label && document.getElementById(label.getAttribute('for'));
      if (!el) throw new Error(`label "${re}" has no control — fix 9 regressed`);
      return el;
    };
    const type = (input, value) => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      setter.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    };
    const tap = (el) => el.dispatchEvent(new MouseEvent('click', { bubbles: true }));

    await waitFor(() => expect(text()).toMatch(/System Login/));
    // fix 9: every control in the shipped bundle is labelled
    expect(q('input').length).toBeGreaterThan(0);
    expect(q('input').every((i) => !!document.getElementById(i.id))).toBe(true);

    tap(button(/School Manager/));
    // the tab rename is a React state update, so let it flush before reading
    await waitFor(() => expect(labelControl(/Username/i)).toBeTruthy());
    type(labelControl(/Username/i), 'Admin '); // fix 7: space + capital A
    type(labelControl(/Password/i), 'admin123');
    tap(button(/Authenticate/));
    await waitFor(() => expect(text()).toMatch(/Syllabus & Curriculum Administration/));

    // fix 1: the Log Topics modal reflects its own toggles
    const card = q('.rounded-xl').find((c) => /Mathematics/.test(c.textContent));
    tap(button(/Log Topics/, card));
    await waitFor(() => expect(text()).toMatch(/Curriculum Units/));
    tap(q('input[type="checkbox"]').find((c) => !c.checked));
    await waitFor(() => expect(text()).toMatch(/75% covered · target 85%/));
    expect(card.textContent).toMatch(/Curriculum Progress: 75%/);

    // fix 8: a new unit re-weights the plan without closing the modal
    // (3 covered of 4 -> 3 of 5 = 60%; the new unit starts uncovered)
    tap(button(/Add Unit/));
    await waitFor(() => expect(text()).toMatch(/60% covered · target 85% · 5 units/));

    tap(button(/Logout/));
    await waitFor(() => expect(text()).toMatch(/System Login/));

    root.unmount();
    container.remove();
    delete globalThis.__ArenaOS;
  });
});
