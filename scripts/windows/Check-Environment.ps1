#Requires -Version 5.1
# Verify that a Windows machine can run SchoolSystem from PowerShell.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_Common.ps1')

$Root = Get-RepoRoot
Set-Location $Root

Write-Host 'SchoolSystem environment check'
Write-Host "Repository: $Root"
Write-Host ''

$failed = $false
function Show-Check {
    param($Label, $Ok, $Detail)
    $mark = if ($Ok) { 'OK' } else { 'MISSING' }
    if (-not $Ok) { $script:failed = $true }
    Write-Host ('[{0,-7}] {1}: {2}' -f $mark, $Label, $Detail)
}

try {
    $launcher = Get-PythonLauncher
    $versionArgs = @()
    $versionArgs += $launcher.PrefixArgs
    $versionArgs += '--version'
    $pyVersion = & $launcher.File @versionArgs 2>&1 | Out-String
    Show-Check 'Python 3' $true ($pyVersion.Trim() + ' (' + $launcher.File + ')')
}
catch {
    Show-Check 'Python 3' $false $_.Exception.Message
}

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Show-Check 'Node.js' $true ((& node --version) + ' (' + $node.Source + ')')
}
else {
    Show-Check 'Node.js' $false 'Install Node.js LTS from https://nodejs.org/'
}

$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    Show-Check 'npm' $true ((& npm --version) + ' (' + $npm.Source + ')')
}
else {
    Show-Check 'npm' $false 'npm is installed with Node.js LTS.'
}

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    Show-Check 'Git' $true ((& git --version) + ' (' + $git.Source + ')')
}
else {
    Show-Check 'Git' $false 'Install Git for Windows from https://git-scm.com/download/win'
}

$docker = Get-DockerExe
if ($docker) {
    try {
        $info = & $docker info --format '{{.ServerVersion}}' 2>$null
        if ($LASTEXITCODE -eq 0 -and $info) {
            Show-Check 'Docker' $true ('engine ' + $info + ' (' + $docker + ')')
        }
        else {
            Show-Check 'Docker' $true ('CLI found at ' + $docker + ' (engine not running - optional for SQLite demo)')
        }
    }
    catch {
        Show-Check 'Docker' $true ('CLI found at ' + $docker + ' (engine not running - optional for SQLite demo)')
    }
}
else {
    Write-Host '[SKIP   ] Docker: not required for the SQLite demo. Install Docker Desktop to run PostgreSQL.'
}

Write-Host ''
if ($failed) {
    Write-Host 'Fix the MISSING items, then re-run:'
    Write-Host '  .\scripts\windows\Check-Environment.cmd'
    exit 1
}

Write-Host 'Environment looks ready. Next:'
Write-Host '  .\scripts\windows\Run-SchoolSystem.cmd'
exit 0
