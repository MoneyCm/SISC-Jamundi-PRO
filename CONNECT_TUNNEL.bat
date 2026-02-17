@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo   SISC JAMUNDI: CONECTANDO TUNEL PERMANENTE
echo ======================================================
echo.

:: REEMPLAZA EL TEXTO ABAJO CON TU TOKEN (EL QUE EMPIEZA POR eyJh...)
set CLOUDFLARE_TOKEN=eyJhIjoiOGRjZjNlYzRmNjdjODUxNmZkZWU1MWZlYzYzYzMzMTEiLCJ0IjoiMjhiNDNmYzUtOGE0YS00OTdiLWFiNWYtODVkNjkxMGE1YTIxIiwicyI6Ik5ETmhOelppTWpndE5XUXdaUzAwTTJKaUxUbGhNVGN0WmpkbVpESTJNek14TkRBMiJ9

if "%CLOUDFLARE_TOKEN%"=="TU_TOKEN_AQUI" (
    echo [ERROR] Debes poner tu TOKEN en este archivo.
    echo Haz clic derecho en este archivo, selecciona 'Editar' y pega el token.
    pause
    exit /b
)

echo Iniciando conexion segura con Cloudflare...
.\cloudflared.exe tunnel run --token %CLOUDFLARE_TOKEN%

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No se pudo conectar el tunel. 
    echo Verifica tu conexion a internet y que el Token sea correcto.
)

pause
