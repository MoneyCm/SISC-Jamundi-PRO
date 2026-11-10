# Crea (o actualiza) la tarea programada de Windows que mantiene el portal ciudadano al dia.
# Ejecutar una sola vez:  powershell -ExecutionPolicy Bypass -File scripts\programar_actualizacion_portal.ps1
#
# - Corre todos los dias a las 8:00 p. m. (despues de la copia de seguridad de las 7:00 p. m.)
#   y tambien al iniciar sesion, por si hubo una carga y el equipo se apago antes de la hora.
# - Si el equipo estaba apagado a la hora programada, corre apenas se encienda.
# - Solo sube a Neon si los datos cambiaron (ver scripts\actualizar_portal.ps1 -Auto).
# - Registro: logs\actualizar_portal.log

param([string]$Hora = '20:00')

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'actualizar_portal.ps1'
$nombre = 'SISC - Actualizar portal'

$accion = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Auto" `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$disparadores = @(
    (New-ScheduledTaskTrigger -Daily -At $Hora),
    (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME)
)
# Al iniciar sesion espera 10 minutos para que Docker termine de arrancar.
$disparadores[1].Delay = 'PT10M'
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparadores -Settings $ajustes `
    -Description 'Copia a Neon la base del SISC de la oficina cuando hay datos nuevos, para el portal ciudadano.' -Force | Out-Null

Write-Host "Tarea '$nombre' programada: todos los dias a las $Hora y al iniciar sesion." -ForegroundColor Green
Write-Host 'Para probarla ahora:  Start-ScheduledTask -TaskName "SISC - Actualizar portal"'
Write-Host 'Registro:             logs\actualizar_portal.log'
