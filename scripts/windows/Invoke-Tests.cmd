@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Invoke-Tests.ps1" %*
