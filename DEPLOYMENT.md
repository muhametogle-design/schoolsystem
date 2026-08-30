# Production Deployment Guide

## 1. Recommended topology

```text
            ┌────────────┐      ┌──────────────────────────┐
 clients ──▶│ TLS proxy  │────▶│ uvicorn (2+ replicas)    │
            │ (Caddy/    │      │  app.main:app            │
            │  nginx)    │      │  behind --proxy-headers  │
            └────────────┘      └───────────┬──────────────┘
                                            │
                              ┌─────────────▼─────────────┐
                              │ PostgreSQL 16 (primary)   │
                              │ + nightly pg_dump backups │
                              └───────────────────────────┘
```

The in-process 15:00 worker runs in every replica but is idempotent
(UPSERT on `UNIQUE(school_id, log_date)` + duplicate alarms are harmless),
so replicas are safe. For strict single-shot semantics, set
`ENABLE_SCHEDULER=false` on all but one replica or externalise the cron:

```bash
# /etc/cron.d/schoolsystem-compliance
0 15 * * 1-5 schoolsystem curl -s -X POST http://api.internal/api/v1/state/audit/run -H "Authorization: Bearer $STATE_ADMIN_WORKER_TOKEN"
```

## 2. Provision with Docker Compose

```bash
cp .env.example .env
# MANDATORY edits for production:
#   DATABASE_URL=postgresql+psycopg2://school:<strong-secret>@db:5432/schoolsystem
#   JWT_SECRET_KEY=$(openssl rand -hex 64)
#   APP_ENV=production
#   CORS_ORIGINS_RAW=https://emis.example.gov
#   AUTO_SEED_DEMO=false
#   PLATFORM_TIMEZONE=Africa/Nairobi
docker compose up -d --build
```

Then create real operator accounts (the seeded demo users are for evaluation
only — disable or rotate them before going live).

## 3. TLS & headers

Terminate TLS at the proxy and forward `X-Forwarded-*` to uvicorn started with
`--proxy-headers --forwarded-allow-ips="<proxy-cidr>"`.

The API already sets `X-Content-Type-Options`, `Referrer-Policy` and
`Permissions-Policy`. Because the dashboards may be embedded in approved
portal frames, no `X-Frame-Options`/`frame-ancestors` restriction is applied
by default — tighten this at the proxy to your frame origin, e.g. with Caddy:

```
header Content-Security-Policy "frame-ancestors https://portal.example.gov"
```

## 4. Database roles and RLS (defence in depth)

Apply `sql/001_schema.sql`, load the seed estate, then apply
`sql/002_security_firewall.sql` and `sql/003_analytics_views.sql` as the database owner. The latter enables
**FORCE ROW LEVEL SECURITY**, so even a normal table owner must honour the API
request context. Never use a PostgreSQL superuser or `BYPASSRLS` role for the
API process.

For least privilege, create a dedicated runtime login that inherits the
provided `school_app` grants, then point `DATABASE_URL` at it:

```sql
CREATE ROLE schoolsystem_runtime LOGIN PASSWORD 'replace-with-a-long-secret';
GRANT school_app TO schoolsystem_runtime;
```

The API derives `app.school_id` and `app.role` from the verified JWT on every
request. Keep reporting-only state analytics on the dedicated
`state_readonly` role — it has **zero grants** on the financial tier, while
financial RLS adds an explicit state-role denial. Never elevate either runtime
or `state_readonly` to superuser/BYPASSRLS.

> The supplied Compose file uses the local `school` owner for convenience;
> FORCE RLS still applies. Create and use the dedicated runtime role for a
> real deployment.

## 5. Backups & recovery

```bash
# nightly logical backup (cron 01:30)
30 1 * * * postgres pg_dump -Fc schoolsystem > /backups/schoolsystem-$(date +\%F).dump
```

Retention: 30 daily + 12 monthly. Test restores quarterly — the compliance
audit trail (`daily_submission_logs`, `exam_submission_events`,
`security_audit_log`) is evidence and must be included in every backup.

## 6. Monitoring checklist

| Signal | Source | Alert when |
|---|---|---|
| Liveness | `GET /api/health` | non-200 or uptime resets repeatedly |
| Red Alarm worker fired | logs at 15:00 platform tz | no run on a school day |
| WebSocket clients | ops metrics | state dashboards disconnect en masse |
| Login throttling (429s) | API logs | sustained bursts → credential-stuffing |
| `security_audit_log` BLOCKED rows | DB | any state-role financial attempt |
| Disk / DB connections | infra | >80% / saturation |

## 7. Secrets rotation

- Rotate `JWT_SECRET_KEY` during a maintenance window (invalidates sessions;
  users simply re-sign-in).
- Rotate the PostgreSQL password with `ALTER ROLE` + `.env` update + rolling
  restart.
- Never commit `.env`; the repo ships `.env.example` only.

## 8. Go-live checklist

- [ ] Demo accounts removed or rotated
- [ ] `AUTO_SEED_DEMO=false`
- [ ] Strong `JWT_SECRET_KEY` (≥ 64 random bytes)
- [ ] TLS enforced at the proxy, HSTS on
- [ ] Frame/CSP policy pinned to your portal origin
- [ ] Nightly `pg_dump` verified restorable
- [ ] `PLATFORM_TIMEZONE` matches the state's school calendar
- [ ] First 15:00 audit observed firing on a school day
- [ ] Firewall pen-test: state token × every `/api/v1/school/finance/*` route → 403 + audit row
