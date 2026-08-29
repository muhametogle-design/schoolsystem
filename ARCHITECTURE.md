# Architecture

## Topology

```text
   Tenant A (Greenfield)      Tenant B (Horizon)          State Government
 ┌────────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
 │ school_manager     │    │ school_manager     │    │ state_inspector     │
 │ teacher            │    │ teacher            │    │ (super-admin, R/O)  │
 └─────────┬──────────┘    └─────────┬──────────┘    └─────────┬───────────┘
           │ JWT + school_id          │                         │ JWT (school_id NULL)
           ▼                          ▼                         ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ FastAPI monolith                                                          │
 │  /api/school/*  tenant ERP   (scoped by user.school_id on EVERY query)    │
 │  /api/school/billing/* 🔒    private financial tier (school_manager only) │
 │  /api/state/*   read-only academics + alarm engine (state_inspector only) │
 │  /ws            live WebSocket bus (red_alarm / exam_published / …)       │
 │                                                                            │
 │  services: Phase-2 worker cron (15:00) · ID generator · publish valve      │
 └───────────────────────────────┬───────────────────────────────────────────┘
                                 ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ PostgreSQL 14+  (shared DB, logical multi-tenancy via school_id)          │
 │  academic tier  — state-readable (RLS: published grades only)             │
 │  financial tier — 🔒 DENY-ALL RLS for state roles, zero grants            │
 │  demo tier      — SQLite engine (same ORM, same API)                      │
 └───────────────────────────────────────────────────────────────────────────┘
```

## Request lifecycle (tenant write)

1. `Authorization: Bearer <JWT>` → `get_current_user` loads the user + role.
2. `require_school(...)` rejects state roles (audited), enforces role matrix.
3. The handler injects `user.school_id` into every filter — a query without a
   tenant predicate is structurally impossible to write through the router.
4. On PostgreSQL a second line of defence scopes rows via RLS session vars.

## The 15:00 Red Alarm pipeline

```text
 scheduler loop (platform tz)
   └─ sleep until 15:00
        └─ process_daily_attendance_deadlines(session)
             ├─ SELECT active private_schools
             ├─ for each school with no submitted roster today:
             │    ├─ UPSERT daily_submission_logs (alarm_triggered = true)
             │    ├─ INSERT communication_logs (Red_Alarm, Pending)
             │    └─ emit_live_websocket_alarm_event() ──► /ws ──► all
             │        state_inspector browsers (banner + toast + map refresh)
             └─ COMMIT
```

The same function backs `POST /api/state/audit/run` so the dashboard can demo
the escalation instantly.

## Exam Data Release Valve

```text
 teacher/school → student_grades (is_published = FALSE)   [private draft]
                         │
        school_manager: POST /api/school/grades/publish
                         │  (single transaction)
                         ├─ UPDATE student_grades SET is_published = TRUE
                         ├─ INSERT exam_submission_events  (IMMUTABLE —
                         │       trigger blocks UPDATE/DELETE on PostgreSQL)
                         └─ ws broadcast exam_published
                         ▼
 View C / state analytics aggregate ONLY is_published = TRUE rows
```

## Technology

* **Backend** — FastAPI, SQLAlchemy 2.0 ORM, PyJWT (HS256), Argon2id hashes.
* **Realtime** — native WebSockets with a broadcast `ConnectionManager`.
* **Database** — PostgreSQL 14+ (authoritative DDL in `sql/`); SQLite demo
  engine so the platform boots with zero infrastructure.
* **Worker** — in-process asyncio cron (no external queue needed); swap in
  Celery/APScheduler by calling the same service function.
* **Frontend** — dependency-free vanilla JS SPA served by the API at `/`.
