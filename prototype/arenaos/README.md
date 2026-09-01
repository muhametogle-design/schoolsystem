# ArenaOS — standalone mock prototype

> **Status: prototype / demo tier only. Not part of the NE-EMIS product.**
> Nothing here talks to the FastAPI backend. There is no auth session, no
> tenant isolation, no audit trail, and no persistence — all data lives in
> `useState` and resets on refresh. The real, API-backed implementations of
> these two screens are [`web/src/pages/Syllabus.jsx`](../../web/src/pages/Syllabus.jsx)
> and [`web/src/pages/TeacherDashboard.jsx`](../../web/src/pages/TeacherDashboard.jsx).

## Why a CSS shim was needed

`ArenaOS.jsx` is stored **verbatim** as authored. It is written against Tailwind
utility classes (`bg-slate-950`, `max-w-6xl`, `text-[11px]`, `bg-red-600/20`)
plus one custom `animate-fadeIn` class. The `web/` workspace has **no Tailwind**
at all — it uses a hand-written design system in `web/src/styles.css` — so the
component would render as an unstyled wall of text inside that app.

This folder is therefore its own Vite project whose only extra dependency is
Tailwind v4 through `@tailwindcss/vite` (zero config, automatic content
scanning). `src/index.css` adds the single `fadeIn` keyframe the component
references. `web/`, the backend, and the CI pipeline are untouched.

## Run it

```bash
cd prototype/arenaos
npm install
npm run dev            # Vite on 0.0.0.0:5173
```

Seeded demo logins (client-side string comparison only):

| Portal   | Credential    | Secret    |
|----------|---------------|-----------|
| Teacher  | `T-402`       | `1234`    |
| Teacher  | `T-409`       | `5678`    |
| Manager  | `admin`       | `admin123`|

`npm run build` produces a self-contained `dist/` you can host anywhere.

## Review notes on the mock

Things a reader should know before this design is promoted to the real app.
The first item is a genuine display bug; the rest are prototype shortcuts.

1. **The "Log Topics" modal does not visibly react to its checkboxes.**
   `activeModalSyllabus` holds a *snapshot copy* of the row, so after
   `handleToggleTopic` updates `syllabusList` the modal still renders the stale
   `unit.covered` values and the boxes snap back. Progress on the card behind
   the modal does move. One-line fix — derive the open row instead of copying it:
   ```jsx
   const activeSyllabus = activeModalSyllabus
     ? syllabusList.find((s) => s.id === activeModalSyllabus.id) ?? null
     : null;
   ```
   then render `activeSyllabus` and keep `setActiveModalSyllabus(id)` as the
   open/close signal.
2. **`animate-fadeIn`** is not a built-in Tailwind utility (shimmed here).
3. **Hardcoded `2026-09-01`** attendance key (twice) — the real pages use
   `new Date().toISOString().slice(0, 10)` and a date picker.
4. **`handleAddSubject` ignores `target` and `deadline` in the UI** — they sit in
   `newSubject` state but have no inputs, so new rows silently inherit 80 /
   `2026-11-15`.
5. **`id: \`SYL-${Date.now().toString().slice(-3)}\`** collides easily (3 digits of
   a rolling timestamp) and duplicates can make React keys non-unique.
6. **New syllabus rows never reach the teacher side** — `assignedSubjects` comes
   from the frozen `INITIAL_TEACHERS`, so a manager-created subject is invisible
   to the teacher portal.
7. **No `Excused` status** — the real roster is Present / Absent / Late /
   Excused (4 taps), and the real backend writes a `SubjectAttendance` row per
   class + subject + period slot.
8. **Attendance is not filtered by `classGrade`** — `INITIAL_STUDENTS` is shown
   for every subject, so Class 8 would list Form 3 students.
9. **Client-side auth only** — no rate limit, no session, PINs in source.
   The real flow is Argon2-hashed Staff ID + PIN over `/api/auth/login` with an
   HttpOnly cookie and `RBAC` guards on every route.
10. **Manager portal is syllabus-only** — the real School Manager keeps the full
    ERP (students, staff, streams, schedules, private billing behind the
    financial firewall).
