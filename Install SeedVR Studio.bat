@echo off
setlocal
title Install SeedVR Studio
cd /d "%~dp0"
echo Installing SeedVR Studio and its GPU runtime...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
set "seedvr_exit_code=%errorlevel%"
echo.
if not "%seedvr_exit_code%"=="0" (
  echo Installation failed. See the message above and outputs\install.log.
) else (
  echo Installation complete.
  echo Double-click Launch SeedVR Studio Pro.bat to start the app.
)
pause
exit /b %seedvr_exit_code%
