param()
Write-Host 'setup_seedvr2.ps1 is now handled by the complete installer.' -ForegroundColor Yellow
& (Join-Path $PSScriptRoot 'install.ps1')
exit $LASTEXITCODE