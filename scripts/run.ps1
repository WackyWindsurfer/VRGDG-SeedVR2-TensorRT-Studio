param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$StudioUrl = 'http://127.0.0.1:7860/'

function Test-SeedVRStudio {
    try {
        $response = Invoke-WebRequest -Uri $StudioUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200 -and $response.Content -match 'SeedVR Studio'
    }
    catch {
        return $false
    }
}

try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw 'The virtual environment is missing. Run scripts\setup_app.ps1 first.'
    }

    if (Test-SeedVRStudio) {
        Write-Host 'SeedVR Studio is already running. Opening it now...' -ForegroundColor Green
        if (-not $NoBrowser) {
            Start-Process $StudioUrl
        }
        exit 0
    }

    Set-Location -LiteralPath $Root
    Write-Host "Starting SeedVR Studio at $StudioUrl" -ForegroundColor Cyan
    & $Python app.py
    $pythonExitCode = $LASTEXITCODE
    if ($null -ne $pythonExitCode -and $pythonExitCode -ne 0) {
        throw "SeedVR Studio exited with code $pythonExitCode."
    }
}
catch {
    Write-Error $_
    exit 1
}
