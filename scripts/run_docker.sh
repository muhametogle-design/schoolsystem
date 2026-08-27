#!/usr/bin/env bash
# Bring the full NE-EMIS stack up with Docker Compose.
#
#   ./scripts/run_docker.sh
#
# 1. Starts PostgreSQL (auto-applies sql/001_schema.sql + sql/002_indexes.sql)
# 2. Builds and runs the seed job (demo campus, users, civil-service grades)
# 3. Starts the API + dashboard container on http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose build
docker compose up -d db
echo "Waiting for PostgreSQL to become healthy..."
docker compose ps db
echo "Running the seed service..."
docker compose up seed
echo "Starting the API..."
docker compose up -d api
docker compose ps

echo
echo "Dashboard:  http://localhost:8000"
echo "API docs:   http://localhost:8000/docs"
echo
echo "Demo logins (seeded):"
echo "  demo.clerk / ChangeMe#2026"
echo "  demo.dean  / ChangeMe#2026"
echo "  state.admin / ChangeMe#2026"
echo "  aggregator  / ChangeMe#2026"
