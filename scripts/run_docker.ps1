<#
.SYNOPSIS
    Build and run the NE-EMIS stack with Docker Compose (PowerShell).

.DESCRIPTION
    1. Builds the API image (layer-cached via requirements.txt)
    2. Starts PostgreSQL and waits for it to be healthy
    3. Runs the one-shot seed service (demo campus, users, grade tiers)
    4. Starts the API on http://localhost:5000

.EXAMPLE
    .\scripts\run_docker.ps1
    .\scripts\run_docker.ps1 -SkipBuild
#>
param(
    [switch]$SkipBuild
)

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not on PATH. Install Docker Desktop and reopen PowerShell."
}

if (-not $SkipBuild) {
    Write-Host "==> Building NE-EMIS image (layer-cached via requirements.txt)" -ForegroundColor Cyan
    docker compose build
}

Write-Host "==> Starting PostgreSQL..." -ForegroundColor Cyan
docker compose up -d db

Write-Host "Waiting for db to become healthy..." -ForegroundColor Cyan
$dbPs = docker compose ps db --format json
Write-Host $dbPs

Write-Host "==> Running seed service (creates demo campus, users, grade tiers)..." -ForegroundColor Cyan
docker compose run --rm seed

Write-Host "==> Starting API..." -ForegroundColor Cyan
docker compose up -d api

docker compose ps

Write-Host ""
Write-Host "Dashboard:  http://localhost:5000" -ForegroundColor Green
Write-Host "API docs:   http://localhost:5000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Demo logins (seeded):"
Write-Host "  demo.clerk   / ChangeMe#2026"
Write-Host "  demo.dean    / ChangeMe#2026"
Write-Host "  state.admin  / ChangeMe#2026"
Write-Host "  aggregator   / ChangeMe#2026"
