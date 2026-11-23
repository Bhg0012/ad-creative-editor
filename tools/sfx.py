"""Default sound effects, synthesized with ffmpeg so the engine works before any library is bought.

Writes pop, click, whoosh, ding, riser, thud, swipe, sub, impact, suckback and hit as 48 kHz wav files. Real licensed SFX in audio/sfx/
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
    "click": ("anoisesrc=c=white:r=48000:a=0.6:d=0.06", "highpass=f=1800,lowpass=f=9000,afade=t=in:d=0.002,afade=t=out:st=0.005:d=0.05,volume=0.7"),
    # whoosh: pink noise with a band sweep and fade
    "whoosh": ("anoisesrc=c=pink:r=48000:a=0.9:d=0.45", "afade=t=in:d=0.12,afade=t=out:st=0.2:d=0.25,highpass=f=400,lowpass=f=5000,volume=0.9"),
    # ding: two partials with a long decay
    "ding": ("sine=frequency=1320:sample_rate=48000:duration=0.7", "afade=t=out:st=0.05:d=0.65,volume=0.5"),
    # riser: rising tone into the CTA
    "riser": ("sine=frequency=220:sample_rate=48000:duration=1.2", "afade=t=in:d=0.6,afade=t=out:st=1.0:d=0.2,volume=0.35"),
    # thud: low impact for a big number landing
    "thud": ("sine=frequency=70:sample_rate=48000:duration=0.35", "afade=t=in:d=0.003,afade=t=out:st=0.05:d=0.3,volume=0.9"),
    # swipe: short airy sweep for a card sliding in
    "swipe": ("anoisesrc=c=pink:r=48000:a=0.8:d=0.25", "highpass=f=900,lowpass=f=7000,afade=t=in:d=0.05,afade=t=out:st=0.1:d=0.15,volume=0.7"),
    # sub: a soft low pulse under a reveal
    "sub": ("sine=frequency=45:sample_rate=48000:duration=0.6", "afade=t=in:d=0.08,afade=t=out:st=0.2:d=0.4,volume=0.7"),
    # impact: a low body plus a short noise crack, layered across frequencies so it fills the room (Gavin Herman, V6)
    "impact": ("aevalsrc='0.9*sin(2*PI*55*t)*exp(-7*t)+0.35*(2*random(0)-1)*exp(-35*t)':s=48000:d=0.6", "lowpass=f=4000,afade=t=out:st=0.4:d=0.2,volume=0.9"),
    # suck-back: a whoosh played backwards, pulling into a moment (V6)
    "suckback": ("anoisesrc=c=pink:r=48000:a=0.9:d=0.5", "highpass=f=300,lowpass=f=6000,afade=t=out:st=0.05:d=0.45,areverse,volume=0.8"),
    # hit: an impact with a reverb tail, for the last beat before the end card (V6)
    "hit": ("aevalsrc='0.8*sin(2*PI*80*t)*exp(-6*t)+0.4*(2*random(0)-1)*exp(-25*t)':s=48000:d=1.6", "aecho=0.8:0.6:60|120:0.4|0.25,lowpass=f=5000,afade=t=out:st=0.9:d=0.7,volume=0.8"),
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
