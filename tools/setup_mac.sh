#!/usr/bin/env bash
# One-time setup on macOS. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh" >&2
  exit 1
fi

# Homebrew's plain `ffmpeg` (slimmed Jan 2026) lacks libass/freetype, which captions
# and drawtext need. `ffmpeg-full` is keg-only; tools/common.py finds it automatically.
brew install ffmpeg-full python@3.12 node

PY="$(brew --prefix python@3.12)/bin/python3.12"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Optional: auto-editor (first-pass silence removal) is a separate CLI.
brew install auto-editor || echo "auto-editor not installed (optional)"

.venv/bin/python tools/doctor.py
