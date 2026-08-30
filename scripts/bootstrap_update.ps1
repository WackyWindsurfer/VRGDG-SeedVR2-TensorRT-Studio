param(
    [Parameter(Mandatory = $true)]
    [string]$StudioRoot,
    [string]$RepositoryUrl = 'https://github.com/vrgamegirl19/VRGDG-SeedVR2-TensorRT-Studio.git',
    [switch]$NoLaunch,
    [switch]$SkipDependencyRepair
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$StudioRoot = [IO.Path]::GetFullPath($StudioRoot).TrimEnd('\', '/')
$Outputs = Join-Path $StudioRoot 'outputs'
$Log = Join-Path $Outputs 'bootstrap-update.log'
$Launcher = Join-Path $StudioRoot 'Launch SeedVR Studio Pro.bat'
$InstallScript = Join-Path $StudioRoot 'scripts\install.ps1'
$TemporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ('seedvr-bootstrap-' + [guid]::NewGuid().ToString('N'))
$BackupRoot = Join-Path $Outputs ('bootstrap-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$PreviousCommit = $null
$UpdateApplied = $false
$MigrationApplied = $false
$MigrationFiles = @()
$Git = $null

New-Item -ItemType Directory -Force -Path $Outputs | Out-Null
try { Start-Transcript -Path $Log -Append | Out-Null } catch {}

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host ('== ' + $Message + ' ==') -ForegroundColor Cyan
}

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = $machinePath + ';' + $userPath
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )
    $previousPreference = $ErrorActionPreference
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
        $ErrorActionPreference = $previousPreference
    }
    return [pscustomobject]@{ ExitCode = $commandExitCode; Output = $commandOutput }
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingTree,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $result = Invoke-NativeCommand -FilePath $Git -Arguments (
        @('-c', 'http.sslBackend=schannel', '-C', $WorkingTree) + $Arguments
    )
    if ($result.ExitCode -ne 0) {
        $tail = @($result.Output | Select-Object -Last 12) -join [Environment]::NewLine
        throw "Git failed (exit $($result.ExitCode)). $tail"
    }
    return @($result.Output)
}

function Install-GitIfNeeded {
    $gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($gitCommand) { return $gitCommand.Source }
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'Git is required, and Windows Package Manager (winget) is unavailable. Install Git for Windows, then run this updater again.'
    }
    Write-Step 'Installing Git for safe future updates'
    & $winget.Source install --id Git.Git --exact --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) { throw "winget could not install Git (exit $LASTEXITCODE)." }
    Refresh-Path
    $gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $gitCommand) { throw 'Git was installed but is not available yet. Restart Windows, then run this updater again.' }
    return $gitCommand.Source
}

function Get-FileDigest([string]$Path) {
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [IO.File]::ReadAllBytes($Path)
        return [Convert]::ToBase64String($sha256.ComputeHash($bytes))
    }
    finally {
        $sha256.Dispose()
    }
}

