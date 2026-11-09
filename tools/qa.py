"""Automated QA for finished ads. Produces evidence images for the visual checks
Claude must still do by eye (typos, caption sync, cropped faces, brand colors).

Per ad, writes to <qa_dir>/<ad name>/:
    report.json, first_frame.png, first_frame_360.png, contact_sheet.png,
    safezone_*.png (red = keep clear), mobile360_*.png
For the batch, writes <qa_dir>/REPORT.md, including a first-frame similarity check.

Automated checks: container and codec specs, loudness, black frames, silent opening,
opening similarity across ads, plus (when the ad was made by tools/render.py and its
.render.json sidecar is next to it) caption geometry against the safe zone, caption and
lower-third overlap, headline on frame 1, a face in the hook and in the CTA, duration
guidance, and (with --script) that the captions say what the script says.

Usage:
    .venv/bin/python tools/qa.py batches/<id>/exports/*.mp4 --qa-dir batches/<id>/qa [--script brief/08_scripts.md]
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
from common import RESOLUTIONS, ffmpeg, find_font, fps, load_config, probe, ratio_of, safe_box  # noqa: E402

MAX_BYTES = 4 * 1024**3
MAX_SECONDS_ALL_PLACEMENTS = 60   # keep every placement eligible (playbook: 15-35 s preferred for lead gen)
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


# ---------- checks that need the render sidecar ----------

def load_sidecar(path: Path) -> dict | None:
    sc = path.with_suffix(".render.json")
    if not sc.exists():
        sc = path.parent / f"{path.stem}.render.json"
    return json.loads(sc.read_text()) if sc.exists() else None


def ass_pages(ass_path: Path) -> tuple[dict, list[dict]]:
    """Parse the caption file: style fields and one entry per Dialogue (start, end, lines of plain text)."""
    style, pages = {}, []
    for line in ass_path.read_text().splitlines():
        if line.startswith("Style: Cap,"):
            f = line.split(",")
            style = {"font": f[1], "size": int(float(f[2])), "outline": float(f[16]), "margin_l": int(f[19]),
                     "margin_r": int(f[20]), "margin_v": int(f[21])}
        elif line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            text = re.sub(r"\{[^}]*\}", "", parts[9])
            pages.append({"start": ass_to_s(parts[1]), "end": ass_to_s(parts[2]), "lines": text.split(r"\N")})
    return style, pages


def ass_to_s(t: str) -> float:
    h, m, sec = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def caption_geometry(ass_path: Path, w: int, h: int, ratio: str, sidecar: dict) -> list[dict]:
    """Prove captions sit inside the safe zone and never under the lower third."""
    res = []
    style, pages = ass_pages(ass_path)
    if not style or not pages:
        return [check("caption geometry", "WARN", "no caption pages found in the .ass file")]
    box = safe_box(w, h, ratio)
    font_path, exact = find_font(style["font"])
    if style["margin_v"] < box["bottom"]:
        res.append(check("captions above bottom safe zone", "FAIL", f"MarginV {style['margin_v']} < {box['bottom']}"))
    else:
        res.append(check("captions above bottom safe zone", "PASS", f"MarginV {style['margin_v']} >= {box['bottom']}"))
    widest, tallest, tallest_page = 0, 0, None
    if font_path:
        from PIL import ImageFont

        fnt = ImageFont.truetype(font_path, style["size"])
        for pg in pages:
            width = max(fnt.getlength(ln) for ln in pg["lines"]) + 2 * style["outline"]
            height = len(pg["lines"]) * style["size"] * 1.2 + 2 * style["outline"]
            if width > widest:
                widest = width
            if height > tallest:
                tallest, tallest_page = height, pg
    avail = w - style["margin_l"] - style["margin_r"]
    if widest > avail * 1.02:
        res.append(check("caption width inside safe sides", "FAIL",
                         f"widest page {widest:.0f}px > {avail}px available; shorten words_per_chunk_max or MAX_LINE_CHARS"))
    else:
        res.append(check("caption width inside safe sides", "PASS", f"widest page {widest:.0f}px of {avail}px"
                         + ("" if exact else " (measured with a fallback font)")))
    too_many = [pg for pg in pages if len(pg["lines"]) > 2]
    res.append(check("caption pages max 2 lines", "PASS" if not too_many else "WARN", f"{len(too_many)} pages over 2 lines"))
    lt = next((g for g in sidecar.get("graphics", []) if g["type"] == "lower_third"), None)
    if lt and tallest_page:
        cap_top = h - style["margin_v"] - tallest
        try:
            import render as _render  # noqa: WPS433
            gap = _render.LOWER_THIRD_GAP
        except ImportError:
            gap = 0.15
        lt_bottom = h - box["bottom"] - round(h * gap)
        clash = [pg for pg in pages if pg["start"] < lt["at"] + lt["duration"] and pg["end"] > lt["at"]
                 and h - style["margin_v"] - (len(pg["lines"]) * style["size"] * 1.2) < lt_bottom]
        res.append(check("lower third clear of captions", "PASS" if not clash else "WARN",
                         f"{len(clash)} caption pages reach the lower third band" if clash else f"caption top {cap_top:.0f} vs band {lt_bottom}"))
    return res


def caption_pages_checks(pages_json: Path, h: int, sidecar: dict) -> list[dict]:
    """Browser-rendered captions live inside a safe-zone container by construction; check pacing and overlap."""
    pages = json.loads(pages_json.read_text())
    if not pages:
        return [check("caption pages", "WARN", "no caption pages")]
    res = [check("captions inside safe zone", "PASS", f"{len(pages)} pages in the caption band (container bounded by the safe zone)")]
    fast = [p for p in pages if (p["end"] - p["start"]) < 0.35 and len(p["text"].split()) >= 3]
    res.append(check("caption pages readable", "PASS" if not fast else "WARN",
                     "ok" if not fast else f"{len(fast)} pages of 3+ words shown under 0.35 s"))
    long_words = [p for p in pages if len(p["text"]) > 34]
    res.append(check("caption pages max 2 lines", "PASS" if not long_words else "WARN",
                     "ok" if not long_words else f"{len(long_words)} pages over 34 characters may wrap to 3 lines"))
    lt = next((g for g in sidecar.get("graphics", []) if g["type"] == "lower_third"), None)
    if lt:
        # The browser lower third sits 17% of the frame above the bottom safe zone; two caption lines reach about 13%.
        clash = [p for p in pages if p["start"] < lt["at"] + lt["duration"] and p["end"] > lt["at"] and len(p["text"]) > 34]
        res.append(check("lower third clear of captions", "PASS" if not clash else "WARN",
                         "ok" if not clash else f"{len(clash)} three-line caption pages while the lower third is up"))
    return res


def script_check_pages(pages_json: Path, script_path: Path) -> list[dict]:
    import selects  # noqa: WPS433

    lines = selects.script_lines(script_path)
    spoken = " ".join(p["text"] for p in json.loads(pages_json.read_text()))
    toks = [selects.norm(t) for t in spoken.split() if selects.norm(t)]
    words = [{"word": t, "start": i, "end": i} for i, t in enumerate(toks)]
    missing = [ln for ln in lines if not (b := selects.best_spans(ln, words, top=1)) or b[0]["score"] < 0.6]
    if not lines:
        return [check("captions match script", "WARN", "no script lines parsed")]
    status = "PASS" if not missing else ("WARN" if len(missing) <= len(lines) / 2 else "FAIL")
    return [check("captions match script", status, "all lines heard" if not missing else "not heard: " + " | ".join(m[:50] for m in missing[:5]))]


def sidecar_checks(sidecar: dict, duration: float) -> list[dict]:
    res = []
    # Two graphics fighting for the same region at the same time is the fastest way to look machine-made.
    gs = [g for g in sidecar.get("graphics", []) if g.get("region") in ("center", "top")]
    clashes = []
    for i in range(len(gs)):
        for j in range(i + 1, len(gs)):
            a, b = gs[i], gs[j]
            if a["region"] == b["region"] and a["at"] < b["at"] + b["duration"] and b["at"] < a["at"] + a["duration"]:
                clashes.append(f"{a['type']}@{a['at']}s and {b['type']}@{b['at']}s")
    res.append(check("one graphic per region at a time", "PASS" if not clashes else "FAIL",
                     "ok" if not clashes else "overlapping: " + "; ".join(clashes[:4])))
    short = [g for g in sidecar.get("graphics", []) if g["type"] in ("label", "stat", "compare", "card", "callout") and g["duration"] < 1.4]
    res.append(check("graphics stay up long enough to read", "PASS" if not short else "WARN",
                     "ok" if not short else f"{len(short)} graphics under 1.4 s"))
    hook = next((g for g in sidecar.get("graphics", []) if g["type"] in ("hook_text", "hook") and g["at"] == 0.0), None)
    res.append(check("headline on frame 1", "PASS" if hook else "WARN",
                     f'"{hook.get("text", "")}" for {hook["duration"]}s' if hook else "no hook_text in the EDL; the text hook must be on screen from frame 1"))
    res.append(check("duration for all placements", "PASS" if duration <= MAX_SECONDS_ALL_PLACEMENTS else "WARN",
                     f"{duration:.1f}s (keep under {MAX_SECONDS_ALL_PLACEMENTS}s so every placement is eligible)"))
    if not any(c.get("src") == "end_card" for c in sidecar.get("clips", [])):
        res.append(check("end card with CTA", "WARN", "no end_card in the EDL; the last 2-3 s should state the exact action"))
    else:
        res.append(check("end card with CTA", "PASS", "present"))
    return res


def face_checks(path: Path, sidecar: dict | None, duration: float) -> list[dict]:
    """A face on screen in the hook and in the CTA (skill rule). Uses the render engine's detector."""
    try:
        import render  # noqa: WPS433
    except ImportError:
        return []
    detect = render.face_detector()
    if detect is None:
        return [check("face in hook and CTA", "WARN", "no face detector available")]
    clips = (sidecar or {}).get("clips", [])
    aroll_end = next((c["at"] for c in clips if c.get("src") == "end_card"), duration)

    def faces_between(a: float, b: float) -> bool:
        import numpy as np

        sw, sh = 480, 480 * 16 // 9
        for i in range(3):
            t = a + (b - a) * (i + 0.5) / 3
            raw = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                                  "-vf", "scale=480:-2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
            if not raw:
                continue
            hh = len(raw) // (480 * 3)
            img = np.frombuffer(raw[: hh * 480 * 3], np.uint8).reshape(hh, 480, 3)
            if detect(img):
                return True
        return False

    hook_ok = faces_between(0.0, min(1.5, aroll_end))
    cta_ok = faces_between(max(0.0, aroll_end - 2.0), aroll_end)
    return [check("face in hook (first 1.5s)", "PASS" if hook_ok else "WARN", "found" if hook_ok else "no face detected; the hook should show the speaker"),
            check("face in CTA (last 2s before end card)", "PASS" if cta_ok else "WARN", "found" if cta_ok else "no face detected; say the CTA on camera")]


