@echo off
setlocal
title Update SeedVR Studio
cd /d "%~dp0"

set "seedvr_root=%~dp0"
if not exist "%seedvr_root%Launch SeedVR Studio Pro.bat" (
  echo This updater must be placed in the SeedVR Studio folder.
  echo Put it beside Launch SeedVR Studio Pro.bat, then run it again.
  echo.
  pause
  exit /b 1
)

set "seedvr_bootstrap=%TEMP%\seedvr-bootstrap-update-%RANDOM%-%RANDOM%.ps1"
set "seedvr_url=https://raw.githubusercontent.com/vrgamegirl19/VRGDG-SeedVR2-TensorRT-Studio/main/scripts/bootstrap_update.ps1"

echo Downloading the official SeedVR Studio updater...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%seedvr_url%' -OutFile '%seedvr_bootstrap%'"
if errorlevel 1 (
  echo.
  echo The updater could not be downloaded. Check the internet connection and try again.
  del /q "%seedvr_bootstrap%" 2>nul
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%seedvr_bootstrap%" -StudioRoot "%seedvr_root%"
set "seedvr_exit_code=%errorlevel%"
del /q "%seedvr_bootstrap%" 2>nul

echo.
if not "%seedvr_exit_code%"=="0" (
  echo Update failed. Your previous application code was preserved or restored.
  echo See outputs\bootstrap-update.log for details.
) else (
  echo Update complete. Future updates are available from the update button inside Studio.
  echo You can now delete this downloaded BAT file.
)
