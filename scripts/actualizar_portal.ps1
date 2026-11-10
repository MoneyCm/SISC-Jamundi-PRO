# Copia la base de la oficina (Docker) a Neon para que el portal ciudadano muestre la ultima carga.
#
# Manual:      doble clic en ACTUALIZAR_PORTAL.bat (siempre copia y muestra el resultado).
# Automatico:  la tarea programada "SISC - Actualizar portal" lo ejecuta con -Auto (sin ventanas):
#              solo copia si los datos cambiaron desde la ultima vez y deja registro en
#              logs\actualizar_portal.log. Para crear la tarea: scripts\programar_actualizacion_portal.ps1
#
# La direccion de Neon (usuario neondb_owner, sin pooling) se lee de SISC_NEON_URL o del archivo
# .neon_url en la raiz del proyecto. Ese archivo NO se sube a GitHub (.gitignore).

param([switch]$Auto)

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
if (-not (Test-Path $docker)) { $docker = 'docker' }
$archivo = 'sisc_portal.dump'
$estadoArchivo = Join-Path $raiz '.portal_sync_state'
$carpetaLogs = Join-Path $raiz 'logs'
# Tablas que el portal no usa (mapa antiguo, archivos de actas, temporal de carga): se copian vacias.
$sinDatos = @('events', 'council_act_files', 'stg_policia_semanal')

if ($Auto) {
    New-Item -ItemType Directory -Force -Path $carpetaLogs | Out-Null
    Start-Transcript -Path (Join-Path $carpetaLogs 'actualizar_portal.log') -Append | Out-Null
}

function Paso($texto) { Write-Host "`n== $(Get-Date -Format 'yyyy-MM-dd HH:mm') $texto" }
function Terminar([int]$codigo) {
    if ($Auto) { Stop-Transcript | Out-Null } else { Read-Host 'Pulse Enter para cerrar' | Out-Null }
    exit $codigo
}
function Falla($texto) { Write-Host "`nERROR: $texto" -ForegroundColor Red; Terminar 1 }

$neon = $env:SISC_NEON_URL
if (-not $neon -and (Test-Path '.neon_url')) { $neon = (Get-Content '.neon_url' -Raw).Trim() }
if (-not $neon) { Falla 'No encontre la direccion de Neon. Cree el archivo .neon_url con la cadena de conexion de neondb_owner (sin pooling).' }
if ($neon -match '-pooler') { Falla 'La direccion de Neon usa pooling (-pooler). Copie la conexion directa: en Neon, Connect con "Connection pooling" apagado.' }

# Huella de los datos que usa el portal: si no cambio desde la ultima copia, no hay nada que subir.
$consultaHuella = @"
select md5(string_agg(t, '|' order by t)) from (
  select 'h:' || count(*) || ':' || coalesce(max(fecha_ingesta)::text, '') as t from hechos_seguridad
  union all select 's:' || count(*) || ':' || coalesce(max(fecha_carga)::text, '') from sabana_snapshot_rows
  union all select 'r:' || count(*) || ':' || coalesce(max(fecha_fin)::text, '') from ingestion_runs
  union all select 'i:' || count(*) from inspeccion_actuaciones
  union all select 'n:' || count(*) from national_crime_stats
  union all select 'q:' || count(*) from institutional_indicators
) x;
"@

try {
    Paso '1/6 Revisando la base de la oficina'
    $huella = (& $docker exec sisc_db psql -U sisc_user -d sisc_jamundi -tAc $consultaHuella 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $huella) { Falla 'No pude leer la base de la oficina. Revise que Docker y el contenedor sisc_db esten encendidos.' }
    $anterior = if (Test-Path $estadoArchivo) { (Get-Content $estadoArchivo -Raw).Trim() } else { '' }
    if ($Auto -and $huella -eq $anterior) {
        Write-Host 'Sin datos nuevos desde la ultima actualizacion. No se copia nada.'
        Terminar 0
    }

    Paso '2/6 Exportando la base de la oficina'
    $excluir = $sinDatos | ForEach-Object { "--exclude-table-data=$_" }
    & $docker exec sisc_db pg_dump -U sisc_user -d sisc_jamundi -Fc @excluir --exclude-table='respaldo_*' -f /tmp/sisc_portal.dump
    if ($LASTEXITCODE -ne 0) { Falla 'No se pudo exportar la base de la oficina.' }
    & $docker cp sisc_db:/tmp/sisc_portal.dump ".\$archivo" | Out-Null
    & $docker exec sisc_db rm -f /tmp/sisc_portal.dump | Out-Null

    Paso '3/6 Probando la conexion con Neon'
    $ok = $false
    foreach ($i in 1..3) {
        & $docker run --rm postgres:17 psql $neon -tAc 'select 1' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Write-Host "   Sin respuesta (intento $i de 3). Reintentando..."; Start-Sleep -Seconds 20
    }
    if (-not $ok) { Falla 'Neon no responde. Si esta en la red de la oficina, puede que bloquee el puerto 5432; se intentara de nuevo en la proxima ejecucion.' }

    Paso '4/6 Cargando en Neon (puede tardar varios minutos; el portal puede fallar mientras tanto)'
    & $docker run --rm -v "${raiz}:/w" postgres:17 psql $neon -v ON_ERROR_STOP=1 -q -f /w/docs/despliegue/limpiar_neon.sql
    if ($LASTEXITCODE -ne 0) { Falla 'No se pudo preparar Neon para la carga (limpiar_neon.sql).' }
    $ok = $false
    foreach ($i in 1..3) {
        & $docker run --rm -v "${raiz}:/w" postgres:17 pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error -d $neon "/w/$archivo"
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Write-Host "   La carga se interrumpio (intento $i de 3). Reintentando..."; Start-Sleep -Seconds 30
    }
    if (-not $ok) { Falla 'La carga no termino. Se intentara de nuevo en la proxima ejecucion (o ejecute ACTUALIZAR_PORTAL.bat).' }

    Paso '5/6 Restableciendo permisos del usuario de solo lectura'
    & $docker run --rm -v "${raiz}:/w" postgres:17 psql $neon -v ON_ERROR_STOP=1 -q -f /w/docs/despliegue/permisos_portal.sql
    if ($LASTEXITCODE -ne 0) { Falla 'No se pudieron aplicar los permisos. Ejecute docs\despliegue\permisos_portal.sql en el SQL Editor de Neon.' }

    Paso '6/6 Comprobando'
    & $docker run --rm postgres:17 psql $neon -c "select max(fecha_evento) as ultimo_hecho, count(*) as hechos from hechos_seguridad;" -c "select conducta_estandar, count(*) from hechos_seguridad group by 1 order by 2 desc limit 6;"
    Set-Content -Path $estadoArchivo -Value $huella -NoNewline
    Write-Host "`nListo. El portal ya muestra los datos de la oficina: https://sisc-portal.onrender.com" -ForegroundColor Green
}
finally {
    # El respaldo tiene los datos completos: no se deja en la carpeta.
    if (Test-Path ".\$archivo") { Remove-Item ".\$archivo" -Force }
}
Terminar 0