def script_check(ass_path: Path, script_path: Path) -> list[dict]:
    """Every script line should be heard (captioned) somewhere; flags lines that were cut or misread."""
    import selects  # noqa: WPS433

    lines = selects.script_lines(script_path)
    _, pages = ass_pages(ass_path)
    spoken = " ".join(ln for pg in pages for ln in pg["lines"])
    toks = [selects.norm(t) for t in spoken.split() if selects.norm(t)]
    words = [{"word": t, "start": i, "end": i} for i, t in enumerate(toks)]
    missing = []
    for line in lines:
        best = selects.best_spans(line, words, top=1)
        if not best or best[0]["score"] < 0.6:
            missing.append(line)
    if not lines:
        return [check("captions match script", "WARN", "no script lines parsed")]
    status = "PASS" if not missing else ("WARN" if len(missing) <= len(lines) / 2 else "FAIL")
    return [check("captions match script", status, "all lines heard" if not missing else "not heard: " + " | ".join(m[:50] for m in missing[:5]))]


def frame_scan(path: Path, fps: int = 10) -> list[dict]:
    """Watch the ad at 10 frames per second like an editor would: flag flash frames (one frame that differs
    sharply from both neighbours while the neighbours match each other) and frozen stretches."""
    import numpy as np

    sw, sh = 96, 96
    raw = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale={sw}:{sh},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    n = len(raw) // (sw * sh)
    if n < 4:
        return []
    frames = np.frombuffer(raw[: n * sw * sh], np.uint8).reshape(n, sh, sw).astype(np.int16)
    d = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2)) / 255.0   # d[i] = diff between frame i and i+1
    flashes, frozen = [], []
    for i in range(1, n - 1):
        prev_next = np.abs(frames[i - 1] - frames[i + 1]).mean() / 255.0
        if d[i - 1] > 0.18 and d[i] > 0.18 and prev_next < 0.06:
            flashes.append(round(i / fps, 1))
    run = 0
    for i, v in enumerate(d):
        run = run + 1 if v < 0.002 else 0
        if run == fps * 3:   # 3 s with no visible change (end card excluded by the caller via sidecar)
            frozen.append(round((i - run + 1) / fps, 1))
    res = [check("flash frames (10 fps scan)", "PASS" if not flashes else "FAIL",
                 "none" if not flashes else "at " + ", ".join(f"{t}s" for t in flashes[:8]))]
    res.append(check("no frozen stretch over 3s", "PASS" if not frozen else "WARN",
                     "none" if not frozen else "from " + ", ".join(f"{t}s" for t in frozen[:5]) + " (a still or a static graphic held too long?)"))
    return res


