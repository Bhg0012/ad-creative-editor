"""Inventory every media file in the raw footage folder.

Usage:
    .venv/bin/python tools/inventory.py --raw raw --out batches/<id>/work/inventory.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import display_size, fps, probe, rotation  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
MEDIA_EXT = IMAGE_EXT | {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts", ".wav", ".mp3", ".m4a", ".aac"}

FIELDS = ["file", "kind", "duration_s", "width", "height", "orientation", "rotation", "fps",
          "vcodec", "has_audio", "acodec", "sample_rate", "channels", "size_mb", "flags"]


def describe(path: Path) -> dict:
    info = probe(path)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not (s.get("disposition") or {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration") or 0)
    row = {k: "" for k in FIELDS}
    row["file"] = str(path)
    row["size_mb"] = round(path.stat().st_size / 1e6, 1)
    flags = []
    if v:
        w, h = display_size(v)
        still = path.suffix.lower() in IMAGE_EXT
        row.update(
            kind="image" if still else "video",
            width=w, height=h, rotation=rotation(v),
            orientation="vertical" if h > w else "horizontal" if w > h else "square",
            fps=round(fps(v.get("avg_frame_rate", "0/1")), 3) if not still else "",
            vcodec=v.get("codec_name", ""),
        )
        if not still:
            if min(w, h) < 1080:
                flags.append("below-1080p")
            r_fps, avg_fps = fps(v.get("r_frame_rate", "0/1")), fps(v.get("avg_frame_rate", "0/1"))
            if avg_fps and abs(r_fps - avg_fps) > 0.5:
                flags.append("variable-frame-rate")
            if v.get("color_transfer") in {"arib-std-b67", "smpte2084"}:
                flags.append("HDR (convert to SDR before editing)")
    else:
        row["kind"] = "audio"
    if a:
        row.update(has_audio="yes", acodec=a.get("codec_name", ""),
                   sample_rate=a.get("sample_rate", ""), channels=a.get("channels", ""))
    else:
        row["has_audio"] = "no"
    row["duration_s"] = "" if row["kind"] == "image" else round(duration, 2)
    row["flags"] = "; ".join(flags)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    files = sorted(p for p in Path(args.raw).rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXT)
    if not files:
        print(f"No media found in {args.raw}")
        return 1
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for p in files:
            try:
                w.writerow(describe(p))
            except RuntimeError as e:
                w.writerow({**{k: "" for k in FIELDS}, "file": str(p), "flags": f"unreadable: {e}"})
    print(f"Wrote {len(files)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
