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
  echo See outputs\js_server_error.log if the window never appeared.
  pause
  exit /b %seedvr_exit_code%
)
endlocal
exit /b 0
