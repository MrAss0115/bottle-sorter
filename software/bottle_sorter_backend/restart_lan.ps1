$ErrorActionPreference = 'Stop'
$backendRoot = $PSScriptRoot
$runPath = Join-Path $backendRoot 'run_server.py'
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue)
foreach ($ownerId in @($listeners.OwningProcess | Select-Object -Unique)) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerId"
    if ($owner.CommandLine -notmatch [regex]::Escape($runPath)) { throw 'Port 8000 belongs to a different application. It was not stopped.' }
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($owner.ParentProcessId)"
    $stopId = $owner.ProcessId
    if ($parent -and $parent.CommandLine -match [regex]::Escape($runPath)) { $stopId = $parent.ProcessId }
    & taskkill.exe /PID $stopId /T /F
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop the verified backend process.' }
}
$env:BOTTLE_SORTER_HOST = '0.0.0.0'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $backendRoot 'work\temp'
$env:TMP = $env:TEMP
$process = Start-Process -FilePath (Join-Path $backendRoot '.venv\Scripts\python.exe') -ArgumentList @('-B',$runPath) -WorkingDirectory $backendRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $backendRoot 'outputs\lan-server.stdout.log') -RedirectStandardError (Join-Path $backendRoot 'outputs\lan-server.stderr.log') -PassThru
for ($attempt=0; $attempt -lt 40; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 1
        if ($health.status -eq 'ok') { Write-Host 'Backend ready: http://127.0.0.1:8000/ (LAN port 8000)'; exit 0 }
    } catch { Start-Sleep -Milliseconds 200 }
}
throw 'Backend did not become ready; check outputs/lan-server.stderr.log.'
