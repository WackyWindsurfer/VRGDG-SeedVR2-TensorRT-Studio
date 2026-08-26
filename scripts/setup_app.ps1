$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $Python)) {
    python -m venv (Join-Path $Root '.venv')
}

& $Python -m pip --isolated install --index-url https://pypi.org/simple `
    --trusted-host pypi.org --trusted-host files.pythonhosted.org `
    --retries 1 --timeout 30 'gradio>=5.49,<7' 'fastapi>=0.115' 'uvicorn>=0.32' 'pillow>=10.4' 'pip-system-certs>=5.3'
if ($LASTEXITCODE -ne 0) { throw 'App dependency installation failed.' }
Write-Host "SeedVR Studio app environment is ready." -ForegroundColor Green
