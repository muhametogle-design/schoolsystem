# ArenaOS prototype on Termux — online npm route

Everything here runs **on the phone**; `http://127.0.0.1:PORT` in Android Chrome is
the phone's own loopback, so nothing has to reach a desktop or a sandbox.

## Bootstrap

```bash
pkg update -y
pkg install -y git nodejs-lts python
```

clang/make/pkg-config are only needed for the Python route at the bottom (argon2's
native build), not for the prototype.

## Get the code

```bash
git clone https://github.com/muhametogle-design/schoolsystem.git
cd schoolsystem
git fetch origin arena/01a05d78-schoolsystem
git checkout arena/01a05d78-schoolsystem
```

Or unzip `schoolsystem-arenaos-termux.zip` from the repo root — it carries a built
`dist/`, which a plain clone does not (`.gitignore` keeps `dist/` out of git).

## 1. The normal npm workflow

```bash
cd prototype/arenaos
npm ci            # or: npm install --no-audit --no-fund
npm run dev -- --host 0.0.0.0 --port 5173
```

Open **http://127.0.0.1:5173** in Chrome on the phone. HMR is live — edit
`src/ArenaOS.jsx` and the phone reloads.

`npm ci` is preferred when a `package-lock.json` is present: it installs exactly
the locked versions (react 18.3.1, vite 5.4.21, @tailwindcss/vite 4.3.3, esbuild)
instead of re-resolving. `dist/` is a build artefact, so a fresh clone needs
`npm run build` before anything can be served from it.

Other commands:

| Command | What it does |
|---|---|
| `npm test` | 14 checks: 10 source-level + 4 that boot the built `dist/` bundle |
| `npm run build` | Vite output, then the no-install `dist/ArenaOS.html` |
| `npm run verify` | build + tests in one go |
| `npm run serve:dist` | `python serve.py 8090` over `dist/`, no-cache headers |

## 2. Serve the build (what CI produces)

```bash
npm run build
cd dist && python -m http.server 8090
```

Open **http://127.0.0.1:8090** → a landing page with three entries. The
self-contained `ArenaOS.html` is the one that needs nothing else; it still loads
`ArenaOS.vendor.react.js` / `.react-dom.js` from the same folder, so copy `dist/`
as a folder, never the HTML file alone.

To reach it from another device on the same Wi-Fi, use the phone's LAN address:
`ifconfig wlan0` → `http://<that-ip>:8090`.

## 3. Published online (GitHub Pages)

`prototype/arenaos/ci/pages.yml` builds the prototype with `npm ci` and deploys
`dist/` to Pages. It is **ready but not installed** — this workspace's GitHub App
may not write `.github/workflows/*` (see `ci/README.md`). As a repo admin:

```bash
cp prototype/arenaos/ci/pages.yml .github/workflows/pages.yml
git add .github/workflows && git commit -m "ci: publish the prototype to Pages"
```

**Then one manual step, in the repo UI** (the Actions token is refused for it):
Settings → Pages → Source: **GitHub Actions**. Then:

```bash
gh workflow run pages.yml --repo muhametogle-design/schoolsystem --ref arena/01a05d78-schoolsystem
```

URL: `https://muhametogle-design.github.io/schoolsystem/prototype/`

That works on a phone browser from anywhere — no Termux, no server on the device.
Until Pages is switched on, the workflow's *deploy* step fails with "Pages is not
enabled"; the *build* step still proves the npm path works.

Until that workflow file is installed, the quickest online route from the phone is
`npx serve`-free and manual: `npm run build` then `cd dist && python -m http.server
8090`.

Prefer another host? Netlify CLI works straight from Termux and needs no repo admin:

```bash
cd prototype/arenaos && npm run build
npx netlify-cli deploy --prod --dir dist      # prints the live URL
```

Netlify's build command does the same remotely if you connect the repo instead.

## 4. Offline fallback

`node tools/make-single-file.mjs` compiles the JSX with esbuild, copies React UMD
byte-for-byte out of `node_modules` and reuses the stylesheet from the Vite build,
producing `dist/ArenaOS.html`: no CDN, no Babel in the browser, works in airplane
mode. Needs one `npm ci && npm run build` first.

No file transfer at all? `dist/ArenaOS.cdn.html` (2.3 kB) and `dist/ArenaOS.app.js`
(28 kB) are both plain text: paste them into two files in one folder and serve it —
React/Tailwind come from unpkg with a jsdelivr fallback, so it needs network.

Regenerate with `node tools/make-single-file.mjs --cdn`.

## 5. The full app (FastAPI + real NE-EMIS SPA)

```bash
cd ~/schoolsystem
python -m venv .venv
.venv/bin/pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings PyJWT email-validator
.venv/bin/pip install argon2-cffi argon2-cffi-bindings cffi pycparser cryptography
cd web && npm ci && npm run build && cd ..
termux-wake-lock
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://127.0.0.1:8000** → `manager@nugaal.edu.so` / `School@2026`, or a
teacher with Staff ID `NE-TID-…` and PIN `2026`. API docs: `http://127.0.0.1:8000/docs`.

`argon2-cffi-bindings` → `cffi` → `pycparser` compile against Android's libc, so
`pkg install clang make pkg-config` first. Termux drops background processes unless
`termux-wake-lock` is held.

## Handy checks

```bash
ss -ltn | grep -E '5173|8000|8090'     # is something listening?
tail -f /tmp/arena.log                  # if you backgrounded the server
npm test                                # re-run the 14 checks only
```
