@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set "PYTHONUTF8=1"

:: ====================================================
:: SuperAssist Application Launcher
:: ====================================================
:: This batch file will:
:: 1. Check if Python is installed
:: 2. Create a virtual environment if needed
:: 3. Install dependencies from requirements.txt
:: 4. Launch the SuperAssist application
:: ====================================================

echo.
echo ====================================================
echo        SUPERASSIST APPLICATION LAUNCHER
echo ====================================================
echo.

:: Check if Python is installed
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.7+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    exit /b 1
)

:: Get Python version for display
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo    Found Python %PYTHON_VERSION%
echo.

:: Check if virtual environment exists
echo [2/5] Checking virtual environment...
if not exist "venv\" (
    echo    Virtual environment not found, creating one...
    python -m venv venv
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
python -c "import aiofiles, fastapi, webview" >nul 2>&1
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
echo [5/5] Starting SuperAssist application...
echo    Launching main.py...
echo.
echo ====================================================
echo           APPLICATION STARTING...
echo ====================================================
echo.
echo Press Ctrl+C to stop the application
echo.

python main.py

:: Handle application exit
echo.
echo ====================================================
echo           APPLICATION STOPPED
echo ====================================================
echo.

:: Check exit code
if errorlevel 1 (
    echo Application exited with an error code: %errorlevel%
    echo Check the output above for error details
) else (
    echo Application exited normally
)

echo.