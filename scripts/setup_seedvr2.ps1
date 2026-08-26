$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Engine = Join-Path $Root 'vendor\seedvr2'

if (-not (Test-Path $Python)) {
    & (Join-Path $PSScriptRoot 'setup_app.ps1')
}
if (-not (Test-Path (Join-Path $Engine 'inference_cli.py'))) {
    New-Item -ItemType Directory -Force (Split-Path -Parent $Engine) | Out-Null
    git clone https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git $Engine
}

& $Python -m pip --isolated install --pre torch torchvision torchaudio `
    --index-url https://download.pytorch.org/whl/nightly/cu130 `
    --trusted-host download.pytorch.org --trusted-host download-r2.pytorch.org `
    --trusted-host pypi.org --trusted-host files.pythonhosted.org `
    --retries 1 --timeout 120
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
& $Python -m pip --isolated install --index-url https://pypi.org/simple `
    --trusted-host pypi.org --trusted-host files.pythonhosted.org `
    --retries 1 --timeout 60 -r (Join-Path $Engine 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'SeedVR2 dependency installation failed.' }
Write-Host "SeedVR2 is installed. Model weights will download on the first AI render." -ForegroundColor Green

