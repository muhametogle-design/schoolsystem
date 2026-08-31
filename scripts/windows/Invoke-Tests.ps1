<#
.SYNOPSIS
    Run the SchoolSystem pytest suite and React production build from PowerShell.
#>
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_Common.ps1')

$Root = Get-RepoRoot
Set-Location $Root

$venvPython = Ensure-VirtualEnv -RepoRoot $Root
Install-PythonDependencies -VenvPython $venvPython -RepoRoot $Root

Write-Host "Running pytest ..."
Invoke-Native -FilePath $venvPython -ArgumentList @('-m', 'pytest', '-q') -WorkingDirectory $Root

Build-ReactWorkspace -RepoRoot $Root

Assert-Command -Name 'node' -InstallHint 'Install Node.js LTS from https://nodejs.org/' | Out-Null
Write-Host "Checking frontend\app.js ..."
Invoke-Native -FilePath 'node' -ArgumentList @('--check', '.\frontend\app.js') -WorkingDirectory $Root

Write-Host ""
Write-Host "All PowerShell quality checks passed."
