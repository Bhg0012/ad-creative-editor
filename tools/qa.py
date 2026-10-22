"""Automated QA for finished ads. Produces evidence images for the visual checks
Claude must still do by eye (typos, caption sync, cropped faces, brand colors).

Per ad, writes to <qa_dir>/<ad name>/:
    report.json, first_frame.png, first_frame_360.png, contact_sheet.png,
    safezone_*.png (red = keep clear), mobile360_*.png
For the batch, writes <qa_dir>/REPORT.md, including a first-frame similarity check.

Usage:
    .venv/bin/python tools/qa.py batches/<id>/exports/*.mp4 --qa-dir batches/<id>/qa
Exit code 1 if any automated check FAILS.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESOLUTIONS, ffmpeg, fps, load_config, probe, ratio_of, safe_box  # noqa: E402

MAX_BYTES = 4 * 1024**3
SIMILAR_FIRST_FRAME = 0.06  # mean abs pixel difference (0-1) below which two openings look alike

MANUAL_CHECKS = [
    "Contact sheet: no black frames, flashes, cropped faces, leftover timecode or watermarks",
    "Safe-zone frames: every caption, headline, logo and CTA sits outside the red areas",
    "First frame works as a still: clear subject, readable hook text, would stop a scroll",
    "Caption text matches the transcript word for word; no typos; sync within ~2 frames",
    "Brand colors correct (#3B96F6 / #E55B13); text readable in mobile360 frames",
    "Compliance checklist (skill reference/compliance.md) passed line by line",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def check(name: str, status: str, detail: str) -> dict:
    return {"check": name, "status": status, "detail": detail}


def spec_checks(path: Path, info: dict) -> tuple[list[dict], dict]:
    res = []
    streams = info["streams"]
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    fmt = info["format"]
    duration = float(fmt.get("duration", 0))
    meta = {"duration": duration}
    if v is None:
        return [check("video stream", "FAIL", "no video stream")], meta
    w, h = int(v["width"]), int(v["height"])
    ratio = ratio_of(w, h)
    meta.update(width=w, height=h, ratio=ratio)
    res.append(check("container", "PASS" if any(x in fmt["format_name"] for x in ("mp4", "mov")) else "FAIL", fmt["format_name"]))
    res.append(check("video codec", "PASS" if v["codec_name"] == "h264" else "FAIL", v["codec_name"]))
    res.append(check("pixel format", "PASS" if v.get("pix_fmt") == "yuv420p" else "FAIL", v.get("pix_fmt", "?")))
    if ratio is None:
        res.append(check("aspect ratio", "FAIL", f"{w}x{h} is not 9:16, 4:5 or 1:1"))
    else:
        ok = (w, h) in RESOLUTIONS[ratio]
        res.append(check("resolution", "PASS" if ok else "FAIL",
                         f"{w}x{h} ({ratio}); accepted {RESOLUTIONS[ratio]}"))
    sar = v.get("sample_aspect_ratio", "1:1")
    res.append(check("square pixels", "PASS" if sar in ("1:1", "0:1") else "FAIL", f"SAR {sar}"))
    r, avg = fps(v.get("r_frame_rate", "0/1")), fps(v.get("avg_frame_rate", "0/1"))
    res.append(check("constant frame rate", "PASS" if abs(r - avg) < 0.05 else "FAIL", f"r={r:.3f} avg={avg:.3f}"))
    if a is None:
        res.append(check("audio stream", "FAIL", "no audio (Meta strongly recommends sound)"))
    else:
        res.append(check("audio codec", "PASS" if a["codec_name"] == "aac" else "FAIL", a["codec_name"]))
        res.append(check("audio channels", "PASS" if a.get("channels") == 2 else "FAIL", f"{a.get('channels')} ch"))
        sr = int(a.get("sample_rate", 0))
        res.append(check("audio sample rate", "PASS" if sr in (44100, 48000) else "WARN", f"{sr} Hz"))
        br = a.get("bit_rate")
        if br:
            res.append(check("audio bitrate", "PASS" if int(br) >= 127000 else "FAIL", f"{int(br)//1000} kbps (min 128)"))
        else:
            res.append(check("audio bitrate", "WARN", "not reported; encode with -b:a 192k"))
    size = path.stat().st_size
    res.append(check("file size", "PASS" if size < MAX_BYTES else "FAIL", f"{size/1e6:.1f} MB"))
    m = re.search(r"_(\d+)s_", path.name)
    if m:
        target = int(m.group(1))
        res.append(check("length vs name", "PASS" if abs(duration - target) <= 1.0 else "WARN",
                         f"{duration:.2f}s vs {target}s in filename"))
    else:
        res.append(check("naming convention", "WARN", "name lacks _<length>s_; see naming convention"))
    return res, meta


def loudness(path: Path, target: float, tp_max: float) -> list[dict]:
    err = run([ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a:0?", "-af", "ebur128=peak=true",
               "-f", "null", "-"]).stderr
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    i_match = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    tp_match = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    if not i_match or not tp_match:
        return [check("loudness", "FAIL", "could not measure (no audio?)")]
    integrated = float(i_match.group(1))
    tp = float(tp_match.group(1))
    return [
        check("integrated loudness", "PASS" if abs(integrated - target) <= 1.0 else "FAIL",
              f"{integrated:.1f} LUFS (target {target} +/-1)"),
        check("true peak", "PASS" if tp <= tp_max else "FAIL", f"{tp:.1f} dBTP (max {tp_max})"),
    ]


def black_and_silence(path: Path) -> list[dict]:
    res = []
    err = run([ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path), "-vf", "blackdetect=d=0.1:pix_th=0.10",
               "-an", "-f", "null", "-"]).stderr
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)
    if blacks:
        spans = ", ".join(f"{float(s):.2f}-{float(e):.2f}s" for s, e in blacks)
        status = "FAIL" if any(float(s) < 0.05 for s, _ in blacks) else "WARN"
        res.append(check("black frames", status, spans))
    else:
        res.append(check("black frames", "PASS", "none"))
    err = run([ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a:0?",
               "-af", "silencedetect=n=-45dB:d=0.5", "-f", "null", "-"]).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    res.append(check("sound in first 0.5s", "WARN" if any(s <= 0.05 for s in starts) else "PASS",
                     "opens silent; hook should be heard immediately" if any(s <= 0.05 for s in starts) else "ok"))
    return res


def evidence(path: Path, out: Path, meta: dict) -> None:
    ff = ffmpeg()
    w, h, dur, ratio = meta["width"], meta["height"], meta["duration"], meta.get("ratio")
    run([ff, "-nostdin", "-y", "-v", "error", "-i", str(path), "-frames:v", "1", str(out / "first_frame.png")])
    run([ff, "-nostdin", "-y", "-v", "error", "-i", str(path), "-frames:v", "1", "-vf", "scale=360:-2",
         str(out / "first_frame_360.png")])
    rows = max(1, math.ceil(dur / 6))
    run([ff, "-nostdin", "-y", "-v", "error", "-i", str(path), "-vf",
         f"fps=1,scale=270:-2,tile=6x{rows}:padding=4:color=white", "-frames:v", "1", str(out / "contact_sheet.png")])
    if not ratio:
        return
    box = safe_box(w, h, ratio)
    zones = (f"drawbox=x=0:y=0:w=iw:h={box['top']}:color=red@0.35:t=fill,"
             f"drawbox=x=0:y=ih-{box['bottom']}:w=iw:h={box['bottom']}:color=red@0.35:t=fill,"
             f"drawbox=x=0:y=0:w={box['side']}:h=ih:color=red@0.35:t=fill,"
             f"drawbox=x=iw-{box['side']}:y=0:w={box['side']}:h=ih:color=red@0.35:t=fill")
    for label, t in [("00_start", 0.0), ("25pct", dur * 0.25), ("50pct", dur * 0.5),
                     ("75pct", dur * 0.75), ("99_end", max(0.0, dur - 0.5))]:
        run([ff, "-nostdin", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
             "-vf", zones, str(out / f"safezone_{label}.png")])
        run([ff, "-nostdin", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
             "-vf", "scale=360:-2", str(out / f"mobile360_{label}.png")])


def first_frame_signature(path: Path) -> bytes:
    return subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(path), "-frames:v", "1",
                           "-vf", "scale=32:32,format=gray", "-f", "rawvideo", "-"],
                          capture_output=True).stdout


def similarity_checks(paths: list[Path]) -> list[str]:
    sigs = {p.name: first_frame_signature(p) for p in paths}
    names = list(sigs)
    lines = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = sigs[names[i]], sigs[names[j]]
            if len(a) != 1024 or len(b) != 1024:
                continue
            diff = sum(abs(x - y) for x, y in zip(a, b)) / (1024 * 255)
            if diff < SIMILAR_FIRST_FRAME:
                lines.append(f"- WARN: `{names[i]}` and `{names[j]}` open on near-identical frames "
                             f"(diff {diff:.3f}). Fine for an aspect-ratio pair of one concept; "
                             "not fine for two different concepts.")
    return lines


def qa_one(path: Path, qa_dir: Path, target: float, tp_max: float) -> dict:
    out = qa_dir / path.stem
    out.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    results, meta = spec_checks(path, info)
    results += loudness(path, target, tp_max)
    results += black_and_silence(path)
    if "width" in meta:
        evidence(path, out, meta)
    results += [check(m, "MANUAL", "look at the images in this folder") for m in MANUAL_CHECKS]
    report = {"file": str(path), **meta, "results": results}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--qa-dir", required=True)
    args = ap.parse_args()
    audio_cfg = load_config().get("audio", {}) or {}
    target = float(audio_cfg.get("target_lufs", -14))
    tp_max = float(audio_cfg.get("true_peak_max_dbtp", -1.0))
    qa_dir = Path(args.qa_dir)
    paths = [Path(f) for f in args.files]
    reports = [qa_one(p, qa_dir, target, tp_max) for p in paths]

    md = ["# QA report", "", "Automated checks below. MANUAL rows must be checked by eye in each ad's folder "
          "and marked in this file before delivery.", ""]
    any_fail = False
    for r in reports:
        md += [f"## {Path(r['file']).name}", "", "| check | status | detail |", "|---|---|---|"]
        for c in r["results"]:
            any_fail |= c["status"] == "FAIL"
            md.append(f"| {c['check']} | {c['status']} | {c['detail']} |")
        md.append("")
    sim = similarity_checks(paths) if len(paths) > 1 else []
    md += ["## Opening diversity", ""] + (sim or ["- PASS: no two ads open on near-identical frames."]) + [""]
    (qa_dir / "REPORT.md").write_text("\n".join(md))
    fails = sum(c["status"] == "FAIL" for r in reports for c in r["results"])
    print(f"QA: {len(reports)} ads, {fails} automated FAIL(s). Report: {qa_dir / 'REPORT.md'}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
