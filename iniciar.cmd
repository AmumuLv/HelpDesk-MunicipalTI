@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\trasladar.ps1" iniciar
exit /b %errorlevel%
