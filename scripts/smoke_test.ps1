<#
.SYNOPSIS
    Smoke-test the running NE-EMIS container API (PowerShell).
    Run against http://localhost:5000 by default.
#>
param(
    [string]$BaseUrl = "http://localhost:5000"
)

Set-StrictMode -Version Latest

Write-Host "==> /health" -ForegroundColor Cyan
Invoke-RestMethod "$BaseUrl/health" | ConvertTo-Json

Write-Host ""
Write-Host "==> GET /students" -ForegroundColor Cyan
$students = Invoke-RestMethod "$BaseUrl/students"
Write-Host "student count = $($students.Count)"
$students | Select-Object -First 3 | ConvertTo-Json

Write-Host ""
Write-Host "==> POST /students (add)" -ForegroundColor Cyan
$body = @{
    first_name          = "Zainab"
    last_name           = "Abubakar"
    dob                 = "2013-01-15"
    gender              = "female"
    current_grade_level = "JSS1-A"
} | ConvertTo-Json
$added = Invoke-RestMethod "$BaseUrl/students" -Method Post -ContentType "application/json" -Body $body
$added | ConvertTo-Json

Write-Host ""
Write-Host "==> GET /students/{ne_sid}" -ForegroundColor Cyan
Invoke-RestMethod "$BaseUrl/students/$($added.ne_sid)" | ConvertTo-Json

Write-Host ""
Write-Host "Smoke test complete." -ForegroundColor Green
