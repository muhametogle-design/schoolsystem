#!/usr/bin/env node
/**
 * Builds the no-package-manager variant of the prototype: dist/ArenaOS.html
 *
 *   node tools/make-single-file.mjs          self-contained (default)
 *   node tools/make-single-file.mjs --cdn    CDN variant, smallest file
 *
 * Why this exists: `npm install && npm run dev` is the normal workflow, but on a
 * phone (Termux) you may be offline, on metered data, or mid-toolchain-install.
 * The default output needs neither npm nor a network:
 *
 *   - src/ArenaOS.jsx is compiled with esbuild at build time — no Babel in the
 *     browser, no runtime transpile cost on a phone
 *   - the Tailwind stylesheet is the one `vite build` already emitted
 *     (dist/index.css), so this file can never drift from `npm run dev`
 *   - React/ReactDOM UMD builds are copied verbatim from node_modules
 *   - the fadeIn shim from src/index.css is inlined
 *
 * Two files rather than one, because of how HTML parsing works: inline
 * <script> bodies end at the first `</script` token the parser finds, and
 * react-dom.production.min.js deliberately embeds `<script>` plus a closing tag
 * inside one of its own string literals. Any escaping scheme either truncates
 * the page or corrupts the bundle, and no regex can tell those apart
 * (a previous version of this generator learned that the hard way). So the
 * vendored files load via src="" — byte-identical — while our own compiled
 * output, checked for the hazardous tokens, is inlined into the host HTML.
 *
 * Output is a build artefact: edit src/ArenaOS.jsx, never dist/.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync, renameSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const useCdn = process.argv.includes('--cdn');

const REACT_VERSION = require('react/package.json').version;
const MOUNT = "ReactDOM.createRoot(document.getElementById('root')).render(ArenaOS);";
const VENDORED = [
  ['ArenaOS.vendor.react.js', 'react', 'umd/react.production.min.js'],
  ['ArenaOS.vendor.react-dom.js', 'react-dom', 'umd/react-dom.production.min.js'],
];
const CDN = {
  react: `https://unpkg.com/react@${REACT_VERSION}/umd/react.production.min.js`,
  reactDom: `https://unpkg.com/react-dom@${REACT_VERSION}/umd/react-dom.production.min.js`,
  tailwind: 'https://cdn.tailwindcss.com/3.4.13',
};

const DIST_INDEX = `<!doctype html>
<!-- GENERATED alongside dist/ by tools/make-single-file.mjs -->
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ArenaOS - dist index</title>
<style>
  body{font:15px/1.6 system-ui;background:#020617;color:#e2e8f0;margin:0;padding:32px}
  a{display:block;padding:14px 16px;margin:10px 0;border:1px solid #1e293b;border-radius:10px;color:#60a5fa;text-decoration:none;background:#0f172a}
  a:hover{border-color:#334155}
  small{color:#94a3b8;display:block;margin-top:2px}
</style></head><body>
<h1>ArenaOS prototype</h1>
<p>Three ways to open it from this folder:</p>
<a href="./ArenaOS.html"><strong>Self-contained</strong><small>React and Tailwind vendored from node_modules. No npm, no network.</small></a>
<a href="./index.html"><strong>Vite production build</strong><small>The real bundler output: index.html + app.js + index.css.</small></a>
<a href="./ArenaOS.cdn.html"><strong>CDN variant</strong><small>Smallest file; needs network. Regenerate with node tools/make-single-file.mjs --cdn.</small></a>
</body></html>
`;

/* ---------------------------------------------------------------- component */

