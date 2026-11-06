#!/usr/bin/env bash
# One-time setup on Debian/Ubuntu (cloud sessions, CI). Safe to re-run. macOS uses tools/setup_mac.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg fontconfig
  else
    echo "Install ffmpeg (with libass and freetype) and fontconfig first." >&2
    exit 1
  fi
fi

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade -q pip
.venv/bin/pip install -q -r requirements.txt
[ -x /opt/pw-browsers/chromium ] || .venv/bin/playwright install chromium

.venv/bin/python tools/doctor.py
