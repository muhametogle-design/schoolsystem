# Shared helpers for SchoolSystem Windows scripts. Dot-source from sibling scripts.
$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

function Get-PythonLauncher {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @{ File = $py.Source; PrefixArgs = @('-3') }
    }
    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return @{ File = $cmd.Source; PrefixArgs = @() }
        }
    }
    throw "Python 3 was not found. Install Python 3.11+ from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
}

function Get-VenvPython {
    param([string]$RepoRoot)
    $candidates = @(
        (Join-Path $RepoRoot '.venv\Scripts\python.exe'),
        (Join-Path $RepoRoot '.venv\bin\python')
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$InstallHint
    )
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        $hint = if ($InstallHint) { " $InstallHint" } else { '' }
        throw "Required command '$Name' was not found.$hint"
    }
    return $cmd
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory
    )
    $previous = Get-Location
    try {
        if ($WorkingDirectory) {
            Set-Location $WorkingDirectory
        }
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
            $joined = $ArgumentList -join ' '
            throw "Command failed (${LASTEXITCODE}): $FilePath $joined"
        }
    }
    finally {
        Set-Location $previous
    }
}

function Ensure-VirtualEnv {
    param([string]$RepoRoot)
    $venvPython = Get-VenvPython -RepoRoot $RepoRoot
    if ($venvPython) { return $venvPython }

    Write-Host 'Creating Python virtual environment in .venv ...'
    $launcher = Get-PythonLauncher
    $pyArgs = @()
    $pyArgs += $launcher.PrefixArgs
    $pyArgs += @('-m', 'venv', '.venv')
    Invoke-Native -FilePath $launcher.File -ArgumentList $pyArgs -WorkingDirectory $RepoRoot
    $venvPython = Get-VenvPython -RepoRoot $RepoRoot
    if (-not $venvPython) {
        throw 'Virtual environment was created but python.exe was not found under .venv.'
    }
    return $venvPython
}

function Install-PythonDependencies {
    param(
        [Parameter(Mandatory = $true)][string]$VenvPython,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )
    Write-Host 'Installing Python dependencies ...'
    Invoke-Native -FilePath $VenvPython -ArgumentList @('-m', 'pip', 'install', '--upgrade', 'pip') -WorkingDirectory $RepoRoot
    Invoke-Native -FilePath $VenvPython -ArgumentList @('-m', 'pip', 'install', '-r', 'requirements-dev.txt') -WorkingDirectory $RepoRoot
}

function Build-ReactWorkspace {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)
    Assert-Command -Name 'npm' -InstallHint 'Install Node.js LTS from https://nodejs.org/' | Out-Null
    $web = Join-Path $RepoRoot 'web'
    Write-Host 'Installing and building the React workspace ...'
    Invoke-Native -FilePath 'npm' -ArgumentList @('ci') -WorkingDirectory $web
    Invoke-Native -FilePath 'npm' -ArgumentList @('run', 'build') -WorkingDirectory $web
    $index = Join-Path $web 'dist\index.html'
    if (-not (Test-Path $index)) {
        throw "React build finished but $index is missing."
    }
}

function Get-DockerExe {
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $pf86 = ${env:ProgramFiles(x86)}
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe')
    )
    if ($pf86) {
        $candidates += (Join-Path $pf86 'Docker\Docker\resources\bin\docker.exe')
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA 'Docker\cli-plugins\docker.exe')
    }
    foreach ($path in $candidates) {
        if ($path -and (Test-Path $path)) { return $path }
    }
    return $null
}
