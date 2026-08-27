<#
.SYNOPSIS
    Check that the NE-EMIS repo, branch, Docker CLI and current directory are
    all correct before running run_docker.ps1.

.DESCRIPTION
    Prints:
      * current directory
      * whether run_docker.ps1 exists here (i.e. you are in the repo root)
      * the git branch
      * whether docker is on PATH / Docker Desktop is reachable

.EXAMPLE
    .\scripts\check_env.ps1
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "==> Current directory" -ForegroundColor Cyan
Write-Host (Get-Location).Path

$scriptPath = Join-Path (Get-Location) "scripts\run_docker.ps1"
if (Test-Path $scriptPath) {
    Write-Host "OK   run_docker.ps1 found here (you are in the repo root)" -ForegroundColor Green
} else {
    Write-Host "MISS run_docker.ps1 not found here." -ForegroundColor Red
    Write-Host "     You are NOT in the schoolsystem repository folder."
    Write-Host "     cd to the folder that contains scripts\ and re-run."
}

Write-Host ""
Write-Host "==> Git branch" -ForegroundColor Cyan
if (Get-Command git -ErrorAction SilentlyContinue) {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    Write-Host "Branch: $branch"
} else {
    Write-Host "git not found on PATH."
}

Write-Host ""
Write-Host "==> Docker" -ForegroundColor Cyan
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "docker CLI found on PATH: $((Get-Command docker).Source)" -ForegroundColor Green
    try {
        $ver = docker version 2>&1
        Write-Host ($ver | Select-Object -First 4)
    } catch {
        Write-Host "docker CLI exists but daemon may not be reachable. Start Docker Desktop." -ForegroundColor Yellow
    }
} else {
    Write-Host "docker NOT found on PATH." -ForegroundColor Red
    Write-Host "  -> Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and launch it."
    Write-Host "  -> After launch, open a NEW PowerShell and run:  docker --version"
}

Write-Host ""
Write-Host "==> Repo scripts present (expected if you are in the repo root)" -ForegroundColor Cyan
Get-ChildItem .

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1) cd into the folder that contains this repo (look for an .git folder here)."
Write-Host "  2) Ensure branch is 'arena/01a043e9-schoolsystem':  git checkout arena/01a043e9-schoolsystem"
Write-Host "  3) Start Docker Desktop, then in a NEW PowerShell run:"
Write-Host "       .\scripts\run_docker.ps1"
