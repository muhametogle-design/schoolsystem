# Run your School System on a Termux phone — real-time localhost

This guide puts the **complete platform** — FastAPI backend, SQLite database
and the built React app — on *your phone*, served by **one process** at
`http://127.0.0.1:8000`. No laptop, no sandbox, no demo schools: the
`bootstrap_real` step registers **your own school** with your own logins.

How it works: `app/main.py` serves the prebuilt interface in `web/dist/`
from the same port as the API, so once the API runs you have the whole
system. `127.0.0.1` in Android Chrome *is the phone itself*.

Storage needed: roughly 1.5 GB free (toolchains + Python env + app).

---

## A. One-time phone setup

```bash
pkg update -y && pkg upgrade -y
pkg install -y git python nodejs-lts clang make pkg-config libffi rust
pkg install -y python-cryptography
```

- `nodejs-lts` is only needed for **Option B** (building the interface yourself).
- `rust`/`clang`/`make` let pip compile `pydantic-core` and `argon2` **once**
  (the first install can take 10–30 minutes on a phone; later installs reuse
  the compiled wheels). The Termux-packaged `python-cryptography` skips one
  of those builds when visible to the venv below.
- There is **no `python-pydantic` Termux package** — pip builds pydantic-core
  with the rust toolchain above. This is the slowest step; run
  `termux-wake-lock` and keep the phone charging.
- apt aborts an entire `pkg install` line when one package name is unknown,
  so retry remaining packages on their own line if that ever happens.

## B. Get the code — pick ONE option

### Option B1 — Termux zip with the interface prebuilt (recommended, no Node)

```bash
cd ~
curl -LO https://github.com/muhametogle-design/schoolsystem/raw/arena/01a05e29-schoolsystem/schoolsystem-termux-realtime.zip
unzip -q schoolsystem-termux-realtime.zip -d schoolsystem
cd schoolsystem
```

The zip already contains `web/dist/` (the compiled app), so **you never run npm**.

### Option B2 — Git clone (build the interface yourself)

```bash
cd ~
git clone https://github.com/muhametogle-design/schoolsystem.git
cd schoolsystem
git checkout arena/01a05e29-schoolsystem
cd web && npm ci && npm run build && cd ..
```

`npm run build` writes `web/dist/` — the API serves whatever it finds there.

## C. Python environment (once)

```bash
python -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install fastapi uvicorn sqlalchemy "pydantic[email]" pydantic-settings PyJWT email-validator argon2-cffi cryptography
```

Notes
- Plain `uvicorn` is deliberate: `uvicorn[standard]` pulls `uvloop` and
  `watchfiles`, which need extra native toolchains on Android. The
  application runs identically on the plain install.
- Do **not** `pip install -r requirements.txt` on the phone: it pins
  `psycopg2-binary` (PostgreSQL driver), which cannot build on Termux and is
  not needed — the SQLite URL below needs no driver.

## D. Configure REAL mode — no demo schools

```bash
.venv/bin/python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))" > .env
cat >> .env << 'EOF'
DATABASE_URL=sqlite:///./data/schoolsystem.db
AUTO_SEED_DEMO=false
PLATFORM_TIMEZONE=Africa/Mogadishu
EOF
```

`AUTO_SEED_DEMO=false` is the switch that keeps all sample schools out. Your
data lives in `data/schoolsystem.db` on the phone.

## E. Register YOUR school (once)

Replace the values with your school's, then run:

```bash
.venv/bin/python -m scripts.bootstrap_real \
  --admin-email admin@myschool.so --admin-password 'PickAStrongPass1' \
  --school-name "MY SCHOOL NAME" --license "MOE-2026-001" \
  --manager-email me@myschool.so --manager-password 'PickAnother1' \
  --manager-first "YourFirstName" --manager-last "YourLastName" \
  --streams "A"
```

You get, with **zero demo records**:
- a **state admin** login (`--admin-email`) for the oversight portal;
- **your school**: Class 1–12, 120 subjects, roll-number allocator, termly
  tuition rates, and a complete staff mapping for every class-subject pair;
- a **school manager** login (`--manager-email`) — this is your daily account;
- 8 *template faculty* profiles so every subject is mapped: rename them and
  set passwords/PINs from the **Teachers** page (or add your own staff).

## F. Run it — real-time

```bash
termux-wake-lock
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then in Chrome on the phone: **http://127.0.0.1:8000**

- Sign in as the **manager** → the full ERP from this workspace: syllabus
  tracker, teacher portal + PIN logins, restricted attendance marking,
  back-button bar, media engine, design drawer (🎨), and the Publishing
  Control Bar (Save Progress / Test Mobile View / Push Live).
- API docs: `http://127.0.0.1:8000/docs`
- Share with other devices on the same Wi-Fi: find the phone's address with
  `ip addr show wlan0 | grep 'inet '` and browse `http://<that-ip>:8000`.
- `termux-wake-lock` stops Android from killing the server while the screen
  is off (release afterwards with `termux-wake-unlock`).

## G. Daily life

| Task | Command / path |
|---|---|
| Stop the server | `Ctrl+C` in Termux |
| Start it again | step **F** only (everything persists in `data/`) |
| Enroll real students | Students page → *Add student* (roll numbers auto-issue) |
| Give teachers logins | Teachers page → edit a profile → set password / Staff-ID PIN |
| Update the code | `git pull` (Option B2) then `cd web && npm ci && npm run build`, or re-download the zip (B1); restart the server |
| Wipe & start over | Stop the server, `rm -rf data`, repeat steps **E** and **F** |
| Backup files | `data/backups/` (encrypted nightly export at 00:00) |
| See the demo instead | set `AUTO_SEED_DEMO=true` in `.env`, `rm -rf data`, restart — five sample schools appear (`manager@alqalam.edu.so` / `School@2026`) |

## Quick checks

```bash
ss -ltn | grep 8000                    # is the server listening?
tail -f data/*.log 2>/dev/null         # (if you redirected logs)
.venv/bin/python -m pytest -q          # run the 101-test suite on the phone
```

## Troubleshooting

- **`pip install` fails building pydantic-core / argon2 / cffi** → make sure
  step A completed (`clang make pkg-config libffi rust`), then retry. Nothing
  else in the app compiles native code on this path.
- **Chrome shows "can't reach this site"** → confirm `ss -ltn | grep 8000`
  shows the listener and that you browsed to `http://` not `https://`.
- **Page loads but sign-in fails** → you skipped step **E** (there are no
  accounts in real mode until you register your school).
- **Port already in use** → an old server is still running: `pkill -f uvicorn`.
