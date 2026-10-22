"""Word-level transcription with mlx-whisper (Apple Silicon).

Writes, per input file:
    <out>/<stem>.words.json   [{"word", "start", "end", "prob"}], times in seconds
    <out>/<stem>.srt          sentence-level subtitles for reading
    <out>/<stem>.txt          plain transcript

Usage:
    .venv/bin/python tools/transcribe.py raw/clip1.mov raw/clip2.mov --out batches/<id>/work/transcripts
    .venv/bin/python tools/transcribe.py exports/ad.mp4 --out ...   # transcribe a finished cut for captions
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg  # noqa: E402

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
# Spelling hints for local names; whisper uses this as context, not as forced output.
DEFAULT_PROMPT = "AuburnSEO. Auburn, Opelika, Huntsville, Alabama. Google reviews, contractors, HVAC, roofing."
SAMPLE_RATE = 16000


def load_audio(path: str):
    """Decode to 16 kHz mono float32 with our own ffmpeg (keg-only ffmpeg-full may not be on PATH)."""
    import numpy as np

    raw = subprocess.run(
        [ffmpeg(), "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def normalize(result: dict) -> list[dict]:
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            text = w["word"].strip()
            if text:
                words.append({"word": text, "start": round(float(w["start"]), 3),
                              "end": round(float(w["end"]), 3), "prob": round(float(w.get("probability", 1.0)), 3)})
    return words


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(result: dict) -> str:
    blocks = []
    for i, seg in enumerate(result.get("segments", []), 1):
        blocks.append(f"{i}\n{srt_time(seg['start'])} --> {srt_time(seg['end'])}\n{seg['text'].strip()}\n")
    return "\n".join(blocks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="spelling/context hint for names")
    args = ap.parse_args()

    try:
        import mlx_whisper
    except ImportError:
        print("mlx-whisper not installed. On Apple Silicon: .venv/bin/pip install mlx-whisper")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in args.files:
        result = mlx_whisper.transcribe(
            load_audio(f), path_or_hf_repo=args.model, word_timestamps=True,
            initial_prompt=args.prompt, language="en",
        )
        stem = Path(f).stem
        words = normalize(result)
        (out / f"{stem}.words.json").write_text(json.dumps(words, indent=1))
        (out / f"{stem}.srt").write_text(to_srt(result))
        (out / f"{stem}.txt").write_text(result.get("text", "").strip() + "\n")
        low = sum(1 for w in words if w["prob"] < 0.5)
        print(f"{f}: {len(words)} words, {low} low-confidence (check these by ear)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
