#!/usr/bin/env bash
# Native macOS/Linux launcher; Windows continues to use run.bat.
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1

if [[ "${1:-}" == --silent ]]; then
    mkdir -p output
    nohup bash "$APP_DIR/run.sh" --background >output/desktop-launch.log 2>&1 </dev/null &
    echo "VeyraCue starting (PID $!). Log: $APP_DIR/output/desktop-launch.log"
    exit 0
fi

APP_PYTHON="$(command -v python3 || command -v python || true)"
if [[ -z "$APP_PYTHON" ]]; then
    echo 'Install Python 3.10+ and its venv module, then run this launcher again.' >&2
    exit 1
fi
"$APP_PYTHON" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'

# Never overwrite the working Windows virtual environment in a shared checkout.
if [[ -x .venv/bin/python ]]; then
    APP_PYTHON="$APP_DIR/.venv/bin/python"
elif [[ -x venv/bin/python ]]; then
    APP_PYTHON="$APP_DIR/venv/bin/python"
else
    "$APP_PYTHON" -m venv .venv
    APP_PYTHON="$APP_DIR/.venv/bin/python"
fi

if [[ "${1:-}" == --update || "${1:-}" == --install ]] ||
   ! "$APP_PYTHON" -c 'import aiofiles, fastapi, webview, importlib.util, sys; assert importlib.util.find_spec("soundcard"); exec("import qtpy.QtWebEngineWidgets, mss" if sys.platform == "linux" else "import AppKit, Quartz")' >/dev/null 2>&1; then
    "$APP_PYTHON" -m pip install -r requirements.txt --timeout 60
fi

if [[ "$(uname -s)" == Linux && -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    echo 'A graphical Linux desktop is required. Start this from your desktop session.' >&2
    exit 1
fi
echo 'Starting VeyraCue. Setup instructions: CROSS_PLATFORM.md'
exec "$APP_PYTHON" main.py
