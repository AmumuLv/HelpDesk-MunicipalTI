@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\trasladar.ps1" iniciar
set "resultado=%errorlevel%"
if not "%resultado%"=="0" (
    echo.
    echo No se pudo iniciar. La ventana queda abierta para leer el error.
    echo Corrige el problema y vuelve a abrir iniciar.cmd.
    pause
)
exit /b %resultado%