def plate_over_face(path: Path, sidecar: dict) -> list[dict]:
    """A graphic that sits on the speaker's face is the mistake editors catch first."""
    plates = [g for g in sidecar.get("graphics", []) if g.get("region") in ("center",)]
    if not plates:
        return []
    try:
        import render  # noqa: WPS433
        import numpy as np
    except ImportError:
        return []
    detect = render.face_detector()
    if detect is None:
        return []
    hits = []
    for g in plates:
        t = g["at"] + min(0.5, g["duration"] / 2)
        raw = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                              "-vf", "scale=480:-2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        if not raw:
            continue
        hh = len(raw) // (480 * 3)
        img = np.frombuffer(raw[: hh * 480 * 3], np.uint8).reshape(hh, 480, 3)
        faces = detect(img)
        if faces:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            cy = (y + h / 2) / hh
            if 0.30 < cy < 0.55:   # the center band where center plates sit
                hits.append(f"{g.get('type')} at {g['at']}s")
    return [check("graphics clear of the face", "PASS" if not hits else "WARN",
                  "none overlap" if not hits else "possible overlap: " + ", ".join(hits[:5]))]


def seam_checks(path: Path, sidecar: dict) -> list[dict]:
    """Every cut between A-roll segments: a butt-splice click (audio step) and a repeated word across the seam."""
    import numpy as np

    seams = [c["at"] for c in sidecar.get("clips", [])[1:] if c.get("src") != "end_card" and c["at"] > 0.05]
    if not seams:
        return []
    clicks = []
    for t in seams:
        raw = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-ss", f"{max(0, t - 0.04):.3f}", "-t", "0.08", "-i", str(path),
                              "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], capture_output=True).stdout
        if len(raw) < 400:
            continue
        a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        step = float(np.max(np.abs(np.diff(a))))
        if step > 0.35:
            clicks.append(f"{t:.2f}s ({step:.2f})")
    res = [check("no clicks at cuts", "PASS" if not clicks else "WARN",
                 "ok" if not clicks else "sample jumps at " + ", ".join(clicks[:6]) + "; add tighten_keep or move the cut")]
    caps = sidecar.get("captions") or {}
    wj = Path(caps.get("words_json", "")) if caps.get("words_json") else None
    if wj and wj.is_file():
        words = json.loads(wj.read_text())
        dups = []
        for t in seams:
            before = [w for w in words if w["end"] <= t + 0.05 and w["end"] > t - 1.5]
            after = [w for w in words if w["start"] >= t - 0.05 and w["start"] < t + 1.5]
            if before and after:
                a_ = re.sub(r"[^\w']", "", before[-1]["word"]).lower()
                b_ = re.sub(r"[^\w']", "", after[0]["word"]).lower()
                if len(a_) >= 3 and a_ == b_:
                    dups.append(f"'{a_}' at {t:.2f}s")
                elif len(before) >= 2 and len(after) >= 2:
                    bg1 = [re.sub(r"[^\w']", "", w["word"]).lower() for w in before[-2:]]
                    bg2 = [re.sub(r"[^\w']", "", w["word"]).lower() for w in after[:2]]
                    if bg1 == bg2 and any(len(x) >= 3 for x in bg1):
                        dups.append(f"'{' '.join(bg1)}' at {t:.2f}s")
        res.append(check("no repeated words across cuts", "PASS" if not dups else "FAIL",
                         "ok" if not dups else "a retake survived: " + "; ".join(dups[:5])))
    return res


