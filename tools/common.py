"""Shared helpers: repo paths, ffmpeg discovery, config loading, safe zones."""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Homebrew's plain `ffmpeg` formula (slimmed Jan 2026) lacks libass and freetype,
# so captions and drawtext fail. `ffmpeg-full` is keg-only, so look for it first.
_FFMPEG_CANDIDATES = [
    "/opt/homebrew/opt/ffmpeg-full/bin",  # Apple Silicon
    "/usr/local/opt/ffmpeg-full/bin",     # Intel Mac
]

REQUIRED_FILTERS = ["ass", "subtitles", "drawtext", "drawbox", "ebur128", "loudnorm", "tile", "blackdetect", "silencedetect"]

# Fraction of the frame to keep clear, per aspect ratio: (top, bottom, left/right).
# 9:16 is Meta's published Reels safe zone (playbook fact reels_safe_zone).
# 4:5 and 1:1 have no published overlay zone; these are conservative house defaults.
SAFE_ZONES = {
    "9:16": (0.14, 0.35, 0.06),
    "4:5": (0.05, 0.20, 0.05),
    "1:1": (0.05, 0.20, 0.05),
}

# Accepted output sizes per ratio, best first.
RESOLUTIONS = {
    "9:16": [(1440, 2560), (1080, 1920)],
    "4:5": [(1440, 1800), (1080, 1350)],
    "1:1": [(1440, 1440), (1080, 1080)],
}


def find_tool(name: str) -> str | None:
    env = os.environ.get(f"AD_{name.upper()}")
    if env and Path(env).exists():
        return env
    for d in _FFMPEG_CANDIDATES:
        p = Path(d) / name
        if p.exists():
            return str(p)
    return shutil.which(name)


def ffmpeg() -> str:
    path = find_tool("ffmpeg")
    if not path:
        raise SystemExit("ffmpeg not found. Run tools/setup_mac.sh (installs ffmpeg-full).")
    return path


def ffprobe() -> str:
    path = find_tool("ffprobe")
    if not path:
        raise SystemExit("ffprobe not found. Run tools/setup_mac.sh (installs ffmpeg-full).")
    return path


def missing_filters(ffmpeg_path: str) -> list[str]:
    out = subprocess.run([ffmpeg_path, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    present = {line.split()[1] for line in out.splitlines() if len(line.split()) > 2 and not line.startswith("Filters")}
    return [f for f in REQUIRED_FILTERS if f not in present]


def probe(path: str | Path) -> dict:
    res = subprocess.run(
        [ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {res.stderr.strip()}")
    return json.loads(res.stdout)


def rotation(stream: dict) -> int:
    """Display rotation in degrees (phones store portrait video as rotated landscape)."""
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            return int(round(float(sd["rotation"]))) % 360
    tag = (stream.get("tags") or {}).get("rotate")
    return int(tag) % 360 if tag else 0


def display_size(stream: dict) -> tuple[int, int]:
    w, h = int(stream["width"]), int(stream["height"])
    return (h, w) if rotation(stream) in (90, 270) else (w, h)


def fps(rate: str) -> float:
    num, _, den = rate.partition("/")
    den_f = float(den or 1)
    return float(num) / den_f if den_f else 0.0


def ratio_of(width: int, height: int) -> str | None:
    for name in SAFE_ZONES:
        a, b = (int(x) for x in name.split(":"))
        if abs(width / height - a / b) < 0.01:
            return name
    return None


def safe_box(width: int, height: int, ratio: str) -> dict:
    """Pixel margins to keep clear, rounded up so the box is never too generous."""
    top, bottom, side = SAFE_ZONES[ratio]
    return {
        "top": math.ceil(height * top),
        "bottom": math.ceil(height * bottom),
        "side": math.ceil(width * side),
    }


def load_yaml(path: Path) -> dict:
    import yaml  # imported lazily so tools without YAML needs still run

    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict:
    return load_yaml(ROOT / "config.yaml")
