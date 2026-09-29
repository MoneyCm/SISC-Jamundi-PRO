# Copia de seguridad diaria de la base de datos del SISC (la ejecuta el Programador de tareas de Windows).
#
# - Guarda Documentos\SISC Respaldos\sisc-AAAA-MM-DD.dump (formato comprimido de PostgreSQL).
# - Antes de guardarla comprueba que la copia se pueda leer (pg_restore -l).
# - Conserva las 14 copias mas recientes y la ultima de cada mes de los ultimos 12 meses;
#   las demas van a la Papelera de reciclaje (nunca se borran de forma definitiva).
# - Deja el resultado en backend\data\respaldo_estado.json, que el SISC muestra en el Centro de fuentes.
#
# Para restaurar una copia (solo con autorizacion y otra copia previa):
#   docker cp "<archivo>.dump" sisc_db:/tmp/r.dump
#   docker exec sisc_db sh -c 'pg_restore -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists /tmp/r.dump'

$ErrorActionPreference = 'Stop'
$destino = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'SISC Respaldos'
$estadoArchivo = Join-Path $PSScriptRoot '..\backend\data\respaldo_estado.json'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$diarias = 14
$mensuales = 12

function Guardar-Estado([bool]$ok, [string]$mensaje, [string]$archivo, [double]$tamanoMb) {
    $copias = @(Get-ChildItem -Path $destino -Filter 'sisc-*.dump' -ErrorAction SilentlyContinue)
    $estado = [ordered]@{
        fecha      = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss')
        ok         = $ok
        mensaje    = $mensaje
        archivo    = $archivo
        tamano_mb  = [math]::Round($tamanoMb, 1)
        copias     = $copias.Count
        carpeta    = $destino
    }
    if ($ok) { $estado['ultima_exitosa'] = $estado['fecha'] }
    elseif (Test-Path $estadoArchivo) {
        $anterior = Get-Content $estadoArchivo -Raw | ConvertFrom-Json
        if ($anterior.ultima_exitosa) { $estado['ultima_exitosa'] = $anterior.ultima_exitosa }
    }
    $json = $estado | ConvertTo-Json
    [System.IO.File]::WriteAllText($estadoArchivo, $json, (New-Object System.Text.UTF8Encoding($false)))
}

try {
    New-Item -ItemType Directory -Force -Path $destino | Out-Null
    $nombre = 'sisc-' + (Get-Date -Format 'yyyy-MM-dd') + '.dump'
    $final = Join-Path $destino $nombre

    & $docker exec sisc_db sh -c 'pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc -f /tmp/sisc_respaldo.dump'
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar la copia (pg_dump). Revise que Docker y el SISC esten encendidos.' }
    & $docker exec sisc_db sh -c 'pg_restore -l /tmp/sisc_respaldo.dump > /dev/null'
    if ($LASTEXITCODE -ne 0) { throw 'La copia generada no se puede leer (pg_restore).' }
    & $docker cp sisc_db:/tmp/sisc_respaldo.dump $final
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo copiar el archivo al computador.' }
    & $docker exec sisc_db rm -f /tmp/sisc_respaldo.dump

    # Rotacion: 14 diarias + la ultima de cada mes (12 meses). Lo demas, a la Papelera.
    Add-Type -AssemblyName Microsoft.VisualBasic
    $todas = @(Get-ChildItem -Path $destino -Filter 'sisc-*.dump' | Sort-Object Name -Descending)
    $conservar = @{}
    $todas | Select-Object -First $diarias | ForEach-Object { $conservar[$_.Name] = $true }
    $todas | Group-Object { $_.Name.Substring(5, 7) } | Select-Object -First ($mensuales + 1) |
        ForEach-Object { $conservar[($_.Group | Select-Object -First 1).Name] = $true }
    foreach ($copia in $todas) {
        if (-not $conservar.ContainsKey($copia.Name)) {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($copia.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin')
        }
    }

    $tamano = (Get-Item $final).Length / 1MB
    Guardar-Estado $true 'Copia creada y verificada.' $nombre $tamano
}
catch {
    Guardar-Estado $false $_.Exception.Message '' 0
    exit 1
}
