"""Default sound effects, synthesized with ffmpeg so the engine works before any library is bought.

Writes pop, click, whoosh, ding, riser as 48 kHz wav files. Real licensed SFX in audio/sfx/
with the same names take priority (tools/render.py looks there first).

Usage:
    .venv/bin/python tools/sfx.py --out audio/sfx/_default
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import run_ffmpeg  # noqa: E402

RECIPES = {
    # short soft pop: a quick sine blip with a fast decay
    "pop": ("sine=frequency=520:sample_rate=48000:duration=0.18", "afade=t=in:d=0.004,afade=t=out:st=0.03:d=0.15,volume=0.8"),
    # click: filtered noise burst, very short
    "click": ("anoisesrc=c=white:r=48000:a=0.6:d=0.06", "highpass=f=1800,afade=t=out:st=0.005:d=0.05,volume=0.7"),
    # whoosh: pink noise with a band sweep and fade
    "whoosh": ("anoisesrc=c=pink:r=48000:a=0.9:d=0.45", "afade=t=in:d=0.12,afade=t=out:st=0.2:d=0.25,highpass=f=400,lowpass=f=5000,volume=0.9"),
    # ding: two partials with a long decay
    "ding": ("sine=frequency=1320:sample_rate=48000:duration=0.7", "afade=t=out:st=0.05:d=0.65,volume=0.5"),
    # riser: rising tone into the CTA
    "riser": ("sine=frequency=220:sample_rate=48000:duration=1.2", "afade=t=in:d=0.6,afade=t=out:st=1.0:d=0.2,volume=0.35"),
}


def ensure_defaults(out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (src, af) in RECIPES.items():
        p = out_dir / f"{name}.wav"
        if not p.exists():
            run_ffmpeg(["-f", "lavfi", "-i", src, "-af", af, "-ac", "2", str(p)])
        paths[name] = p
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    paths = ensure_defaults(Path(args.out))
    print("\n".join(str(p) for p in paths.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
