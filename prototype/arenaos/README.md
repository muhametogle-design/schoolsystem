# ArenaOS — standalone mock prototype

> **Prototype / demo tier. Not part of the NE-EMIS product.**
> Nothing here talks to the FastAPI backend: no session, no tenant isolation, no
> audit trail, no persistence. All data lives in `useState` and resets on refresh.
> The API-backed implementations of these screens are
> [`web/src/pages/Syllabus.jsx`](../../web/src/pages/Syllabus.jsx) and
> [`web/src/pages/TeacherDashboard.jsx`](../../web/src/pages/TeacherDashboard.jsx),
> guarded by `tests/test_syllabus_tracker.py` and `tests/test_teacher_portal_rbac.py`.

## Layout

| File | Purpose |
|---|---|
| `src/ArenaOS.jsx` | the screens (manager syllabus board + teacher attendance portal), with the fixes below applied and each one tagged `[prototype-fix N]` |
| `src/index.css` | Tailwind v4 entry + the one shim the markup needs |
| `src/ArenaOS.test.jsx` | behavioural tests for the fixes (jsdom render of the real component) |
| `vite.config.js` | dev server on `0.0.0.0:5173`, `allowedHosts: true`, deliberately **no** `/api` proxy |

## Why this folder exists instead of `web/`

The component is written against Tailwind utilities (`bg-slate-950`, `max-w-6xl`,
`text-[11px]`, `bg-red-600/20`) plus one custom `animate-fadeIn` class. The `web/`
workspace has **no Tailwind** — it uses a hand-written design system in
`web/src/styles.css` — so the component would render as an unstyled wall of text
inside the real app. This folder is its own Vite project whose only extra
dependency is Tailwind v4 via `@tailwindcss/vite` (zero config, automatic content
scanning); `src/index.css` adds the single `fadeIn` keyframe. `web/`, the backend,
and CI are untouched, and `.dockerignore` keeps `prototype/` out of images.

## Run it

```bash
cd prototype/arenaos
npm install
npm run dev     # http://localhost:5173
npm test        # vitest, 10 behavioural checks
npm run build   # self-contained dist/
```

Mock logins (client-side string comparison only):

| Portal  | Credential | Secret     |
|---------|------------|------------|
| Teacher | `T-402`    | `1234`     |
| Teacher | `T-409`    | `5678`     |
| Manager | `admin`    | `admin123` |

## Fixes applied to the pasted mock

The design itself is unchanged — same structure, same class strings, same colour
language. Only behaviour that was broken or self-contradictory was repaired.

1. **Log Topics modal rendered a stale snapshot.** `setActiveModalSyllabus(item)`
   stored a *copy* of the row, so every unit toggle re-rendered the card behind the
   modal while the checklist kept rendering the frozen copy and the boxes snapped
   back. State now holds the **id** and the modal derives the live row
   (`activeSyllabus`). Covered by test *"re-renders live unit state after each toggle"*.
2. **`animate-fadeIn`** is not a built-in Tailwind utility — shimmed in `index.css`.
3. **`SESSION_DATE`** replaces the literal `'2026-09-01'` that was duplicated in the
   writer and the reader; the register key is derived once, like the real pages.
4. **Add-subject form now exposes `target` and `deadline`.** Both already sat in
   `newSubject` state with no inputs, so every created row silently inherited
   80 / `2026-11-15`.
5. **Unique plan ids.** `SYL-${Date.now().toString().slice(-3)}` reused ids freely
   (three rolling digits), producing duplicate React keys and mis-targeted modals;
   ids are now derived from the live list.
6. **Roster scoped to the subject's class, four statuses.** All three Form 3
   students were listed under the Class 8 subject, and only Present/Absent/Late
   existed. Now `roster = students.filter(classGrade)` with Present/Absent/Late/
   **Excused**, matching the product's 4-tap register.
7. **Manager username is trimmed and case-insensitive**, mirroring what the staff-ID
   branch already did.
8. **Units can be added, and manager-created subjects reach the teacher portal.**
   A plan used to be born with one hard-coded "Chapter 1: Foundations" and no way
   to grow; new subjects also never appeared for the assigned teacher, so manager
   "CRUD" only ever moved the manager's own board. Both are now wired (`＋ Add Unit`,
   derived `teacherSubjects`).
9. **Labels are paired with their inputs** (`htmlFor`/`id`), which also normalises the
   one label that had lost Tailwind's `block` class. Unlabelled controls are invisible
   to assistive tech and to `getByLabelText`.
10. **Logout resets the role tab and closes the CRUD form.** Previously a manager who
    signed out and then tried a teacher account stayed on the *Manager* tab and was
    told "Invalid Manager Credentials" for valid staff IDs.

## Still mock by design (do not promote as-is)

- **Auth is client-side only** — no hashing, no rate limit, no session cookie. The
  product uses Argon2-hashed Staff ID + PIN over `/api/auth/login` with an HttpOnly
  cookie, `login_rate_limit` throttling, and role guards on every route.
- **No audit trail.** `log_topics_covered` in `app/services/syllabus.py` writes a
  checkpoint per toggle; here a checkbox just flips a boolean.
- **No server-side slot ownership.** The real endpoint refuses to open a register for
  a class/subject/period the teacher does not own; this mock simply filters a list.
- **Manager portal is syllabus-only**; the real School Manager keeps the full ERP
  (students, staff, streams, schedules, and private billing behind the financial
  firewall), and State Admin/Inspector roles do not exist here at all.
- **Benchmarks are cosmetic.** No midterm/final gates, no `On Track` / `Ahead` /
  `Behind Schedule` computation from `expected_pct`, no deadline red-alarm.
