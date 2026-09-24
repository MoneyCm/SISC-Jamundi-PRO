$ErrorActionPreference = 'Stop'
$syncScript = Join-Path $PSScriptRoot 'sync_source_monitors.py'
$running = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like '*sync_source_monitors.py*--watch*' }
if ($running) { exit 0 }
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$projectPath = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Start-Process -FilePath $pythonPath -ArgumentList @('"' + $syncScript + '"', '--watch') `
    -WorkingDirectory $projectPath -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $projectPath 'source-sync.out.log') `
    -RedirectStandardError (Join-Path $projectPath 'source-sync.err.log')
