param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Url = 'http://127.0.0.1:7870/'
if (-not (Test-Path -LiteralPath $Python)) { throw 'The virtual environment is missing. Run scripts\setup_app.ps1 first.' }
Set-Location -LiteralPath $Root

$existingListener = Get-NetTCPConnection -LocalPort 7870 -State Listen -ErrorAction SilentlyContinue
if ($existingListener) {
  Write-Host 'SeedVR Studio JS is already running. Opening it now...' -ForegroundColor Green
  if (-not $NoBrowser) { Start-Process $Url }
  exit 0
}

if (-not $NoBrowser) { Start-Process $Url }
& $Python -m uvicorn api_server:app --host 127.0.0.1 --port 7870
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