function Test-DependencyChange([string]$OldRoot, [string]$NewRoot) {
    $dependencyFiles = @(
        'pyproject.toml',
        'requirements-windows-cu130.txt',
        'requirements-tensorrt.txt',
        'vendor/seedvr2/requirements.txt'
    )
    foreach ($relative in $dependencyFiles) {
        $oldFile = Join-Path $OldRoot ($relative -replace '/', '\')
        $newFile = Join-Path $NewRoot ($relative -replace '/', '\')
        if ((Test-Path -LiteralPath $oldFile -PathType Leaf) -ne (Test-Path -LiteralPath $newFile -PathType Leaf)) {
            return $true
        }
        if (Test-Path -LiteralPath $oldFile -PathType Leaf) {
            if ((Get-FileDigest $oldFile) -ne (Get-FileDigest $newFile)) {
                return $true
            }
        }
    }
    return $false
}

function Backup-ApplicationFiles([string]$SourceRoot, [string[]]$RelativeFiles) {
    $backupFiles = Join-Path $BackupRoot 'files'
    New-Item -ItemType Directory -Force -Path $backupFiles | Out-Null
    foreach ($relative in $RelativeFiles) {
        $source = Join-Path $SourceRoot ($relative -replace '/', '\')
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        $destination = Join-Path $backupFiles ($relative -replace '/', '\')
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
    $RelativeFiles | Set-Content -LiteralPath (Join-Path $BackupRoot 'tracked-files.txt') -Encoding UTF8
}

function Restore-MigratedInstallation {
    Write-Host 'Restoring the previous ZIP-based installation...' -ForegroundColor Yellow
    $gitDirectory = Join-Path $StudioRoot '.git'
    if (Test-Path -LiteralPath $gitDirectory) {
        Remove-Item -LiteralPath $gitDirectory -Recurse -Force
    }
    foreach ($relative in $MigrationFiles) {
        $target = Join-Path $StudioRoot ($relative -replace '/', '\')
        if (Test-Path -LiteralPath $target -PathType Leaf) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    $backupFiles = Join-Path $BackupRoot 'files'
    if (Test-Path -LiteralPath $backupFiles) {
        Get-ChildItem -LiteralPath $backupFiles -File -Recurse | ForEach-Object {
            $relative = $_.FullName.Substring($backupFiles.Length).TrimStart('\', '/')
            $target = Join-Path $StudioRoot $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
    Write-Host 'Previous application code restored.' -ForegroundColor Green
}

function Start-Studio {
    if ($NoLaunch) { return }
    if (Test-Path -LiteralPath $Launcher) {
        Start-Sleep -Seconds 2
        Start-Process -FilePath $Launcher -WorkingDirectory $StudioRoot
    }
}

function Repair-DependenciesIfNeeded([bool]$Changed) {
    if (-not $Changed -or $SkipDependencyRepair) { return }
    Write-Step 'Refreshing changed Python dependencies'
    $repair = Invoke-NativeCommand -FilePath 'powershell.exe' -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $InstallScript,
        '-SkipModels', '-SkipTensorRT', '-Repair'
    )
    $repair.Output | ForEach-Object { Write-Host $_ }
    if ($repair.ExitCode -ne 0) { throw "Dependency refresh failed (exit $($repair.ExitCode))." }
}

try {
    Write-Host 'SeedVR Studio one-time safe update' -ForegroundColor Green
    if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $StudioRoot 'api_server.py') -PathType Leaf) -or
        -not (Test-Path -LiteralPath $InstallScript -PathType Leaf)) {
        throw 'This is not a SeedVR Studio installation. Place the BAT beside Launch SeedVR Studio Pro.bat and try again.'
    }

    $listener = Get-NetTCPConnection -LocalPort 7870 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        throw 'SeedVR Studio is still running. Close its app window, wait a few seconds, then run this updater again.'
    }

    $Git = Install-GitIfNeeded
    $isGitInstallation = Test-Path -LiteralPath (Join-Path $StudioRoot '.git')
    if ($isGitInstallation) {
        Write-Step 'Checking the existing Git installation'
        $inside = (Invoke-Git -WorkingTree $StudioRoot -Arguments @('rev-parse', '--is-inside-work-tree') | Select-Object -Last 1).Trim()
        if ($inside -ne 'true') { throw 'The existing .git folder is not a valid Git working tree.' }
        $branch = (Invoke-Git -WorkingTree $StudioRoot -Arguments @('branch', '--show-current') | Select-Object -Last 1).Trim()
        if ($branch -ne 'main') { throw "Safe updates require the main branch; found '$branch'." }
        $trackedChanges = @(Invoke-Git -WorkingTree $StudioRoot -Arguments @('status', '--porcelain', '--untracked-files=no') | Where-Object { $_ })
        if ($trackedChanges.Count -gt 0) { throw 'Tracked application files have local changes. Nothing was overwritten.' }

        $PreviousCommit = (Invoke-Git -WorkingTree $StudioRoot -Arguments @('rev-parse', 'HEAD') | Select-Object -Last 1).Trim()
        Invoke-Git -WorkingTree $StudioRoot -Arguments @('fetch', '--quiet', 'origin', 'main') | Out-Null
        $latestCommit = (Invoke-Git -WorkingTree $StudioRoot -Arguments @('rev-parse', 'FETCH_HEAD') | Select-Object -Last 1).Trim()
        if ($PreviousCommit -eq $latestCommit) {
            Write-Host 'SeedVR Studio is already up to date.' -ForegroundColor Green
            Start-Studio
            exit 0
        }
        $ancestor = Invoke-NativeCommand -FilePath $Git -Arguments @(
            '-c', 'http.sslBackend=schannel', '-C', $StudioRoot,
            'merge-base', '--is-ancestor', $PreviousCommit, $latestCommit
        )
        if ($ancestor.ExitCode -ne 0) { throw 'The local main branch has diverged. Nothing was overwritten.' }
        $dependencyFiles = @('pyproject.toml', 'requirements-windows-cu130.txt', 'requirements-tensorrt.txt', 'vendor/seedvr2/requirements.txt')
        $changedFiles = @(Invoke-Git -WorkingTree $StudioRoot -Arguments @('diff', '--name-only', $PreviousCommit, $latestCommit, '--'))
        $dependenciesChanged = @($changedFiles | Where-Object { $dependencyFiles -contains $_ }).Count -gt 0
        Invoke-Git -WorkingTree $StudioRoot -Arguments @('merge', '--ff-only', 'FETCH_HEAD') | ForEach-Object { Write-Host $_ }
        $UpdateApplied = $true
        Repair-DependenciesIfNeeded $dependenciesChanged
    }
    else {
        Write-Step 'Downloading the current application code'
        New-Item -ItemType Directory -Force -Path $TemporaryRoot | Out-Null
        $stagedRoot = Join-Path $TemporaryRoot 'repository'
        $clone = Invoke-NativeCommand -FilePath $Git -Arguments @(
            '-c', 'http.sslBackend=schannel', 'clone', '--quiet', '--depth', '1', '--branch', 'main',
            $RepositoryUrl, $stagedRoot
        )
        if ($clone.ExitCode -ne 0) {
            $tail = @($clone.Output | Select-Object -Last 12) -join [Environment]::NewLine
            throw "The current release could not be downloaded. $tail"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $stagedRoot 'api_server.py') -PathType Leaf) -or
            -not (Test-Path -LiteralPath (Join-Path $stagedRoot 'scripts\update.ps1') -PathType Leaf)) {
            throw 'The downloaded repository did not contain a valid SeedVR Studio release.'
        }

        $dependenciesChanged = Test-DependencyChange $StudioRoot $stagedRoot
        $MigrationFiles = @(Invoke-Git -WorkingTree $stagedRoot -Arguments @('ls-files') | Where-Object { $_ })
        if ($MigrationFiles.Count -lt 10) { throw 'The downloaded application file list was unexpectedly incomplete.' }

        Write-Step 'Backing up the current application code'
        Backup-ApplicationFiles $StudioRoot $MigrationFiles
        Write-Host "Backup: $BackupRoot"

        Write-Step 'Installing the update system'
        Copy-Item -LiteralPath (Join-Path $stagedRoot '.git') -Destination (Join-Path $StudioRoot '.git') -Recurse -Force
        $MigrationApplied = $true
        Invoke-Git -WorkingTree $StudioRoot -Arguments @('reset', '--hard', 'HEAD') | ForEach-Object { Write-Host $_ }
        $UpdateApplied = $true
        $trackedChanges = @(Invoke-Git -WorkingTree $StudioRoot -Arguments @('status', '--porcelain', '--untracked-files=no') | Where-Object { $_ })
        if ($trackedChanges.Count -gt 0) { throw 'The migrated application did not finish in a clean state.' }
        Repair-DependenciesIfNeeded $dependenciesChanged
    }

    Write-Host ''
    Write-Host 'SeedVR Studio is updated. Future updates are available from the update button inside Studio.' -ForegroundColor Green
    Start-Studio
}
catch {
    Write-Host ''
    Write-Host ('UPDATE FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    try {
        if ($MigrationApplied) {
            Restore-MigratedInstallation
        }
        elseif ($UpdateApplied -and $PreviousCommit -and $Git) {
            Write-Host 'Restoring the previous Git revision...' -ForegroundColor Yellow
            $rollback = Invoke-NativeCommand -FilePath $Git -Arguments @(
                '-c', 'http.sslBackend=schannel', '-C', $StudioRoot, 'reset', '--hard', $PreviousCommit
            )
            if ($rollback.ExitCode -ne 0) { throw 'Automatic Git rollback failed.' }
            Write-Host 'Previous application revision restored.' -ForegroundColor Green
        }
    }
    catch {
        Write-Warning "Automatic rollback needs attention: $($_.Exception.Message)"
    }
    Write-Host "Update log: $Log" -ForegroundColor Yellow
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
    if (Test-Path -LiteralPath $TemporaryRoot) {
        Remove-Item -LiteralPath $TemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
