# ==============================================================================
# Indian Stock Extractor - Local Web Server Launcher
# ==============================================================================

[CmdletBinding()]
param (
    [int]$Port = 8000,
    [string]$HostIP = "127.0.0.1"
)

# Auto-detect local Python virtual environment
$PythonCmd = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $PythonCmd = ".\.venv\Scripts\python.exe"
} elseif ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe")) {
    $PythonCmd = "$env:VIRTUAL_ENV\Scripts\python.exe"
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " STARTING INDIAN STOCK EXTRACTOR WEB APP (LOCAL)" -ForegroundColor Cyan
Write-Host " Python:    $PythonCmd" -ForegroundColor Cyan
Write-Host " Host:      $HostIP" -ForegroundColor Cyan
Write-Host " Port:      $Port" -ForegroundColor Cyan
Write-Host " Open:      http://$HostIP`:$Port" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

& $PythonCmd -m uvicorn app:app --host $HostIP --port $Port --reload
