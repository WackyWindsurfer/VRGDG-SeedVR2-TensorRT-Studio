param()
Write-Host 'setup_app.ps1 is now handled by the complete installer.' -ForegroundColor Yellow
& (Join-Path $PSScriptRoot 'install.ps1')
exit $LASTEXITCODE