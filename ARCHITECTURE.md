# Architecture

## Topology

```text
 School tenants (IL / MY / NG / AQ / LB)              State education roles
 ┌─────────────────────────────────────┐          ┌──────────────────────────┐
 │ School Manager · Teacher             │          │ State Admin · Inspector  │
 │ one signed-in school_id each         │          │ school_id is NULL        │
 └──────────────────┬──────────────────┘          └────────────┬─────────────┘
                    │ JWT bearer or HttpOnly cookie             │
                    └──────────────────┬────────────────────────┘
                                       ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ FastAPI application                                                       │
 │ /api/v1/school/*          tenant academic workspace                      │
 │ /api/v1/school/finance/*  manager-only private finance                    │
 │ /api/v1/state/*           academic oversight + State Admin provisioning  │
 │ /ws                        authenticated live event bus                    │
 │ React build                primary interface served at /                  │
 │ frontend/                  legacy fallback at /admin/*                    │
 └──────────────────────────────────┬───────────────────────────────────────┘
                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ PostgreSQL 16                                                            │
 │ FORCE RLS tenant academic tables · published-grade release valve          │
 │ financial RLS denial for State roles · state_readonly column grants        │
 │ SQLite uses the identical ORM/API for local zero-infrastructure runs      │
 └──────────────────────────────────────────────────────────────────────────┘
```

## Request lifecycle

1. A bearer token or same-origin HttpOnly cookie reaches `get_current_user`.
2. The signed claims are validated against the active database account, so a
   disabled account or changed role/tenant invalidates an old session.
3. The request gets a `school_id` / role context for PostgreSQL RLS; pooled
   connections reset to a deny-by-default context first.
4. `require_state`, `require_state_admin`, or `require_school` enforces the
   role boundary before the endpoint executes.
5. Tenant handlers additionally filter every model query by `user.school_id`.
   State serializers are academic-only and exclude all billing values.

## Tenant lifecycle

A State Admin creates a school through `POST /api/v1/state/schools`. The
provisioning service allocates a unique two-letter code, creates the manager,
Class 1–12 streams, all 120 core catalog entries, eight editable faculty
profiles, explicit class/subject/teacher assignments, a roll allocator, and a
private manager billing scaffold. The State response contains only public and
academic provisioning information.

Student registration locks the school’s `school_roll_sequences` row, allocates
an immutable `XX-sequence` roll, and advances the counter inside the same
transaction. State Admins can inspect/advance sequence state but cannot move it
backward.

## Live academic structure

Staff, class, subject, assignment, school-profile, and State-provisioning
mutations broadcast `academic_structure_changed` through the WebSocket manager.
The State dashboard, directory, and institution drill-down subscribe and
refresh only the affected authorized school data. Browser sessions without
localStorage use the same-origin HttpOnly cookie for both REST restoration and
WebSocket authorization.

## Compliance and exam publication

```text
School staff record attendance → school submits daily roster by 12:00
                              → scheduler audits at 15:00
                              → daily submission log + Red Alarm notification
                              → State dashboard event / refresh

Teacher or Manager records grades (draft)
  → Manager publishes an exam scope
  → grade rows become published + immutable exam_submission_event is appended
  → State analytics can read only the released academic data
```

## Technologies

- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic, PyJWT, Argon2id
- **Frontend:** React 18, Redux Toolkit, React Router, Vite
- **Realtime:** native FastAPI WebSockets
- **Database:** PostgreSQL 16 in hardened deployments; SQLite for local runs
- **Deployment:** multi-stage Docker build compiles the React app into the
  FastAPI runtime image
