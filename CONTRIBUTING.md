# Contributing to SchoolSystem

Thank you for improving the platform. This document covers setup, workflow and
the quality bar for changes.

## Development setup

```bash
git clone <your-fork>
cd schoolsystem
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # adjust as needed
make dev                       # http://localhost:8000 (SQLite demo tier)
```

The SQLite demo tier exists so contributors need zero infrastructure. Any
change must work on **both** the demo tier and PostgreSQL — keep SQL
dialect-portable or gate PostgreSQL-only features behind `IS_SQLITE`.

## Daily commands

| Command | Purpose |
|---|---|
| `make dev` | Run the API + dashboards locally |
| `make test` | Full pytest suite |
| `make seed` | Reseed demo data |
| `make docker` | Full PostgreSQL 16 stack |
| `make psql` | psql shell into the compose database |
| `scripts\windows\Run-SchoolSystem.ps1` | Windows: install, build, and run |
| `scripts\windows\Invoke-Tests.ps1` | Windows: pytest + React build |

## Quality bar

1. **Tests are mandatory.** Every behaviour change ships with a test.
   Security-boundary changes (firewall, release valve, RBAC) must extend
   `tests/test_firewall.py` / `tests/test_release_valve.py` with a failing
   attempt proof.
2. **SQL changes must parse.** Validate any `sql/*.sql` edit against the real
   PostgreSQL grammar before committing:
   ```bash
   pip install pglast
   python -c "import pglast; pglast.parse_sql(open('sql/001_schema.sql').read())"
   ```
3. **Never weaken the financial firewall.** No state-facing route, serializer,
   service import or SQL grant may express `tuition_rates`,
   `student_invoices` or `payment_transactions`.
4. **Frontend stays dependency-free.** `frontend/` is vanilla JS/CSS by
   design — do not add frameworks or CDNs without prior discussion.
5. **Migrations** — DDL changes are applied by editing the numbered
   `sql/NNN_*.sql` scripts (and mirrored in `app/models/`). Never edit an
   already-released script destructively; add a new numbered file.

## Commit & PR conventions

- Commits: imperative subject ≤ 72 chars, body explains *why*.
- Branch from `main`, open a PR describing the change, the tests added and a
  demo script the reviewer can run.
- CI must pass: pytest suite + PostgreSQL DDL grammar validation + Docker
  image build (workflow definition ships at `ci/github-actions.yml` — copy it
  to `.github/workflows/ci.yml` to activate; commit rights for workflow files
  are restricted).

## Reporting security issues

Do **not** open public issues for security vulnerabilities — contact the
maintainers privately. Include reproduction steps; firewall bypasses are
treated as critical.
