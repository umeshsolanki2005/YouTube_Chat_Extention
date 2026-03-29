# Start the FastAPI server for the YouTube RAG extension.
# Usage (from this folder):  powershell -ExecutionPolicy Bypass -File .\run_backend.ps1
# Or double-click: run_backend.bat

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
# Helps Python on Windows when logging unicode to the console
$env:PYTHONIOENCODING = "utf-8"

$pythonExe = $null
foreach ($candidate in @(
        "venv\Scripts\python.exe",
        ".venv\Scripts\python.exe"
    )) {
    if (Test-Path $candidate) {
        $pythonExe = (Resolve-Path $candidate).Path
        break
    }
}
if (-not $pythonExe) {
    Write-Host ""
    Write-Host "No virtual environment found (venv or .venv)." -ForegroundColor Yellow
    Write-Host "Run first:  powershell -ExecutionPolicy Bypass -File .\setup.ps1" -ForegroundColor Cyan
    Write-Host "Or create one:  python -m venv venv" -ForegroundColor Cyan
    Write-Host ""
    $pythonExe = "python"
}

Write-Host "Using: $pythonExe" -ForegroundColor Gray
& $pythonExe -m pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed. Fix errors above, then try again." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting API at http://127.0.0.1:8000  (keep this window open)" -ForegroundColor Green
Write-Host ""

& $pythonExe app.py