// The component is authored as an ES module; a plain <script> has no module
// loader, so strip the module syntax rather than keeping a second copy.
function stripModule(src) {
  // Collect react's named bindings before deleting the import lines. esbuild's
  // classic JSX transform resolves the `React` identifier itself, but a bare
  // `useState` would be left as a global that only happens to exist inside a
  // bundler's module scope — it silently produced an empty root once. Rebinding
  // each name off the UMD global keeps the output a genuinely plain script.
  const named = new Set();
  const capture = (names) =>
    names
      .split(',')
      .map((n) => n.trim().split(/\s+as\s+/).pop())
      .filter(Boolean)
      .forEach((n) => named.add(n));

  // `import React, { useState } from 'react'`  ->  drop the braces, keep the rest
  src = src.replace(
    /^(import\s+React)\s*,\s*\{([^}]*)\}\s*from\s*['"]react['"];?\s*$/gm,
    (_, head, names) => {
      capture(names);
      return `${head} from 'react';`.replace(/import React from 'react';?/, '');
    }
  );
  // `import { useState, useEffect } from 'react'`
  src = src.replace(/^import\s*\{([^}]*)\}\s*from\s*['"]react['"];?\s*$/gm, (_, names) => {
    capture(names);
    return '';
  });
  src = src
    .replace(/^import\s+React[^\n]*\n/m, '')
    .replace(/^export\s+default\s+/m, 'const ArenaOS = ')
    .replace(/^export\s+/gm, '');

  const bindings = [...named].map((n) => `const ${n} = React.${n};`).join('\n');
  return bindings ? `${bindings}\n${src.replace(/^/m, '')}` : src;
}

