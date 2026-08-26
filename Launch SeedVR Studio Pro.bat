@echo off
setlocal
title SeedVR Studio Pro
cd /d "%~dp0"
echo Starting SeedVR Studio Pro...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_js.ps1" %*
set "seedvr_exit_code=%errorlevel%"
if not "%seedvr_exit_code%"=="0" (
  echo.
  echo SeedVR Studio Pro failed to start. Exit code: %seedvr_exit_code%
  pause
  exit /b %seedvr_exit_code%
)
echo SeedVR Studio Pro is running at http://127.0.0.1:7870
endlocal
exit /b 0
