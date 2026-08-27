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

function Find-DockerExe {
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

$dockerExe = $null
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $dockerExe = (Get-Command docker).Source
    Write-Host "docker CLI found on PATH: $dockerExe" -ForegroundColor Green
} else {
    $dockerExe = Find-DockerExe
    if ($dockerExe) {
        Write-Host "docker CLI NOT on PATH, but found here: $dockerExe" -ForegroundColor Yellow
        Write-Host "  (run_docker.ps1 will add this folder to PATH automatically.)" -ForegroundColor Yellow
        Write-Host "  Or open a NEW PowerShell after Docker Desktop is fully running." -ForegroundColor Yellow
    }
}

if ($dockerExe) {
    # Add the docker bin to PATH for this session so we can test the daemon.
    $dockerDir = Split-Path $dockerExe
    if ($env:Path -notlike "*$dockerDir*") {
        $env:Path = "$env:Path;$dockerDir"
    }
    try {
        $ver = & $dockerExe version 2>&1
        $out = $ver -join "`n"
        if ($out -match "Server:|Cannot connect|error during connect|is the docker daemon running") {
            Write-Host ($ver | Select-Object -First 3)
            Write-Host "Docker daemon is NOT reachable yet." -ForegroundColor Red
            Write-Host "  -> Launch Docker Desktop from Start Menu and wait for 'Engine running'." -ForegroundColor Red
            Write-Host "  -> Then open a NEW PowerShell and run:  docker --version" -ForegroundColor Red
        } else {
            Write-Host ($ver | Select-Object -First 4)
            Write-Host "Docker daemon is reachable." -ForegroundColor Green
        }
    } catch {
        Write-Host "docker CLI exists but could not query the daemon:" -ForegroundColor Yellow
        Write-Host "  -> Start Docker Desktop and wait for 'Engine running'." -ForegroundColor Yellow
    }
} else {
    Write-Host "docker NOT found anywhere." -ForegroundColor Red
    $desktop = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktop) {
        Write-Host "  Docker Desktop is INSTALLED but its CLI is not on PATH." -ForegroundColor Yellow
        Write-Host "  -> Close this PowerShell and open a NEW one, then:  docker --version" -ForegroundColor Yellow
    } else {
        Write-Host "  -> Docker Desktop does not appear installed at $desktop" -ForegroundColor Red
        Write-Host "  -> Install it from https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
    }
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
