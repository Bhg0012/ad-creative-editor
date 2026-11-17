"""Export every take in a raw recording as its own file, named by what was said, so Bruce can
hand-edit later or hand a folder of clean takes to anyone.

A take is a stretch of speech between pauses (the same split tools/transcribe.py --split uses).
With a words.json next to the raw (work/transcripts/<stem>.words.json) each file is named by
the first words of the take; without one, by its number and timecode. Frame-accurate re-encode
at high quality (libx264 crf 16), audio untouched in level.

Usage:
    .venv/bin/python tools/takes.py raw/truck.mov --out work/takes
    .venv/bin/python tools/takes.py raw/*.mov --out work/takes --transcripts work/transcripts
    .venv/bin/python tools/takes.py --edl work/edl/<adname>.yaml --out work/takes/<adname>   # only the clips that ad uses
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg, load_yaml  # noqa: E402

ENC = ["-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"]
PAD = 0.15   # seconds kept on each side of a take


def slug(text: str, n: int = 4) -> str:
    words = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in text.split()]
    words = [w for w in words if w][:n]
    return "-".join(words) or "take"


def tc(t: float) -> str:
    m, s = divmod(int(t), 60)
    return f"{m:02d}m{s:02d}s"


def cut(src: Path, a: float, b: float, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src),
                    *ENC, "-movflags", "+faststart", str(out)], check=True)


def export_takes(src: Path, out: Path, transcripts: Path | None, min_silence: float = 0.8) -> list[Path]:
    import transcribe as tr  # noqa: WPS433

    words = None
    wj = (transcripts / f"{src.stem}.words.json") if transcripts else None
    if wj and wj.exists():
        words = json.loads(wj.read_text())
    spans = tr.speech_spans(src, min_silence=min_silence)
    written = []
    for i, (a, b) in enumerate(spans, 1):
        if b - a < 0.6:
            continue
        label = tc(a)
        if words:
            said = " ".join(w["word"] for w in words if a - 0.1 <= w["start"] <= b)
            if said.strip():
                label = slug(said)
        dst = out / f"{src.stem}_take{i:02d}_{label}.mp4"
        cut(src, max(0.0, a - PAD), b + PAD, dst)
        written.append(dst)
    return written


def export_edl_clips(edl_path: Path, out: Path) -> list[Path]:
    import render  # noqa: WPS433

    edl = load_yaml(edl_path)
    base = render.batch_dir_of(edl_path)
    written = []
    for n, c in enumerate(edl.get("clips") or [], 1):
        src = Path(str(c.get("src", "")))
        src = src if src.is_absolute() else base / src
        if not src.exists() or "in" not in c:
            continue
        dst = out / f"{edl_path.stem}_clip{n:02d}_{src.stem}_{tc(float(c['in']))}.mp4"
        cut(src, float(c["in"]), float(c["out"]), dst)
        written.append(dst)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raws", nargs="*")
    ap.add_argument("--out", required=True)
    ap.add_argument("--transcripts", help="folder with <stem>.words.json files, for naming by what was said")
    ap.add_argument("--edl", help="export only the clips this EDL uses, in timeline order")
    ap.add_argument("--min-silence", type=float, default=0.8, help="seconds of silence that separate two takes")
    args = ap.parse_args()
    out = Path(args.out)
    if args.edl:
        files = export_edl_clips(Path(args.edl), out)
    else:
        if not args.raws:
            raise SystemExit("give raw files, or --edl")
        files = []
        for r in args.raws:
            files += export_takes(Path(r), out, Path(args.transcripts) if args.transcripts else None, args.min_silence)
    for f in files:
        print(f)
    print(f"{len(files)} files in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
