# Copia la base de la oficina (Docker) a Neon para que el portal ciudadano muestre la ultima carga.
# Uso: doble clic en ACTUALIZAR_PORTAL.bat (o: powershell -ExecutionPolicy Bypass -File scripts\actualizar_portal.ps1)
#
# La direccion de Neon (usuario neondb_owner) se lee de la variable SISC_NEON_URL o del archivo .neon_url
# en la raiz del proyecto. Ese archivo NO se sube a GitHub (.gitignore).

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

function Paso($texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }
function Falla($texto) { Write-Host "`nERROR: $texto" -ForegroundColor Red; Read-Host 'Pulse Enter para cerrar'; exit 1 }

$neon = $env:SISC_NEON_URL
if (-not $neon -and (Test-Path '.neon_url')) { $neon = (Get-Content '.neon_url' -Raw).Trim() }
if (-not $neon) { Falla 'No encontre la direccion de Neon. Cree el archivo .neon_url con la cadena de conexion de neondb_owner (sin pooling).' }
if ($neon -match '-pooler') { Falla 'La direccion de Neon usa pooling (-pooler). Copie la conexion directa: en Neon, Connect con "Connection pooling" apagado.' }

$archivo = 'sisc_portal.dump'
# Tablas que el portal no usa (mapa antiguo, archivos de actas, temporal de carga): se copian vacias.
$sinDatos = @('events', 'council_act_files', 'stg_policia_semanal')

try {
    Paso '1/5 Exportando la base de la oficina'
    $excluir = $sinDatos | ForEach-Object { "--exclude-table-data=$_" }
    docker exec sisc_db pg_dump -U sisc_user -d sisc_jamundi -Fc @excluir --exclude-table='respaldo_*' -f /tmp/sisc_portal.dump
    if ($LASTEXITCODE -ne 0) { Falla 'No se pudo exportar. Revise que Docker y el contenedor sisc_db esten encendidos.' }
    docker cp sisc_db:/tmp/sisc_portal.dump ".\$archivo" | Out-Null
    docker exec sisc_db rm -f /tmp/sisc_portal.dump | Out-Null

    Paso '2/5 Probando la conexion con Neon'
    $ok = $false
    foreach ($i in 1..3) {
        docker run --rm postgres:17 psql $neon -tAc 'select 1' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Write-Host "   Sin respuesta (intento $i de 3). Reintentando..."; Start-Sleep -Seconds 10
    }
    if (-not $ok) { Falla 'Neon no responde. Si esta en la red de la oficina, puede que bloquee el puerto 5432: pruebe desde otra red.' }

    Paso '3/5 Cargando en Neon (puede tardar varios minutos; el portal puede fallar mientras tanto)'
    $ok = $false
    foreach ($i in 1..3) {
        docker run --rm -v "${raiz}:/w" postgres:17 pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error -d $neon "/w/$archivo"
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Write-Host "   La carga se interrumpio (intento $i de 3). Reintentando..."; Start-Sleep -Seconds 15
    }
    if (-not $ok) { Falla 'La carga no termino. Vuelva a ejecutar el script; si sigue fallando, pruebe desde otra red.' }

    Paso '4/5 Restableciendo permisos del usuario de solo lectura'
    docker run --rm -v "${raiz}:/w" postgres:17 psql $neon -v ON_ERROR_STOP=1 -q -f /w/docs/despliegue/permisos_portal.sql
    if ($LASTEXITCODE -ne 0) { Falla 'No se pudieron aplicar los permisos. El portal podria no ver datos: ejecute docs\despliegue\permisos_portal.sql en el SQL Editor de Neon.' }

    Paso '5/5 Comprobando'
    docker run --rm postgres:17 psql $neon -c "select max(fecha_evento) as ultimo_hecho, count(*) as hechos from hechos_seguridad;" -c "select conducta_estandar, count(*) from hechos_seguridad group by 1 order by 2 desc limit 6;"
    Write-Host "`nListo. El portal ya muestra los datos de la oficina: https://sisc-portal.onrender.com" -ForegroundColor Green
}
finally {
    # El respaldo tiene los datos completos: no se deja en la carpeta.
    if (Test-Path ".\$archivo") { Remove-Item ".\$archivo" -Force }
}
Read-Host 'Pulse Enter para cerrar'
