@echo off
setlocal
title SeedVR Studio
cd /d "%~dp0"

echo Starting SeedVR Studio...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run.ps1" %*
set "seedvr_exit_code=%errorlevel%"

if not "%seedvr_exit_code%"=="0" (
    echo.
    echo SeedVR Studio failed to start. Exit code: %seedvr_exit_code%
    echo The error details are shown above.
    pause
)

endlocal
