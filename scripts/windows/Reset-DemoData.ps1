#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_Common.ps1')

$Root = Get-RepoRoot
Set-Location $Root

$venvPython = Ensure-VirtualEnv -RepoRoot $Root
Install-PythonDependencies -VenvPython $venvPython -RepoRoot $Root

Write-Host 'Resetting local demo data (SQLite) ...'
Invoke-Native -FilePath $venvPython -ArgumentList @('-m', 'scripts.seed_data', '--reset') -WorkingDirectory $Root
Write-Host 'Done. Restart Run-SchoolSystem.cmd if the API is already running.'
