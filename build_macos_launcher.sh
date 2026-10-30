#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
osacompile -o VeyraCue.app VeyraCue.applescript
# macOS requires a usage description when recording is attributed to the app bundle.
/usr/bin/defaults write "$APP_DIR/VeyraCue.app/Contents/Info" NSMicrophoneUsageDescription -string 'VeyraCue transcribes your microphone and routed meeting audio.'
