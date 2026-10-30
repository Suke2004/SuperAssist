#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
export UV_PROJECT_ENVIRONMENT="$APP_DIR/.venv"

if [[ "$(uname -s)" == Linux && -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    echo 'A graphical Linux desktop is required. Start this from your desktop session.' >&2
    exit 1
fi

if [[ "${1:-}" == --silent ]]; then
    umask 077
    mkdir -p output
    nohup bash "$APP_DIR/run.sh" --background >output/desktop-launch.log 2>&1 </dev/null &
    echo "VeyraCue starting (PID $!). Log: $APP_DIR/output/desktop-launch.log"
    exit 0
fi

APP_UV="$(command -v uv || true)"
if [[ -z "$APP_UV" && -x "$HOME/.local/bin/uv" ]]; then
    APP_UV="$HOME/.local/bin/uv"
fi
if [[ -z "$APP_UV" ]]; then
    echo 'Installing uv from astral.sh...'
    curl --fail --location --silent --show-error https://astral.sh/uv/install.sh | sh
    APP_UV="$HOME/.local/bin/uv"
    if [[ ! -x "$APP_UV" ]]; then
        echo 'uv was not found. See https://docs.astral.sh/uv/getting-started/installation/' >&2
        exit 1
    fi
fi

APP_REINSTALL=''
if [[ "${1:-}" == --update || "${1:-}" == --install ]]; then
    APP_REINSTALL=1
fi
echo 'Preparing managed Python 3.12 and locked dependencies...'
"$APP_UV" sync --locked --no-dev --managed-python --python 3.12 ${APP_REINSTALL:+--reinstall}
echo 'Starting VeyraCue. Setup instructions: CROSS_PLATFORM.md'
exec "$APP_DIR/.venv/bin/python" main.py
