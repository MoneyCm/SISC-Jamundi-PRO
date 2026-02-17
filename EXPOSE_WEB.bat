@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo   SISC JAMUNDI: TUNEL WEB
echo ======================================================
echo.
echo [1/2] Verificando herramienta...

if not exist "cloudflared.exe" (
    echo [ERROR] No encuentro cloudflared.exe. re-descargando...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
)

echo [2/2] Iniciando conexion segura...
echo.
echo ******************************************************
echo   IMPORTANTE: 
echo   Si la ventana se queda "congelada" sin mostrar la URL,
echo   presiona ENTER una vez.
echo.
echo   Busca la linea que empieza por: "URL: https://..."
echo ******************************************************
echo.

.\cloudflared.exe tunnel --url http://127.0.0.1:5173 --protocol http2

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No se pudo iniciar el tunel. 
    echo Intenta ejecutarlo manualmente en PowerShell con:
    echo cd c:\Proyectos\SISC-Jamundi-PRO
    echo .\cloudflared.exe tunnel --url http://localhost:5173 --protocol http2
)

pause
