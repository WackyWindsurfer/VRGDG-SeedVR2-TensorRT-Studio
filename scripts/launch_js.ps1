param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$StudioRoot = Split-Path -Parent $PSScriptRoot
$StudioPython = Join-Path $StudioRoot '.venv\Scripts\python.exe'
$StudioUrl = 'http://127.0.0.1:7870/'
$HealthUrl = $StudioUrl + 'api/health'
$ShutdownUrl = $StudioUrl + 'api/shutdown'
$LogOut = Join-Path $StudioRoot 'outputs\js_server.log'
$LogErr = Join-Path $StudioRoot 'outputs\js_server_error.log'
$BrowserProfile = Join-Path $StudioRoot 'outputs\.studio-browser-profile'
$ServerRootId = $null
$KeepServerAfterLauncher = [bool]$NoBrowser

function Test-JsStudio {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch { return $false }
}

function Find-AppBrowser {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe')
    )
    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Stop-StudioProcessTree([int]$RootProcessId) {
    if (-not $RootProcessId) { return }
    $processes = Get-CimInstance Win32_Process
    $ids = [System.Collections.Generic.List[int]]::new()
    $ids.Add($RootProcessId)
    for ($index = 0; $index -lt $ids.Count; $index++) {
        $parentId = $ids[$index]
        foreach ($child in $processes | Where-Object { $_.ParentProcessId -eq $parentId }) {
            if (-not $ids.Contains([int]$child.ProcessId)) { $ids.Add([int]$child.ProcessId) }
        }
    }
    for ($index = $ids.Count - 1; $index -ge 0; $index--) {
        Stop-Process -Id $ids[$index] -Force -ErrorAction SilentlyContinue
    }
}

function Get-StudioBrowserProcesses {
    return Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @('msedge.exe', 'chrome.exe') -and $_.CommandLine -like "*$BrowserProfile*"
    }
}

function Test-StudioAppWindow {
    foreach ($browserProcess in Get-StudioBrowserProcesses) {
        $nativeProcess = Get-Process -Id $browserProcess.ProcessId -ErrorAction SilentlyContinue
        if ($nativeProcess -and $nativeProcess.MainWindowHandle -ne 0) { return $true }
    }
    return $false
}

function Stop-StudioBrowserProfile {
    $browserIds = Get-StudioBrowserProcesses | Select-Object -ExpandProperty ProcessId
    foreach ($browserId in $browserIds) {
        Stop-Process -Id $browserId -Force -ErrorAction SilentlyContinue
    }
}

try {
    if (-not (Test-Path -LiteralPath $StudioPython)) {
        throw 'The virtual environment is missing. Run scripts\setup_app.ps1 first.'
    }
    if (Test-JsStudio) {
        $listener = Get-NetTCPConnection -LocalPort 7870 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($listener) { $ServerRootId = [int]$listener.OwningProcess }
        Write-Host 'SeedVR Studio JS is already running.' -ForegroundColor Green
    }
    else {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogOut) | Out-Null
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'
        $server = Start-Process -FilePath $StudioPython -WorkingDirectory $StudioRoot -WindowStyle Hidden -PassThru `
            -ArgumentList '-m uvicorn api_server:app --host 127.0.0.1 --port 7870' `
            -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr
        $ServerRootId = $server.Id
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 300
            if (Test-JsStudio) { $ready = $true; break }
            if ($server.HasExited) { throw "SeedVR Studio JS exited during startup. See $LogErr" }
        }
        if (-not $ready) { throw "SeedVR Studio JS did not become ready at $StudioUrl. See $LogErr" }
        Write-Host 'SeedVR Studio JS is ready.' -ForegroundColor Green
    }

    if ($NoBrowser) { exit 0 }
    $browserPath = Find-AppBrowser
    if (-not $browserPath) {
        Start-Process $StudioUrl
        Write-Warning 'A dedicated Edge/Chrome app window was unavailable. Use the Exit Studio button to release GPU and RAM.'
        $KeepServerAfterLauncher = $true
        exit 0
    }
    New-Item -ItemType Directory -Force -Path $BrowserProfile | Out-Null
    $browser = Start-Process -FilePath $browserPath -PassThru -ArgumentList @(
        "--app=$StudioUrl",
        "--user-data-dir=$BrowserProfile",
        '--no-first-run',
        '--disable-background-mode'
    )
    Write-Host 'Close the SeedVR Studio window to stop rendering and release GPU/RAM.' -ForegroundColor Cyan
    $windowSeen = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (Test-StudioAppWindow) { $windowSeen = $true; break }
        if ($browser.HasExited) { break }
    }
    if (-not $windowSeen) { throw 'The SeedVR Studio app window did not open.' }
    while (Test-StudioAppWindow) { Start-Sleep -Milliseconds 500 }
}
catch {
    Write-Error $_
    exit 1
}
finally {
    if (-not $KeepServerAfterLauncher) {
        try { Invoke-WebRequest -Uri $ShutdownUrl -Method Post -UseBasicParsing -TimeoutSec 4 | Out-Null } catch {}
        Start-Sleep -Milliseconds 500
        if ($ServerRootId) { Stop-StudioProcessTree $ServerRootId }
        Stop-StudioBrowserProfile
    }
}
