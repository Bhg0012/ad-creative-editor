"""Health check: tools installed, config gaps, and playbook freshness.

Usage:
    .venv/bin/python tools/doctor.py            # full report
    .venv/bin/python tools/doctor.py --strict   # exit 1 if any playbook fact is expired
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, find_tool, load_yaml, missing_filters  # noqa: E402

IS_APPLE_SILICON = sys.platform == "darwin" and platform.machine() == "arm64"

PY_PACKAGES = [
    # (import name, pip name, required?)
    ("yaml", "pyyaml", True),
    ("pandas", "pandas", True),
    ("matplotlib", "matplotlib", True),
    ("numpy", "numpy", True),
    ("mlx_whisper", "mlx-whisper", IS_APPLE_SILICON),
    ("scenedetect", "scenedetect[opencv]", False),
    ("librosa", "librosa", False),
    ("auto_editor", "auto-editor", False),
    ("jupyter", "jupyter", False),
]


def check_tools() -> list[str]:
    problems = []
    ff = find_tool("ffmpeg")
    if not ff:
        problems.append("ffmpeg missing -> brew install ffmpeg-full")
    else:
        miss = missing_filters(ff)
        status = "ok" if not miss else f"MISSING FILTERS {miss}"
        print(f"  ffmpeg: {ff} ({status})")
        if miss:
            problems.append(
                f"ffmpeg at {ff} lacks {miss} -> brew install ffmpeg-full "
                "(tools find it automatically under /opt/homebrew/opt/ffmpeg-full)"
            )
    if not find_tool("ffprobe"):
        problems.append("ffprobe missing -> brew install ffmpeg-full")
    for name, pip_name, required in PY_PACKAGES:
        ok = importlib.util.find_spec(name) is not None
        print(f"  python {pip_name}: {'ok' if ok else 'missing'}{'' if required else ' (optional)'}")
        if not ok and required:
            problems.append(f"python package {pip_name} missing -> .venv/bin/pip install -r requirements.txt")
    node = shutil.which("node")
    print(f"  node (for optional Remotion graphics): {node or 'missing (optional) -> brew install node'}")
    return problems


def tbd_paths(node, prefix="") -> list[str]:
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            out += tbd_paths(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, list):
        if any(isinstance(x, str) and x.strip().upper() == "TBD" for x in node):
            out.append(prefix)
        else:
            for i, x in enumerate(node):
                out += tbd_paths(x, f"{prefix}[{i}]")
    elif isinstance(node, str) and node.strip().upper() == "TBD":
        out.append(prefix)
    return out


def stale_facts(facts: list[dict], today: dt.date) -> list[tuple[str, int]]:
    stale = []
    for f in facts:
        verified = f["verified_on"]
        if isinstance(verified, str):
            verified = dt.date.fromisoformat(verified)
        overdue = (today - verified).days - int(f["shelf_life_days"])
        if overdue > 0:
            stale.append((f["id"], overdue))
    return stale


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 if playbook has expired facts")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    print("TOOLS")
    problems = check_tools()

    print("\nCONFIG (fields still TBD)")
    gaps = tbd_paths(load_yaml(ROOT / "config.yaml"))
    print("  " + ("\n  ".join(gaps) if gaps else "none"))

    print("\nPLAYBOOK")
    facts = load_yaml(ROOT / "playbook" / "facts.yaml")["facts"]
    stale = stale_facts(facts, today)
    if stale:
        print(f"  {len(stale)} of {len(facts)} facts EXPIRED -> run /refresh-playbook before strategy work:")
        for fid, days in stale:
            print(f"    {fid} (overdue {days} days)")
    else:
        print(f"  all {len(facts)} facts within shelf life")

    if problems:
        print("\nFIX FIRST")
        for p in problems:
            print(f"  - {p}")
    return 1 if (args.strict and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