const jsxSource = readFileSync(resolve(root, 'src/ArenaOS.jsx'), 'utf8');
const stripped = stripModule(jsxSource);
if (/\buseState\s*\(/.test(stripped) && !stripped.includes('const useState = React.useState;')) {
  throw new Error('useState survived without a React binding — plain <script> would render an empty root');
}
if (/^\s*(import|export)\s/m.test(stripped)) {
  throw new Error('module syntax survived the strip — update stripModule()');
}

const { transformSync } = require('esbuild');
const { code: componentJs } = transformSync(stripped, { loader: 'jsx', jsx: 'transform' });

// Only safe to inline if the HTML parser cannot find a termination token in it.
// Returns null instead of throwing: the caller then loads dist/ArenaOS.app.js,
// which is always written anyway, so the build never dead-ends.
const inlineSafe = (js) =>
  /<\/?script|<!--|-->/i.test(js) ? null : js;

/* -------------------------------------------------------------------- style */

// Only the --cdn variant needs this: it has no built stylesheet to reuse.
const STYLE_SHIM = [
  '@keyframes fadeIn {',
  '  from { opacity: 0; transform: translateY(-4px); }',
  '  to { opacity: 1; transform: none; }',
  '}',
  '.animate-fadeIn { animation: fadeIn 160ms ease-out; }',
  'html, body, #root { min-height: 100%; background-color: #020617; }',
].join('\n');

// Reuse dist/index.css from the Vite build instead of running a second Tailwind
// pipeline here: one source of truth, so this file can never drift from
// `npm run dev`. (It also keeps tailwind v3 out of the dependency tree — v3 and
// v4 are not co-installable under one name, and the Vite plugin needs v4's
// `@import 'tailwindcss'` syntax.)
function viteStyles() {
  const built = resolve(root, 'dist/index.css');
  if (!existsSync(built)) {
    throw new Error('dist/index.css missing — run `vite build` first (npm run build does this for you)');
  }
  const css = readFileSync(built, 'utf8');
  // The shim already lives in src/index.css, hence inside dist/index.css; assert
  // rather than re-append so a silent drop in the Vite build fails loudly here.
  if (!css.includes('.animate-fadeIn')) {
    throw new Error('dist/index.css has no .animate-fadeIn — the src/index.css shim went missing');
  }
  return css;
}

function vendoredUmd(pkg, file) {
  // "exports" blocks require.resolve for these paths, so join from the package root.
  const dir = dirname(require.resolve(`${pkg}/package.json`));
  const abs = resolve(dir, file);
  return existsSync(abs) ? readFileSync(abs, 'utf8') : null;
}

/* -------------------------------------------------------------------- build */

async function build() {
  mkdirSync(resolve(root, 'dist'), { recursive: true });
  // The bundle is always emitted — the self-contained page inlines this same
  // code, and the --cdn page loads it as a plain file.
  writeFileSync(resolve(root, 'dist/ArenaOS.app.js'), `${componentJs}\n${MOUNT}\n`);
  writeFileSync(resolve(root, 'dist/index.html'), DIST_INDEX);

  if (useCdn) {
    // One tiny file, three CDN tags, unpkg -> jsdelivr fallback, loud failure
    // instead of a blank page. Needs network.
    const html = `<!doctype html>
<!-- GENERATED by tools/make-single-file.mjs --cdn. Edit src/ArenaOS.jsx, not this file. -->
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ArenaOS - Standalone Prototype (CDN build)</title>
    <meta name="description" content="Needs network for React, ReactDOM and the Tailwind Play CDN." />
    <style>${STYLE_SHIM}</style>
    <script>
      (function () {
        var chain = [
          ${JSON.stringify(CDN.react)}, ${JSON.stringify(CDN.reactDom)}, ${JSON.stringify(CDN.tailwind)},
          ${JSON.stringify('./ArenaOS.app.js')}
        ];
        var i = 0;
        function fail(where) {
          document.getElementById('root').innerHTML =
            '<p style="font:14px system-ui;color:#fca5a5;padding:24px">Could not load ' + where +
            '. This build needs network. Offline: run node tools/make-single-file.mjs ' +
            '(no flag) and open ArenaOS.single-file.html instead.</p>';
        }
        function next() {
          if (i >= chain.length) return;
          var url = chain[i++];
          var s = document.createElement('script');
          s.src = url;
          s.onload = function () {
            // The Play CDN emits no utilities unless told to scan the DOM.
            if (window.tailwind) {
              tailwind.config = { corePlugins: { preflight: true }, content: ['body'] };
            }
            next();
          };
          s.onerror = function () {
            if (/unpkg\\.com/.test(url)) {
              chain.splice(i, 0, url.replace('unpkg.com', 'cdn.jsdelivr.net'));
              next();
            } else {
              fail(url.split('/')[2] || url);
            }
          };
          document.head.appendChild(s);
        }
        next();
      })();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <noscript><p style="font:14px system-ui;color:#e2e8f0;padding:24px">This prototype is a React app - enable JavaScript.</p></noscript>
  </body>
</html>
`;
    writeFileSync(resolve(root, 'dist/ArenaOS.cdn.html'), html);
    console.log('wrote ArenaOS.cdn.html + ArenaOS.app.js — CDN build, needs network');
    return;
  }

  const scripts = [];
  for (const [file, pkg, umd] of VENDORED) {
    const code = vendoredUmd(pkg, umd);
    if (!code) {
      throw new Error(`missing ${pkg} UMD build in node_modules — run \`npm install\` first`);
    }
    writeFileSync(resolve(root, 'dist', file), code);
    scripts.push(`<script src="./${file}"></script>`);
    console.log(`  vendored ${file} (${(code.length / 1024).toFixed(0)} kB, ${pkg} ${REACT_VERSION})`);
  }

  const css = viteStyles();
  writeFileSync(resolve(root, 'dist/ArenaOS.styles.css'), css);
  console.log(`  wrote ArenaOS.styles.css (${(css.length / 1024).toFixed(0)} kB) + ArenaOS.app.js`);

  const inlined = inlineSafe(componentJs);
  scripts.push(
    inlined
      ? `<script>${inlined}\n${MOUNT}</script>`
      : '<script src="./ArenaOS.app.js"></script>'
  );
  if (!inlined) {
    console.log('  note: component contains a parser-significant token, loading it via src=""');
  }

  const html = `<!doctype html>
<!-- GENERATED by tools/make-single-file.mjs. Edit src/ArenaOS.jsx, not this file. -->
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ArenaOS - Standalone Prototype</title>
    <meta name="description" content="Self-contained: React ${REACT_VERSION} and Tailwind vendored from node_modules. No npm, no network." />
    <link rel="stylesheet" href="./ArenaOS.styles.css" />
  </head>
  <body>
    <div id="root"></div>
    <noscript><p style="font:14px system-ui;color:#e2e8f0;padding:24px">This prototype is a React app - enable JavaScript.</p></noscript>
    ${scripts.join('\n    ')}
  </body>
</html>
`;
  writeFileSync(resolve(root, 'dist/ArenaOS.html'), html);
  writeFileSync(resolve(root, 'dist/index.html'), DIST_INDEX);
  console.log(
    `wrote ArenaOS.html (${(html.length / 1024).toFixed(0)} kB, component ${
      inlined ? 'inlined' : 'sidecar'
    }) plus dist/index.html landing page`
  );
}

build().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
