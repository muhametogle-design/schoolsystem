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

function Get-DockerExe {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        return (Get-Command docker).Source
    }
    $candidates = @(
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
        "$env:ProgramFiles\Docker\Docker\resources\docker.exe",
        "$env:LOCALAPPDATA\Docker\Docker\resources\bin\docker.exe",
        "$env:ProgramData\Docker\Docker\resources\bin\docker.exe",
        "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}

$dockerExe = Get-DockerExe
if (-not $dockerExe) {
    throw "Docker Desktop is not installed or its CLI was not found. Install or repair Docker Desktop."
}
# Add Docker Desktop's bin folder to this session's PATH so `docker compose` works.
$dockerDir = Split-Path $dockerExe
if ($env:Path -notlike "*$dockerDir*") {
    $env:Path = "$env:Path;$dockerDir"
}

# Quick engine check so users get a clear message instead of a crypto loop.
try {
    $null = & docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw "docker info failed" }
} catch {
    throw "Docker CLI found but the Docker daemon is not running. Launch Docker Desktop and wait for 'Engine running', then re-run this script."
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
