@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo   SISC JAMUNDI: TUNEL PROFESIONAL (FIJO)
echo ======================================================
echo.
echo [1/3] Verificando autenticacion...

set CERT_PATH=%USERPROFILE%\.cloudflared\cert.pem

if exist "%CERT_PATH%" goto :authorized

echo [ALERTA] No estas autenticado en Cloudflare.
echo.
echo Por favor, sigue estos pasos:
echo 1. Se abrira una ventana en tu navegador.
echo 2. Inicia sesion con tu cuenta de Cloudflare.
echo 3. Selecciona tu dominio o autoriza el acceso.
echo.
echo Presiona cualquier tecla para abrir el navegador...
pause > nul
.\cloudflared.exe tunnel login

:authorized
echo.
echo [OK] Autenticacion verificada.
echo.
echo [2/3] Verificando tunel 'sisc-jamundi'...
.\cloudflared.exe tunnel create sisc-jamundi 2> tunnel_err.tmp
if %errorlevel% neq 0 (
    echo [INFO] El tunel ya existe o hubo un aviso menor.
)

echo.
echo [3/3] Iniciando el Tunel...
echo ******************************************************
echo   EL ENLACE ES FIJO (Configurado en tu cuenta)
echo ******************************************************
echo.

.\cloudflared.exe tunnel run sisc-jamundi

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No se pudo iniciar el tunel fijo. 
    echo.
    echo Reintentando modo temporal...
    .\cloudflared.exe tunnel --url http://127.0.0.1:5173 --protocol http2
)

pause
