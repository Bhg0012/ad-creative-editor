"""Sort finished ads into upload folders and write a manifest, so uploading to Meta is a
folder walk, not a guessing game.

Reads batches/<id>/exports/*.mp4 (and statics/*.png) whose names follow the convention
    {market}_{offer}_{angle}_{hooktype}_{length}s_{ratio}_v{n}
and copies each into
    batches/<id>/deliver/<market>/<offer>/<ratio>/<name>.mp4
plus deliver/MANIFEST.csv with one row per file: name, market, offer, angle, hook type, length,
ratio, version, duration, size, and the ad copy file if one exists. Use the same name as the ad
name in Ads Manager; tools/metrics.py groups results by these parts later.

Usage:
    .venv/bin/python tools/deliver.py batches/<id>
    .venv/bin/python tools/deliver.py batches/<id> --by ratio      # deliver/<ratio>/<market>/<offer>/
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import probe  # noqa: E402

NAME = re.compile(r"^(?P<market>[A-Za-z0-9-]+)_(?P<offer>[A-Za-z0-9-]+)_(?P<angle>[A-Za-z0-9-]+)_(?P<hooktype>[A-Za-z0-9-]+)_(?P<length>\d+)s_(?P<ratio>\d+x\d+)_v(?P<version>\d+)$")


def parse_name(stem: str) -> dict | None:
    m = NAME.match(stem)
    return m.groupdict() if m else None


def deliver(batch: Path, by: str = "market") -> list[dict]:
    out = batch / "deliver"
    rows = []
    files = sorted((batch / "exports").glob("*.mp4")) + sorted((batch / "statics").glob("*.png"))
    for f in files:
        parts = parse_name(f.stem)
        if not parts:
            print(f"skip (name not in convention): {f.name}")
            continue
        order = {"market": [parts["market"], parts["offer"], parts["ratio"]],
                 "ratio": [parts["ratio"], parts["market"], parts["offer"]],
                 "offer": [parts["offer"], parts["market"], parts["ratio"]]}[by]
        dst = out.joinpath(*order) / f.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        dur = ""
        if f.suffix == ".mp4":
            try:
                dur = f"{float(probe(f)['format']['duration']):.1f}"
            except Exception:  # noqa: BLE001
                dur = ""
        copy_md = batch / "exports" / f"{f.stem}_copy.md"
        rows.append({"name": f.stem, **parts, "duration_s": dur, "size_mb": f"{f.stat().st_size / 1e6:.1f}",
                     "file": str(dst.relative_to(batch)), "copy": str(copy_md.relative_to(batch)) if copy_md.exists() else ""})
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "MANIFEST.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "market", "offer", "angle", "hooktype", "length", "ratio", "version", "duration_s", "size_mb", "file", "copy"])
        w.writeheader()
        w.writerows(rows)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--by", default="market", choices=("market", "ratio", "offer"), help="top-level folder")
    args = ap.parse_args()
    rows = deliver(Path(args.batch), args.by)
    print(f"{len(rows)} files sorted into {Path(args.batch) / 'deliver'} (MANIFEST.csv alongside)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
