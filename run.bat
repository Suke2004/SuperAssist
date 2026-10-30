@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
cd /d "%~dp0" || exit /b 1
set "UV_PROJECT_ENVIRONMENT=%~dp0.venv"
set "APP_UV=uv"
where uv >nul 2>&1
if not errorlevel 1 goto UV_READY
set "APP_UV=%USERPROFILE%\.local\bin\uv.exe"
if exist "%APP_UV%" goto UV_READY
echo Installing uv from astral.sh...
powershell -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression"
if errorlevel 1 exit /b 1
if not exist "%APP_UV%" (
    echo ERROR: uv was not found. Install it from https://docs.astral.sh/uv/getting-started/installation/ and restart the launcher.
    exit /b 1
)

:UV_READY
set "APP_SYNC_FLAGS="
if "%~1"=="--install" set "APP_SYNC_FLAGS=--reinstall"
if "%~1"=="--update" set "APP_SYNC_FLAGS=--reinstall"
echo Preparing managed Python 3.12 and locked dependencies...
call "%APP_UV%" sync --locked --no-dev --managed-python --python 3.12 %APP_SYNC_FLAGS%
if errorlevel 1 (
    echo ERROR: Setup failed. Check the output above or output\desktop-launch.log.
    exit /b 1
)
echo Starting VeyraCue...
"%~dp0.venv\Scripts\python.exe" main.py
exit /b %errorlevel%
