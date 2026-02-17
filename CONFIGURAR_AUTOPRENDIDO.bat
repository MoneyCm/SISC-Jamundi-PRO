@echo off
setlocal
cd /d %~dp0

echo ======================================================
echo   SISC JAMUNDI: CONFIGURANDO AUTO-ENCENDIDO
echo ======================================================
echo.

:: Ruta a los scripts que queremos arrancar
set START_SCRIPT="%cd%\START_SISC.bat"
set TUNNEL_SCRIPT="%cd%\CONNECT_TUNNEL.bat"

:: Carpeta de Inicio de Windows
set STARTUP_FOLDER="%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo [1/2] Creando acceso directo para el Sistema...
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%STARTUP_FOLDER%\Arrancar_SISC.lnk');$s.TargetPath='%START_SCRIPT%';$s.WorkingDirectory='%cd%';$s.Save()"

echo [2/2] Creando acceso directo para el Tunel...
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%STARTUP_FOLDER%\Conectar_Tunel.lnk');$s.TargetPath='%TUNNEL_SCRIPT%';$s.WorkingDirectory='%cd%';$s.Save()"

echo.
echo ======================================================
echo   ¡CONFIGURACION COMPLETADA!
echo ======================================================
echo.
echo A partir de ahora, cuando prendas el computador:
echo 1. Se abrira una ventana para iniciar Docker y la Pagina.
echo 2. Se abrira otra ventana para conectar el Tunel Web.
echo.
echo Presiona cualquier tecla para finalizar.
pause
