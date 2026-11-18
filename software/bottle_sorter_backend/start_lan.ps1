$ErrorActionPreference = 'Stop'
$oldHost = $env:BOTTLE_SORTER_HOST
try {
    $env:BOTTLE_SORTER_HOST = '0.0.0.0'
    Write-Host 'LAN mode: Arduino sends to http://YOUR_PC_LAN_IP:8000'
    & (Join-Path $PSScriptRoot 'start.ps1')
} finally {
    $env:BOTTLE_SORTER_HOST = $oldHost
}
