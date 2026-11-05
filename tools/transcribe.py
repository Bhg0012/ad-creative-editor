"""Word-level transcription with the best backend available on this machine.

Backends (auto picks the first that imports):
    mlx       mlx-whisper, Apple Silicon GPU. Fast; word timings are attention based (about +/-150 ms).
    whisperx  WhisperX: faster-whisper plus forced alignment. Tightest word boundaries; best for
              karaoke / word-by-word captions. CPU int8 on Mac. Numbers may get interpolated timing.
    faster    faster-whisper (CTranslate2), CPU int8. Any platform.
    openai    openai-whisper (PyTorch). Slowest; last resort.

Writes, per input file:
    <out>/<stem>.words.json   [{"word", "start", "end", "prob"}], times in seconds
    <out>/<stem>.srt          sentence-level subtitles for reading
    <out>/<stem>.txt          plain transcript

Usage:
    .venv/bin/python tools/transcribe.py raw/clip1.mov raw/clip2.mov --out batches/<id>/work/transcripts
    .venv/bin/python tools/transcribe.py work/cuts/ad_master.mp4 --out work/transcripts   # for captions
    .venv/bin/python tools/transcribe.py ... --backend whisperx --model large-v3-turbo
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg  # noqa: E402

BACKENDS = ("mlx", "whisperx", "faster", "openai")
MODULES = {"mlx": "mlx_whisper", "whisperx": "whisperx", "faster": "faster_whisper", "openai": "whisper"}
DEFAULT_MODELS = {
    "mlx": "mlx-community/whisper-large-v3-turbo",
    "whisperx": "large-v3-turbo",
    "faster": "large-v3-turbo",
    "openai": "turbo",
}
# Spelling hints for local names; whisper uses this as context, not as forced output.
DEFAULT_PROMPT = "AuburnSEO. Auburn, Opelika, Huntsville, Alabama. Google reviews, contractors, HVAC, roofing."
SAMPLE_RATE = 16000


def pick_backend(name: str = "auto") -> str | None:
    if name != "auto":
        return name if importlib.util.find_spec(MODULES[name]) else None
    for b in BACKENDS:
        if importlib.util.find_spec(MODULES[b]):
            return b
    return None


def load_audio(path: str | Path):
    """Decode to 16 kHz mono float32 with our own ffmpeg (keg-only ffmpeg-full may not be on PATH)."""
    import numpy as np

    raw = subprocess.run(
        [ffmpeg(), "-nostdin", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def normalize(result: dict) -> list[dict]:
    """openai-whisper / mlx-whisper / whisperx result dict -> flat word list."""
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            text = str(w.get("word", "")).strip()
            if not text or w.get("start") is None or w.get("end") is None:
                continue
            prob = w.get("probability", w.get("score", 1.0))
            words.append({"word": text, "start": round(float(w["start"]), 3),
                          "end": round(float(w["end"]), 3), "prob": round(float(prob if prob is not None else 1.0), 3)})
    return words


def fill_missing_times(result: dict) -> dict:
    """WhisperX leaves numbers and symbols without timing; interpolate between neighbours."""
    for seg in result.get("segments", []):
        ws = seg.get("words") or []
        for i, w in enumerate(ws):
            if w.get("start") is None or w.get("end") is None:
                prev_end = next((ws[j]["end"] for j in range(i - 1, -1, -1) if ws[j].get("end") is not None), seg.get("start", 0.0))
                next_start = next((ws[j]["start"] for j in range(i + 1, len(ws)) if ws[j].get("start") is not None), seg.get("end", prev_end + 0.3))
                w["start"], w["end"] = prev_end, max(prev_end + 0.05, next_start)
    return result


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


def run_backend(backend: str, audio, model: str, prompt: str) -> dict:
    if backend == "mlx":
        import mlx_whisper

        return mlx_whisper.transcribe(audio, path_or_hf_repo=model, word_timestamps=True,
                                      initial_prompt=prompt, language="en")
    if backend == "faster":
        from faster_whisper import WhisperModel

        m = WhisperModel(model, device="auto", compute_type="int8")
        segments, _info = m.transcribe(audio, word_timestamps=True, initial_prompt=prompt, language="en",
                                       vad_filter=True)
        segs = []
        for s in segments:
            segs.append({"start": s.start, "end": s.end, "text": s.text,
                         "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                                   for w in (s.words or [])]})
        return {"text": "".join(s["text"] for s in segs), "segments": segs}
    if backend == "whisperx":
        import whisperx

        device = "cpu"
        m = whisperx.load_model(model, device, compute_type="int8", language="en",
                                asr_options={"initial_prompt": prompt})
        result = m.transcribe(audio, batch_size=8, language="en")
        align_model, meta = whisperx.load_align_model(language_code="en", device=device)
        aligned = whisperx.align(result["segments"], align_model, meta, audio, device, return_char_alignments=False)
        aligned = fill_missing_times(aligned)
        aligned["text"] = " ".join(s.get("text", "").strip() for s in aligned["segments"])
        return aligned
    if backend == "openai":
        import whisper

        m = whisper.load_model(model)
        return m.transcribe(audio, word_timestamps=True, initial_prompt=prompt, language="en")
    raise SystemExit(f"unknown backend {backend}")


def transcribe_file(path: str | Path, out: Path, backend: str, model: str | None, prompt: str) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    result = run_backend(backend, load_audio(path), model or DEFAULT_MODELS[backend], prompt)
    stem = Path(path).stem
    words = normalize(result)
    (out / f"{stem}.words.json").write_text(json.dumps(words, indent=1))
    (out / f"{stem}.srt").write_text(to_srt(result))
    (out / f"{stem}.txt").write_text(str(result.get("text", "")).strip() + "\n")
    low = sum(1 for w in words if w["prob"] < 0.5)
    print(f"{path}: {len(words)} words via {backend}, {low} low-confidence (check these by ear)")
    return words


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--backend", default="auto", choices=("auto", *BACKENDS))
    ap.add_argument("--model", help=f"backend model id; defaults: {DEFAULT_MODELS}")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="spelling/context hint for names")
    args = ap.parse_args()

    backend = pick_backend(args.backend)
    if backend is None:
        print("No transcription backend installed. Apple Silicon: .venv/bin/pip install mlx-whisper\n"
              "Tightest word timing (any platform): .venv/bin/pip install whisperx\n"
              "Lightweight (any platform): .venv/bin/pip install faster-whisper")
        return 1
    for f in args.files:
        transcribe_file(f, Path(args.out), backend, args.model, args.prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
