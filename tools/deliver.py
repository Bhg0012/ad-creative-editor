"""Sort finished ads into upload folders and write a manifest, so uploading to Meta is a
folder walk, not a guessing game.

Reads batches/<id>/exports/*.mp4 (and statics/*.png) whose names follow the convention
    {market}_{offer}_{price}_{angle}_{hooktype}_{length}s_{ratio}_v{n}
and copies each into
    batches/<id>/deliver/<market>/<offer>/<price>/<ratio>/<name>.mp4
plus deliver/MANIFEST.csv with one row per file: name, market, offer, price, angle, hook type, length,
ratio, version, duration, size, and the ad copy file if one exists. Use the same name as the ad
name in Ads Manager; tools/metrics.py groups results by these parts later.

Copy to Google Drive (or any synced folder): set `delivery.copy_to` in config.yaml, e.g.
    delivery:
      copy_to: "~/Library/CloudStorage/GoogleDrive-*/My Drive/AuburnSEO Ads"
The `*` matches your Google account folder, so no email address lives in the repo. Each run copies
the sorted deliver/ tree to <copy_to>/<batch id>/, MANIFEST.csv included. Only finished files go;
raw footage and work files never leave the repo folder. `--to <folder>` overrides the config for one
run; `--no-copy` skips it.

Usage:
    .venv/bin/python tools/deliver.py batches/<id>
    .venv/bin/python tools/deliver.py batches/<id> --by ratio      # deliver/<ratio>/<market>/<offer>/<price>/
    .venv/bin/python tools/deliver.py batches/<id> --to "~/Desktop/ads"
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config, parse_ad_name, probe  # noqa: E402


def parse_name(stem: str) -> dict | None:
    d = parse_ad_name(stem)
    if d:
        d.pop("has_price", None)
    return d


def deliver(batch: Path, by: str = "market") -> list[dict]:
    out = batch / "deliver"
    rows = []
    files = sorted((batch / "exports").glob("*.mp4")) + sorted((batch / "statics").glob("*.png"))
    for f in files:
        parts = parse_name(f.stem)
        if not parts:
            print(f"skip (name not in convention): {f.name}")
            continue
        order = {"market": [parts["market"], parts["offer"], parts["price"], parts["ratio"]],
                 "ratio": [parts["ratio"], parts["market"], parts["offer"], parts["price"]],
                 "offer": [parts["offer"], parts["price"], parts["market"], parts["ratio"]]}[by]
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
        w = csv.DictWriter(fh, fieldnames=["name", "market", "offer", "price", "angle", "hooktype", "length", "ratio", "version", "duration_s", "size_mb", "file", "copy"])
        w.writeheader()
        w.writerows(rows)
    return rows


def resolve_copy_to(pattern: str) -> Path:
    """Expand ~ and one glob (the Google account folder) into a real, existing folder."""
    import glob

    expanded = str(Path(pattern).expanduser())
    if any(ch in expanded for ch in "*?["):
        # glob the deepest existing prefix that contains the wildcard, keep the rest as plain folders
        parts = Path(expanded).parts
        for i in range(len(parts), 0, -1):
            head = str(Path(*parts[:i]))
            if any(ch in head for ch in "*?["):
                hits = sorted(glob.glob(head))
                if hits:
                    if len(hits) > 1:
                        print(f"note: {len(hits)} folders match {head}; using {hits[0]}")
                    return Path(hits[0]).joinpath(*parts[i:])
        raise SystemExit(f"copy_to {pattern!r}: no folder matches. Is Google Drive for desktop running and signed in?")
    return Path(expanded)


def copy_out(batch: Path, dest_root: Path) -> Path:
    """Mirror batches/<id>/deliver into <dest_root>/<batch id>/ (only finished files)."""
    src = batch / "deliver"
    if not src.exists():
        raise SystemExit("nothing to copy: run deliver first")
    base = dest_root.parent if dest_root.name else dest_root
    if not base.exists():
        raise SystemExit(f"{base} does not exist. Is Google Drive for desktop running and signed in?")
    dest = dest_root / batch.resolve().name
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src.rglob("*"):
        if f.is_file():
            t = dest / f.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            if not t.exists() or t.stat().st_size != f.stat().st_size or t.stat().st_mtime < f.stat().st_mtime:
                shutil.copy2(f, t)
                n += 1
    print(f"copied {n} new or changed files to {dest}")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--by", default="market", choices=("market", "ratio", "offer"), help="top-level folder")
    ap.add_argument("--to", help="copy the sorted folders here too (overrides delivery.copy_to in config.yaml)")
    ap.add_argument("--no-copy", action="store_true", help="skip the copy to Google Drive for this run")
    args = ap.parse_args()
    batch = Path(args.batch)
    rows = deliver(batch, args.by)
    print(f"{len(rows)} files sorted into {batch / 'deliver'} (MANIFEST.csv alongside)")
    target = args.to or str(((load_config().get("delivery") or {}).get("copy_to")) or "")
    if target and not args.no_copy:
        copy_out(batch, resolve_copy_to(target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
