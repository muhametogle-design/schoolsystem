<#
.SYNOPSIS
    Install dependencies, build the React portal, and run SchoolSystem on Windows.

.PARAMETER SkipBuild
    Skip npm ci / npm run build when web\dist already exists.

.PARAMETER Port
    API and portal port. Default 8000.
#>
#Requires -Version 5.1
param(
    [switch]$SkipBuild,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_Common.ps1')

$Root = Get-RepoRoot
Set-Location $Root

Write-Host "SchoolSystem — Windows PowerShell launcher"
Write-Host "Repository: $Root"
Write-Host ""

$venvPython = Ensure-VirtualEnv -RepoRoot $Root
Install-PythonDependencies -VenvPython $venvPython -RepoRoot $Root

$dist = Join-Path $Root 'web\dist\index.html'
if ($SkipBuild -and (Test-Path $dist)) {
    Write-Host "Skipping React build (web\dist already present)."
}
else {
    Build-ReactWorkspace -RepoRoot $Root
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root 'data') | Out-Null

if (-not (Test-Path (Join-Path $Root '.env')) -and (Test-Path (Join-Path $Root '.env.example'))) {
    Copy-Item (Join-Path $Root '.env.example') (Join-Path $Root '.env')
    Write-Host "Created .env from .env.example (edit secrets before production use)."
}

$url = "http://127.0.0.1:$Port"
Write-Host ""
Write-Host "Starting SchoolSystem at $url"
Write-Host "Demo accounts:"
Write-Host "  State Admin             stateadmin@education.gov   StateAdmin@2026"
Write-Host "  Inspector               inspector@education.gov    State@2026"
Write-Host "  Nugaal School Manager   manager@nugaal.edu.so      School@2026"
Write-Host "  Nugaal Teacher          teacher@nugaal.edu.so      Teach@2026"
Write-Host ""
Write-Host "Press Ctrl+C to stop."
Write-Host ""

try {
    Start-Process $url
}
catch {
    Write-Host "Open $url in your browser if it did not launch automatically."
}

$env:AUTO_SEED_DEMO = 'true'
Invoke-Native -FilePath $venvPython -ArgumentList @(
    '-m', 'uvicorn', 'app.main:app',
    '--host', '0.0.0.0',
    '--port', "$Port"
) -WorkingDirectory $Root
