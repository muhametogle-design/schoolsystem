# Running this on Termux (Android)

Everything below runs **on the phone** — `http://127.0.0.1:PORT` in Android Chrome
is the phone's own loopback, so nothing has to reach a desktop or a sandbox.

## 0. Packages

```bash
pkg update -y
pkg install -y git nodejs-lts python clang make pkg-config
termux-setup-storage          # only needed if you want files in shared storage
```

## 1. Get the code

**If you have the repo:**

```bash
git clone https://github.com/muhametogle-design/schoolsystem.git
cd schoolsystem
git fetch origin arena/01a05d78-schoolsystem
git checkout arena/01a05d78-schoolsystem
```

**If you only have the zip** (`schoolsystem-arena.zip` from this session):

```bash
unzip schoolsystem-arena.zip -d ~/schoolsystem && cd ~/schoolsystem
```

**If you pasted the files by hand:** create
`~/schoolsystem/prototype/arenaos/` and drop in `src/ArenaOS.jsx`, `src/main.jsx`,
`src/index.css`, `index.html`, `vite.config.js`, `package.json`. Only
`src/ArenaOS.jsx` matters for the no-install path in step 2.

## 2. No-install path — single file, zero npm

`prototype/arenaos/dist/` after a build contains `ArenaOS.html` — the component
compiled by esbuild, with React/ReactDOM vendored from node_modules and the
Tailwind stylesheet generated locally. No npm, **no network**, no Babel in the
browser. Serve that folder with nothing but Python:

```bash
cd ~/schoolsystem/prototype/arenaos/dist
python -m http.server 8090
# then open http://127.0.0.1:8090/ArenaOS.html
```

`../serve.py` is the same thing with no-cache headers and a `Ctrl-C`-clean exit:

```bash
cd ~/schoolsystem/prototype/arenaos
python ../arenaos/serve.py 8090     # or: ARENA_DIR=dist python serve.py 8090
```

Termux: swipe the notification → *Kill server* afterwards, or `Ctrl-C` in that
terminal. Want it in the background?

```bash
nohup python -m http.server 8090 > /tmp/arena.log 2>&1 &
```

The dist/ folder is a build artefact (`.gitignore` keeps `dist/` out of git), so a
fresh clone does not have it. Either build it once — `npm run build` — and copy the
folder over, or go straight to step 3. `schoolsystem-arenaos-termux.zip` in the
repo root already contains it.

**No files to copy at all?** `dist/ArenaOS.cdn.html` (2.3 kB) plus
`dist/ArenaOS.app.js` (28 kB) are both plain text: paste them into two files in one
folder, then serve that folder as above and open `ArenaOS.cdn.html`. It pulls React
and Tailwind from unpkg (falling back to jsdelivr), so it needs network — the only
path that works with nothing but a text editor. Regenerate with
`node tools/make-single-file.mjs --cdn`. The `ArenaOS.html` self-contained page
cannot be hand-pasted: it depends on the two vendored React files from
node_modules.

## 3. Real workflow — Vite dev server with HMR

```bash
cd ~/schoolsystem/prototype/arenaos
npm install
npm run dev -- --host 0.0.0.0 --port 5173
# open http://127.0.0.1:5173
```

`--host 0.0.0.0` also lets another device on the same Wi-Fi in through the phone's
LAN IP (`ifconfig wlan0`), but 127.0.0.1 is all you need on-device.

If `npm install` dies in a native build, the culprits here are esbuild/rollup
(prebuilt binaries — usually fine) and nothing else; re-run with:

```bash
npm install --no-audit --no-fund
```

Other commands in that folder:

| Command | What it does |
|---|---|
| `npm test` | the 14 behavioural + artefact checks (vitest + jsdom) |
| `npm run build` | Vite output **plus** `dist/ArenaOS.html` (self-contained) |
| `npm run verify` | build, then all 14 checks incl. the dist/ artefact guards |
| `npm run serve:dist` | hosts `dist/` on 8090 with `serve.py` — no npm at serve time |

## 4. The full app (backend + real React SPA) on the phone

From the repo root:

```bash
cd ~/schoolsystem
python -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings PyJWT email-validator
.venv/bin/pip install argon2-cffi argon2-cffi-bindings cffi pycparser cryptography
```

`argon2-cffi-bindings` → `cffi` → `pycparser` compile against Android's libc, so
clang/make/pkg-config from step 1 must be installed first. If `cryptography` also
fails, the backups module still imports, but the app needs it — install the wheel
or run `PINKY=1 pip install` variants at your discretion.

```bash
# SQLite demo tier auto-seeds on first boot (data/ is gitignored)
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For the React dashboard at `/`, build the SPA once first:

```bash
cd web && npm install && npm run build && cd ..
```

Open `http://127.0.0.1:8000` → sign in as `manager@nugaal.edu.so` /
`School@2026`, or a teacher with Staff ID `NE-TID-…` and PIN `2026`.
API docs live at `http://127.0.0.1:8000/docs`.

Battery: Termux processes die when the app is backgrounded unless you run
`termux-wake-lock` first.

## 5. Handy one-liners

```bash
# is something listening?
ss -ltn | grep -E '5173|8000|8090'
# tail the dev server log if you backgrounded it
tail -f /tmp/arena.log
# re-run only the prototype tests
cd ~/schoolsystem/prototype/arenaos && npx vitest run
```