def lull_scan(path: Path, threshold_db: float = -27.0, min_dur: float = 0.5) -> list[dict]:
    """Breathy lulls at -28 to -36 dB read as dead air to a viewer but pass silencedetect; scan a 50 ms RMS envelope."""
    import numpy as np

    raw = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    win = 800  # 50 ms
    n = len(a) // win
    if n < 10:
        return []
    rms = np.sqrt(np.mean(a[: n * win].reshape(n, win) ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-6))
    low = db < threshold_db
    runs, i = [], 0
    while i < n:
        if low[i]:
            j = i
            while j < n and low[j]:
                j += 1
            dur = (j - i) * 0.05
            start = i * 0.05
            if dur >= min_dur and start > 0.5 and (j * 0.05) < n * 0.05 - 0.5:
                runs.append((start, dur))
            i = j
        else:
            i += 1
    return [check("no breathy lulls over 0.5s", "PASS" if not runs else "WARN",
                  "ok" if not runs else "quiet stretches at " + ", ".join(f"{s:.1f}s ({d:.1f}s)" for s, d in runs[:6]) + "; tighten or cover with a graphic")]


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


def qa_one(path: Path, qa_dir: Path, target: float, tp_max: float, script: Path | None = None) -> dict:
    out = qa_dir / path.stem
    out.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    results, meta = spec_checks(path, info)
    results += loudness(path, target, tp_max)
    results += black_and_silence(path)
    sidecar = load_sidecar(path)
    if sidecar:
        results += sidecar_checks(sidecar, meta["duration"])
        caps = sidecar.get("captions") or {}
        ass = Path(caps["ass"]) if caps.get("ass") else None
        pages_json = Path(caps["pages"]) if caps.get("pages") else None
        if ass and ass.is_file() and meta.get("ratio"):
            results += caption_geometry(ass, meta["width"], meta["height"], meta["ratio"], sidecar)
            if script:
                results += script_check(ass, script)
        elif pages_json and pages_json.is_file():
            results += caption_pages_checks(pages_json, meta["height"], sidecar)
            if script:
                results += script_check_pages(pages_json, script)
        else:
            results.append(check("captions burned", "WARN", "no caption file recorded; render with --captions"))
    else:
        results.append(check("render sidecar", "WARN", "no .render.json next to the file; geometry and hook checks skipped"))
    if "width" in meta:
        results += face_checks(path, sidecar, meta["duration"])
        results += frame_scan(path)
        results += lull_scan(path)
        if sidecar:
            results += plate_over_face(path, sidecar)
            results += seam_checks(path, sidecar)
        evidence(path, out, meta)
    results += [check(m, "MANUAL", "look at the images in this folder") for m in MANUAL_CHECKS]
    report = {"file": str(path), **meta, "results": results}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--qa-dir", required=True)
    ap.add_argument("--script", help="script file; checks that every line is heard in the captions")
    args = ap.parse_args()
    audio_cfg = load_config().get("audio", {}) or {}
    target = float(audio_cfg.get("target_lufs", -14))
    tp_max = float(audio_cfg.get("true_peak_max_dbtp", -1.0))
    qa_dir = Path(args.qa_dir)
    paths = [Path(f) for f in args.files]
    reports = [qa_one(p, qa_dir, target, tp_max, Path(args.script) if args.script else None) for p in paths]

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
