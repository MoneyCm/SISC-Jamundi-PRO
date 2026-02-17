@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo   INICIANDO SISTEMA SISC JAMUNDI (LOCAL)
echo ======================================================
echo.
echo Ubicacion: %cd%
echo.
echo Verificando si Docker esta corriendo...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker no parece estar funcionando. 
    echo Por favor, abre Docker Desktop y vuelve a intentarlo.
    pause
    exit /b
)

echo Deteniendo posibles contenedores previos...
docker-compose down

echo Levantando servicios del SISC Jamundi...
docker-compose up --build -d

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
