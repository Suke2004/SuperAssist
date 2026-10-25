@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
cd /d "%~dp0" || exit /b 1
set "APP_PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%APP_PYTHON%" set "APP_PYTHON=python"

:: ====================================================
:: VeyraCue Application Launcher
:: ====================================================
:: This batch file will:
:: 1. Check if Python is installed
:: 2. Create a virtual environment if needed
:: 3. Install dependencies from requirements.txt
:: 4. Launch the VeyraCue application
:: ====================================================

echo.
echo ====================================================
echo        VEYRACUE DESKTOP LAUNCHER
echo ====================================================
echo.

:: Check if Python is installed
echo [1/5] Checking Python installation...
"%APP_PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    exit /b 1
)

"%APP_PYTHON%" --version
echo.

:: Check if virtual environment exists
echo [2/5] Checking virtual environment...
if not exist "venv\" (
    echo    Virtual environment not found, creating one...
    "%APP_PYTHON%" -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment!
        echo Make sure you have the 'venv' module available
        exit /b 1
    )
    echo    Virtual environment created successfully
) else (
    echo    Virtual environment found
)
echo.

:: Activate virtual environment
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment!
    exit /b 1
)
echo    Virtual environment activated
echo.

:: Check and install/update dependencies if needed
echo [4/5] Checking dependencies...
if "%1"=="--update" goto INSTALL_DEPS
if "%1"=="--install" goto INSTALL_DEPS
if not exist "venv\Lib\site-packages\fastapi\" goto INSTALL_DEPS
if not exist "venv\Lib\site-packages\aiofiles\" goto INSTALL_DEPS
python -c "import aiofiles, fastapi, webview, pyaudiowpatch" >nul 2>&1
if errorlevel 1 goto INSTALL_DEPS

echo    Fast boot: Core dependencies verified. Skipping slow pip check.
echo    (Run 'run.bat --update' if you need to reinstall/update requirements)
goto DEPS_DONE

:INSTALL_DEPS
echo    Upgrading pip...
python -m pip install --upgrade pip --quiet --timeout 60
if errorlevel 1 (
    echo WARNING: Failed to upgrade pip, continuing anyway...
)

echo    Installing requirements from requirements.txt...
python -m pip install -r requirements.txt --quiet --timeout 60
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    echo Please check requirements.txt and your internet connection
    exit /b 1
)
echo    Dependencies installed successfully

:DEPS_DONE
echo.

:: Check if .env file exists (the app may need it)
if not exist ".env" (
    echo WARNING: .env file not found!
    echo The application may require environment variables.
    echo Consider creating a .env file if the app doesn't start properly.
    echo.
)

:: Launch the application
echo [5/5] Starting VeyraCue desktop assistant...
echo    Launching main.py...
echo.
echo ====================================================
echo           APPLICATION STARTING...
echo ====================================================
echo.
echo Press Ctrl+C to stop the application
echo.

if "%~1"=="--silent" (
    python main.py >nul
) else (
    python main.py
)
set "APP_EXIT_CODE=!errorlevel!"

:: Handle application exit
echo.
echo ====================================================
echo           APPLICATION STOPPED
echo ====================================================
echo.

:: Check exit code
if not "%APP_EXIT_CODE%"=="0" (
    echo Application exited with an error code: %APP_EXIT_CODE%
    echo Check the output above for error details
) else (
    echo Application exited normally
)

echo.
exit /b %APP_EXIT_CODE%
