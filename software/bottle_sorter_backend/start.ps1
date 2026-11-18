$ErrorActionPreference = 'Stop'
$backendRoot = $PSScriptRoot
$pythonExe = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Project environment is missing. Install dependencies first.'
}
New-Item -ItemType Directory -Force -Path (Join-Path $backendRoot 'work\temp') | Out-Null
# These settings apply to this process and its children, not Windows global settings.
$env:TEMP = Join-Path $backendRoot 'work\temp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
Push-Location -LiteralPath $backendRoot
try {
    Write-Host 'Dashboard: http://127.0.0.1:8000/'
    Write-Host 'Local API docs: http://127.0.0.1:8000/docs'
    Write-Host 'Press Ctrl+C in this window to stop the server.'
    & $pythonExe -B (Join-Path $backendRoot 'run_server.py')
    if ($LASTEXITCODE -ne 0) { throw 'Server exited with an error. Check the output above.' }
} finally {
    Pop-Location
}
