#!/usr/bin/env bash
# ====================================================
# SuperAssist Application Launcher (macOS / Linux)
# ====================================================
# 1. Check Python installation (3.8+)
# 2. Setup virtual environment (venv)
# 3. Install dependencies from requirements.txt
# 4. Check macOS permissions (Accessibility & Screen Recording)
# 5. Launch SuperAssist
# ====================================================

set -e

echo ""
echo "===================================================="
echo "       SUPERASSIST APPLICATION LAUNCHER (macOS)     "
echo "===================================================="
echo ""

# [1/5] Checking Python installation
echo "[1/5] Checking Python installation..."
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "❌ ERROR: Python is not installed or not found in PATH!"
    echo "   Please install Python 3.8+ using Homebrew ('brew install python') or from https://python.org"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
echo "   Found Python $PYTHON_VERSION ($PYTHON_BIN)"

# [2/5] Checking virtual environment
echo "[2/5] Checking virtual environment..."
if [ ! -d "venv" ]; then
    echo "   Creating virtual environment..."
    $PYTHON_BIN -m venv venv
    echo "   Virtual environment created successfully."
else
    echo "   Virtual environment found."
fi

# [3/5] Activating virtual environment
echo "[3/5] Activating virtual environment..."
source venv/bin/activate
echo "   Virtual environment activated ($(python --version))"

# [4/5] Checking dependencies
echo "[4/5] Checking dependencies..."
FAST_BOOT=true
if [ "$1" == "--update" ] || [ "$1" == "--install" ] || [ ! -d "venv/lib" ]; then
    FAST_BOOT=false
fi

# Check if fastapi is installed in the venv
if ! python -c "import fastapi" &>/dev/null; then
    FAST_BOOT=false
fi

if [ "$FAST_BOOT" = true ]; then
    echo "   ⚡ Fast boot: Core dependencies verified. Skipping pip check."
    echo "   (Run './run.sh --update' to reinstall or update dependencies)"
else
    echo "   Upgrading pip..."
    python -m pip install --upgrade pip --quiet --timeout 60 || echo "   ⚠️ pip upgrade skipped"
    echo "   Installing requirements from requirements.txt..."
    pip install -r requirements.txt --timeout 60
    echo "   Dependencies installed successfully."
fi

# Ensure .env exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "📄 Created .env from .env.example — please configure your API keys!"
    else
        echo "⚠️ WARNING: .env not found. Application may require environment variables."
    fi
fi

# macOS Permissions notice
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo ""
    echo "🍎 macOS Permissions Check:"
    echo "   - Accessibility: Required for global hotkeys (Option+H, Option+X, Option+1/2/3)"
    echo "     Grant to Terminal / iTerm in: System Settings > Privacy & Security > Accessibility"
    echo "   - Screen Recording: Required if screen capture / vision analysis is used"
    echo "     Grant in: System Settings > Privacy & Security > Screen Recording"
fi

# [5/5] Launch SuperAssist
echo ""
echo "[5/5] Starting SuperAssist application..."
echo "===================================================="
echo "          APPLICATION STARTING... (Ctrl+C to stop)   "
echo "===================================================="
echo ""

exec python main.py "$@"
