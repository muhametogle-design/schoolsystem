<#
.SYNOPSIS
  One-command launcher for the School Management Platform on Windows.

.DESCRIPTION
  Creates the Python virtual environment, installs dependencies, builds the
  React interface on first run, optionally reseeds the five-school demo
  estate, then starts the FastAPI server and opens the browser.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\run_windows.ps1
  powershell -ExecutionPolicy Bypass -File .\run_windows.ps1 -Reset   # fresh demo data
  powershell -ExecutionPolicy Bypass -File .\run_windows.ps1 -NoBuild # skip web build
#>

param(
  [switch]$Reset,
  [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "== School Management Platform launcher ==" -ForegroundColor Yellow

# --- 1) Python virtual environment -----------------------------------------
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host ">> Creating Python virtual environment (.venv)..." -ForegroundColor Cyan
  py -3.11 -m venv .venv
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
  }
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  throw "Python 3.11+ is required (winget install Python.Python.3.11)"
}
$py = ".\.venv\Scripts\python.exe"

# --- 2) Backend dependencies ------------------------------------------------
Write-Host ">> Installing backend dependencies..." -ForegroundColor Cyan
& $py -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt

# --- 3) React interface (first run only) ------------------------------------
if (-not $NoBuild -and -not (Test-Path "web\dist\index.html")) {
  Write-Host ">> Building the React interface (first run)..." -ForegroundColor Cyan
  Push-Location web
  if (-not (Test-Path "node_modules")) { npm ci }
  if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm ci failed - is Node.js 18+ installed?" }
  npm run build
  if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm run build failed" }
  Pop-Location
}

# --- 4) Optional demo reseed -------------------------------------------------
if ($Reset) {
  Write-Host ">> Resetting the database to the five-school demo estate..." -ForegroundColor Cyan
  & $py -m scripts.seed_data --reset
}

# --- 5) Launch ----------------------------------------------------------------
Write-Host ""
Write-Host ">> Platform starting on http://127.0.0.1:8000  (Ctrl+C to stop)" -ForegroundColor Green
Write-Host ">> School portal login : manager@nugaal.edu.so / School@2026"   -ForegroundColor Green
Write-Host ">> State Admin (backups): stateadmin@education.gov / StateAdmin@2026" -ForegroundColor Green
Write-Host ""

# Open the browser once the server has had a moment to boot.
Start-Job -ScriptBlock { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000" } | Out-Null

& $py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
