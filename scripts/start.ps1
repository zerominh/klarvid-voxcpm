Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Error "Chua co venv. Chay: py -3.11 -m venv .venv"
}

.\.venv\Scripts\Activate.ps1

if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#") -or $line -notmatch "=") { return }
        $parts = $line.Split("=", 2)
        Set-Item -Path ("Env:" + $parts[0].Trim()) -Value $parts[1].Trim()
    }
}

if (-not $env:HOST) { $env:HOST = "127.0.0.1" }
if (-not $env:PORT) { $env:PORT = "8000" }
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

Write-Host "Starting Klarvid VoxCPM on http://$($env:HOST):$($env:PORT) (workers=1)"
python -m uvicorn app.main:app --host $env:HOST --port $env:PORT --workers 1
