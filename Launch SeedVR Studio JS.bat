@echo off
setlocal
title SeedVR Studio JS
cd /d "%~dp0"
echo Starting SeedVR Studio JS at http://127.0.0.1:7870 ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_js.ps1" %*
set "seedvr_exit_code=%errorlevel%"
if not "%seedvr_exit_code%"=="0" (
  echo.
  echo SeedVR Studio JS failed to start. Exit code: %seedvr_exit_code%
  pause
  exit /b %seedvr_exit_code%
)
exit /b 0
endlocal
