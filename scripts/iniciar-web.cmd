@echo off
rem Doble clic: levanta la API real y la web, y abre el navegador. Ver iniciar-web.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-web.ps1" %*
pause
