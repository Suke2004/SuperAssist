#!/usr/bin/env bash
# Shared quiet launcher for macOS and Linux; diagnostics go to output/desktop-launch.log.
exec bash "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/run.sh" --silent >/dev/null
