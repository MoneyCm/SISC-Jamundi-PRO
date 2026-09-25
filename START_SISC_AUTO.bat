@echo off
setlocal
cd /d %~dp0

echo [%date% %time%] Iniciando SISC Jamundi automatico... >> "%~dp0sisc_autostart.log"

rem Intentar abrir Docker Desktop si no esta corriendo.
docker info >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    )
    if exist "%LocalAppData%\Docker\Docker Desktop.exe" (
        start "" "%LocalAppData%\Docker\Docker Desktop.exe"
    )
)

rem Esperar hasta 3 minutos a que Docker quede listo.
for /l %%i in (1,1,36) do (
    docker info >nul 2>&1
    if not errorlevel 1 goto docker_ready
    timeout /t 5 /nobreak >nul
)

echo [%date% %time%] ERROR: Docker no estuvo listo a tiempo. >> "%~dp0sisc_autostart.log"
exit /b 1

:docker_ready
echo [%date% %time%] Docker listo. Levantando contenedores... >> "%~dp0sisc_autostart.log"
docker compose up -d >> "%~dp0sisc_autostart.log" 2>>&1
if errorlevel 1 docker-compose up -d >> "%~dp0sisc_autostart.log" 2>>&1

rem Sincronizar evidencia de monitores desde GitHub en la base local.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\scripts\start_source_sync.ps1" >> "%~dp0sisc_autostart.log" 2>>&1
echo [%date% %time%] SISC solicitado. >> "%~dp0sisc_autostart.log"
exit /b 0
