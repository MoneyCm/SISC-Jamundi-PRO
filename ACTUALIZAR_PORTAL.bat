@echo off
REM Actualiza el portal ciudadano con la base de la oficina.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\actualizar_portal.ps1"
