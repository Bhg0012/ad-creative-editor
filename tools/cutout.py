"""Cut the background off a photo or render so it can float over the footage as a `pip` cutout.

Reference 4's charm is floating characters and objects with no card behind them. Any PNG with a
transparent background works (a mascot from an illustrator, a product shot, a rendered character,
Bruce's own cut-out). This tool makes one from an ordinary photo or render with rembg (free, local,
one-time model download of about 170 MB).

Install once:
    .venv/bin/pip install "rembg[cpu]"

Usage:
    .venv/bin/python tools/cutout.py brand/mascots/van.jpg --out brand/mascots/van.png
    .venv/bin/python tools/cutout.py raw/product*.jpg --out brand/mascots/      # a folder: one PNG per input
Then in the EDL:
    broll:
      - {src: brand/mascots/van.png, at: 4.0, duration: 2.5, pip: {style: cutout, float: true, w: 0.36, y: 0.2}}
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def cutout(src: Path, out: Path, trim: bool = True) -> Path:
    try:
        from rembg import remove
    except ImportError:
        raise SystemExit('rembg is not installed. Run: .venv/bin/pip install "rembg[cpu]"  (one-time, about 170 MB of model)')
    from PIL import Image

    with Image.open(src) as im:
        im = im.convert("RGBA")
        res = remove(im)
    if trim:
        bbox = res.getchannel("A").getbbox()
        if bbox:
            pad = round(0.03 * max(res.size))
            res = res.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(res.width, bbox[2] + pad), min(res.height, bbox[3] + pad)))
    out.parent.mkdir(parents=True, exist_ok=True)
    res.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", required=True, help="a .png path for one image, or a folder for several")
    ap.add_argument("--no-trim", action="store_true", help="keep the full canvas instead of trimming to the subject")
    args = ap.parse_args()
    out = Path(args.out)
    many = len(args.images) > 1 or out.suffix.lower() != ".png"
    for img in args.images:
        src = Path(img)
        dst = (out / f"{src.stem}.png") if many else out
        print(cutout(src, dst, trim=not args.no_trim))
    return 0


if __name__ == "__main__":
    sys.exit(main())
