"""Measure a reference ad so its style can be copied as numbers, not vibes.

For a video in brand/references/ this writes <name>.analysis.md next to it with: duration,
hard cuts and shot lengths (hook vs body vs CTA), visual change events per second (the pace
a viewer feels, which counts caption pops and graphics, not just cuts), loudness, whether a
music bed is present, and contact sheets plus full-size frames for the eye pass.

Usage:
    .venv/bin/python tools/reference.py brand/references/ad1.mp4
    .venv/bin/python tools/reference.py brand/references/*.mp4 --frames 8
Then view the sheets, fill in the "what it does / adopt" sections, and fold the result into brand/DESIGN.md.
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg, probe, run_ffmpeg, video_stream  # noqa: E402


def cuts(path: Path, threshold: float = 0.3) -> list[float]:
    res = run_ffmpeg(["-v", "info", "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"], check=False)
    return [float(x) for x in re.findall(r"pts_time:\s*([\d.]+)", res.stderr)]


def change_events(path: Path, fps: int = 10, thresh: float = 0.06) -> list[float]:
    import numpy as np

    raw = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale=64:64,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    n = len(raw) // 4096
    if n < 3:
        return []
    f = np.frombuffer(raw[: n * 4096], np.uint8).reshape(n, 64, 64).astype(np.int16)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2)) / 255
    return [round(i / fps, 1) for i, v in enumerate(d) if v > thresh]


def loudness(path: Path) -> dict:
    res = run_ffmpeg(["-v", "info", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], check=False)
    err = res.stderr
    out = {}
    for key, pat in (("lufs", r"I:\s+(-?[\d.]+) LUFS"), ("lra", r"LRA:\s+([\d.]+) LU"), ("tp", r"Peak:\s+(-?[\d.]+) dBFS")):
        m = re.findall(pat, err)
        out[key] = float(m[-1]) if m else None
    sil = run_ffmpeg(["-v", "info", "-i", str(path), "-af", "silencedetect=n=-30dB:d=0.15", "-f", "null", "-"], check=False).stderr
    out["gaps_below_minus30"] = len(re.findall(r"silence_start", sil))
    return out


def analyze(path: Path, frames: int, out_dir: Path | None) -> Path:
    info = probe(path)
    v = video_stream(info)
    dur = float(info["format"]["duration"])
    w, h = int(v["width"]), int(v["height"])
    out_dir = out_dir or path.parent / f"{path.stem}_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    cut_times = cuts(path)
    shots = [b - a for a, b in zip([0.0] + cut_times, cut_times + [dur])]
    events = change_events(path)
    loud = loudness(path)
    # contact sheet at 1 fps with timecodes, plus evenly spaced full-size frames
    cols = 8
    rows = max(1, -(-int(dur) // cols))
    run_ffmpeg(["-i", str(path), "-vf", f"fps=1,scale=240:-2,drawtext=text='%{{pts\\:hms}}':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5:x=4:y=4,"
                f"tile={cols}x{rows}:padding=3:color=0x202020", "-frames:v", "1", str(out_dir / "sheet.png")])
    for i in range(frames):
        t = dur * (i + 0.5) / frames
        run_ffmpeg(["-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", str(out_dir / f"frame_{t:05.1f}s.png")])

    def sec(a: float, b: float) -> list[float]:
        return [t for t in events if a <= t < b]

    hook, body, cta = sec(0, min(3, dur)), sec(3, dur * 0.85), sec(dur * 0.85, dur)
    md = [f"# Reference analysis: {path.name}", "",
          f"Duration {dur:.1f} s, {w}x{h}, {len(cut_times)} hard cuts (median shot {statistics.median(shots):.2f} s, "
          f"shortest {min(shots):.2f}, longest {max(shots):.2f}).", "",
          f"Visual change events (10 fps, >6% frame change, counts graphics and caption pops): {len(events)} total, "
          f"{len(events) / max(dur, 1):.2f} per second. Hook (0-3 s): {len(hook) / max(min(3, dur), 1):.2f}/s. "
          f"Body: {len(body) / max(dur * 0.85 - 3, 1):.2f}/s. CTA (last 15%): {len(cta) / max(dur * 0.15, 1):.2f}/s.", "",
          f"Loudness {loud['lufs']} LUFS integrated, range {loud['lra']} LU, true peak {loud['tp']} dBTP. "
          f"Gaps below -30 dB: {loud['gaps_below_minus30']} ({'voice only, no music bed' if loud['gaps_below_minus30'] > 3 else 'a continuous bed is likely'}).", "",
          "Cuts at: " + ", ".join(f"{t:.1f}" for t in cut_times[:40]) + ("..." if len(cut_times) > 40 else ""), "",
          f"Evidence: `{out_dir.name}/sheet.png` (1 frame per second) and `frame_*.png`. View them and fill in:", "",
          "## What it does", "", "- Layout (where the speaker sits, where graphics live):", "- Captions (case, words per page, highlight, position):",
          "- Graphics vocabulary (what appears, on what kind of word, how long):", "- Hook (first frame, first line):",
          "- CTA (how the ending asks):", "- Sound (bed, hits, voice treatment):", "",
          "## Adopt / do not adopt", "", "- ", ""]
    out_md = path.parent / f"{path.stem}.analysis.md"
    out_md.write_text("\n".join(md))
    return out_md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--frames", type=int, default=6, help="full-size frames to extract, evenly spaced")
    args = ap.parse_args()
    for v in args.videos:
        print(analyze(Path(v), args.frames, None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
