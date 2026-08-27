<#
.SYNOPSIS
    Build and push the NE-EMIS image to a container registry (PowerShell).

.EXAMPLE
    .\scripts\push_image.ps1 -Tag "ghcr.io/yourorg/ne-emis:1.0.0"
    .\scripts\push_image.ps1 -Tag "yourregistry.azurecr.io/ne-emis:latest"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Tag
)

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not on PATH. Install Docker Desktop and reopen PowerShell."
}

Write-Host "Building $Tag ..." -ForegroundColor Cyan
docker build -t $Tag .

Write-Host "Pushing $Tag ..." -ForegroundColor Cyan
docker push $Tag

Write-Host ""
Write-Host "Run it:" -ForegroundColor Green
Write-Host "  docker run --rm -p 5000:5000 -e NEEMIS_DEMO_MODE=true $Tag"
Write-Host "  Invoke-RestMethod http://localhost:5000/health"
Write-Host "  Invoke-RestMethod http://localhost:5000/students"
