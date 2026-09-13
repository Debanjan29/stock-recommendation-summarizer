# ==============================================================================
# 2-STAGE AUTOMATED AGY STOCK EXTRACTION PIPELINE POWERSHELL SCRIPT
# Step 1: Saves translated transcript to text file (reuses if already exists)
# Step 2: Analyzes transcript with LLM / AGY Engine & saves 'DD-MM-YY - Title.md'
# ==============================================================================

[CmdletBinding()]
param (
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Url,
    [Parameter(Position=1)]
    [string]$Method = "agy",
    [Parameter(Position=2)]
    [string]$Format = "markdown",
    [Alias("dangerously-skip-permissions")]
    [switch]$DangerouslySkipPermissions,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$RemainingArgs
)

# Sanitize method if a flag or switch was passed positionally
if ($Method -like "-*") {
    $Method = "agy"
}

# Auto-detect local virtual environment Python
$PythonCmd = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $PythonCmd = ".\.venv\Scripts\python.exe"
} elseif ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe")) {
    $PythonCmd = "$env:VIRTUAL_ENV\Scripts\python.exe"
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " STARTING AUTOMATED AGY STOCK EXTRACTION PIPELINE" -ForegroundColor Cyan
Write-Host " Video URL: $Url" -ForegroundColor Cyan
Write-Host " Python:    $PythonCmd" -ForegroundColor Cyan
Write-Host " Method:    $Method" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

& $PythonCmd pipeline.py "$Url" --method $Method --format $Format

