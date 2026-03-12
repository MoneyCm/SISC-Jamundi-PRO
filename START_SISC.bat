@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo   INICIANDO SISTEMA SISC JAMUNDI (LOCAL)
echo ======================================================
echo.

echo Verificando si Docker esta corriendo...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker no parece estar funcionando. 
    echo Por favor, abre Docker Desktop y vuelve a intentarlo.
    pause
    exit /b
)

rem Verificar si los contenedores ya estan corriendo
docker ps --filter "name=sisc_backend" --filter "status=running" | findstr "sisc_backend" >nul
if %errorlevel% == 0 (
    echo [INFO] El sistema ya parece estar en ejecucion.
    echo ¿Deseas reiniciar y reconstruir el sistema? (s/N)
    set /p REBUILD=
) else (
    set REBUILD=n
)

if /i "%REBUILD%"=="s" (
    echo [REINICIO] Deteniendo y reconstruyendo...
    docker-compose down
    docker-compose up --build -d
) else (
    echo [INICIO] Levantando servicios (sin reconstruir)...
    docker-compose up -d
)

echo.
echo ======================================================
echo   SISTEMA LISTO
echo ======================================================
echo.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo.
echo Presiona cualquier tecla para cerrar esta ventana y dejar el sistema corriendo en segundo plano.
pause

