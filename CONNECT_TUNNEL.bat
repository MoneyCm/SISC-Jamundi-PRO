@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo   SISC JAMUNDI: CONECTANDO TUNEL PERMANENTE
echo ======================================================
echo.

rem El token del tunel NO se guarda en este archivo (el repositorio es publico).
rem Se lee de tunnel_token.txt, junto a este archivo, que Git ignora.
rem Tambien puede venir de la variable de entorno CLOUDFLARE_TUNNEL_TOKEN.
set "CLOUDFLARE_TOKEN=%CLOUDFLARE_TUNNEL_TOKEN%"
if exist "%~dp0tunnel_token.txt" set /p CLOUDFLARE_TOKEN=<"%~dp0tunnel_token.txt"

if "%CLOUDFLARE_TOKEN%"=="" (
    echo [ERROR] No encuentro el token del tunel.
    echo Cree el archivo tunnel_token.txt en esta carpeta y pegue en el
    echo una sola linea con el token que le da Cloudflare ^(empieza por eyJ^).
    pause
    exit /b 1
)

echo Iniciando conexion segura con Cloudflare...
.\cloudflared.exe tunnel run --token %CLOUDFLARE_TOKEN%

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No se pudo conectar el tunel.
    echo Verifica tu conexion a internet y que el token de tunnel_token.txt sea el vigente.
)

pause
