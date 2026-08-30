param(
    [Parameter(Mandatory = $true)]
    [int]$ServerProcessId
)

$ErrorActionPreference = 'Stop'
$StudioRoot = Split-Path -Parent $PSScriptRoot
$Outputs = Join-Path $StudioRoot 'outputs'
$UpdateLog = Join-Path $Outputs 'update.log'
$Launcher = Join-Path $StudioRoot 'Launch SeedVR Studio Pro.bat'
$InstallScript = Join-Path $PSScriptRoot 'install.ps1'
$PreviousCommit = $null
$UpdateApplied = $false

New-Item -ItemType Directory -Force -Path $Outputs | Out-Null
try { Start-Transcript -Path $UpdateLog -Append | Out-Null } catch {}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'SilentlyContinue'
        $commandOutput = @(& $FilePath @Arguments 2>&1)
        $commandExitCode = $LASTEXITCODE
    }
    catch {
        $commandOutput = @($_.Exception.Message)
        $commandExitCode = 1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return [pscustomobject]@{ ExitCode = $commandExitCode; Output = $commandOutput }
}

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $result = Invoke-NativeCommand -FilePath $Git -Arguments (@('-C', $StudioRoot) + $Arguments)
    if ($result.ExitCode -ne 0) {
        $tail = @($result.Output | Select-Object -Last 12) -join [Environment]::NewLine
        throw "Git failed (exit $($result.ExitCode)). $tail"
    }
    return @($result.Output)
}

function Start-Studio {
    if (Test-Path -LiteralPath $Launcher) {
        # Let the previous launcher finish its browser/profile cleanup before reopening.
        Start-Sleep -Seconds 3
        Start-Process -FilePath $Launcher -WorkingDirectory $StudioRoot
    }
}

try {
    Write-Host 'SeedVR Studio safe updater' -ForegroundColor Cyan
    Write-Host 'Waiting for the running Studio process to close...'
    if (Get-Process -Id $ServerProcessId -ErrorAction SilentlyContinue) {
        Wait-Process -Id $ServerProcessId -Timeout 45 -ErrorAction SilentlyContinue
    }
    if (Get-Process -Id $ServerProcessId -ErrorAction SilentlyContinue) {
        throw 'SeedVR Studio did not close. No files were changed.'
    }

    $gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $gitCommand) { throw 'Git is unavailable. No files were changed.' }
    $Git = $gitCommand.Source

    $insideWorkTree = (Invoke-Git -Arguments @('rev-parse', '--is-inside-work-tree') | Select-Object -Last 1).Trim()
    if ($insideWorkTree -ne 'true') { throw 'This installation is not a Git working tree.' }
    $branch = (Invoke-Git -Arguments @('branch', '--show-current') | Select-Object -Last 1).Trim()
    if ($branch -ne 'main') { throw "Safe updates require the main branch; found '$branch'." }
    $trackedChanges = @(Invoke-Git -Arguments @('status', '--porcelain', '--untracked-files=no') | Where-Object { $_ })
    if ($trackedChanges.Count -gt 0) {
        throw 'Tracked application files have local changes. Update stopped without overwriting them.'
    }

    $PreviousCommit = (Invoke-Git -Arguments @('rev-parse', 'HEAD') | Select-Object -Last 1).Trim()
    Write-Host 'Downloading changed application files...'
    Invoke-Git -Arguments @('fetch', '--quiet', 'origin', 'main') | Out-Null
    $latestCommit = (Invoke-Git -Arguments @('rev-parse', 'FETCH_HEAD') | Select-Object -Last 1).Trim()
    if ($PreviousCommit -eq $latestCommit) {
        Write-Host 'SeedVR Studio is already up to date.' -ForegroundColor Green
        Start-Studio
        exit 0
    }

    $ancestor = Invoke-NativeCommand -FilePath $Git -Arguments @(
        '-C', $StudioRoot, 'merge-base', '--is-ancestor', $PreviousCommit, $latestCommit
    )
    if ($ancestor.ExitCode -ne 0) {
        throw 'The local main branch cannot be updated with a safe fast-forward. No files were changed.'
    }

    $dependencyFiles = @(
        'pyproject.toml',
        'requirements-windows-cu130.txt',
        'requirements-tensorrt.txt',
        'vendor/seedvr2/requirements.txt'
    )
    $changedFiles = @(Invoke-Git -Arguments @('diff', '--name-only', $PreviousCommit, $latestCommit, '--'))
    $dependenciesChanged = @($changedFiles | Where-Object { $dependencyFiles -contains $_ }).Count -gt 0

    Invoke-Git -Arguments @('merge', '--ff-only', 'FETCH_HEAD') | ForEach-Object { Write-Host $_ }
    $UpdateApplied = $true

    if ($dependenciesChanged) {
        Write-Host 'Dependencies changed; refreshing the private Python environment...' -ForegroundColor Yellow
        $repair = Invoke-NativeCommand -FilePath 'powershell.exe' -Arguments @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $InstallScript,
            '-SkipModels', '-SkipTensorRT', '-Repair'
        )
        $repair.Output | ForEach-Object { Write-Host $_ }
        if ($repair.ExitCode -ne 0) {
            throw "Dependency refresh failed (exit $($repair.ExitCode))."
        }
    }

    Write-Host 'Update complete. Restarting SeedVR Studio...' -ForegroundColor Green
    Start-Studio
    Start-Sleep -Seconds 2
}
catch {
    Write-Host ''
    Write-Host ('UPDATE FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    if ($UpdateApplied -and $PreviousCommit -and $Git) {
        Write-Host 'Restoring the previous application version...' -ForegroundColor Yellow
        $rollback = Invoke-NativeCommand -FilePath $Git -Arguments @('-C', $StudioRoot, 'reset', '--hard', $PreviousCommit)
        if ($rollback.ExitCode -eq 0) {
            Write-Host 'Previous application version restored.' -ForegroundColor Green
        }
        else {
            Write-Warning "Automatic rollback failed. See $UpdateLog"
        }
    }
    Write-Host ('Update log: ' + $UpdateLog) -ForegroundColor Yellow
    try { Start-Studio } catch {}
    Read-Host 'Press Enter to close this updater window'
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
}
