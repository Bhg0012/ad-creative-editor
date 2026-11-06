"""Assemble a finished ad from an edit decision list (EDL) with ffmpeg.

The EDL is a small YAML file Claude writes per ad (see `edl_example()` or
`--example`). render.py turns it into:
    work/cuts/<name>_master.mp4   graded, mixed, loudness-normalized, no captions
    exports/<name>.mp4            final with burned-in captions (if a words.json is given)
    exports/<name>.render.json    timeline sidecar: every clip, overlay, graphic, and text

Pipeline (each step is a plain ffmpeg call so failures are easy to read):
    1. Each A-roll clip becomes a normalized segment: trim, reframe to the target
       ratio around a focus point (face-detected when `focus: auto`), optional
       punch-in or slow push, constant frame rate, SDR, 48 kHz stereo. Clips with
       `tighten` get their internal silences shortened (gaps, never words).
    2. Segments and the end card are concatenated.
    3. One composite pass adds B-roll overlays, the headline hook text, lower
       third, voice processing, ducked music, and SFX.
    4. Two-pass loudnorm to config `audio.target_lufs`, then captions are burned
       with the final encode settings.

Usage:
    .venv/bin/python tools/render.py --example > work/edl/my_ad.yaml
    .venv/bin/python tools/render.py work/edl/my_ad.yaml --proxy          # rough cut, 540 px, timecode
    .venv/bin/python tools/render.py work/edl/my_ad.yaml                  # master, then prints next step
    .venv/bin/python tools/render.py work/edl/my_ad.yaml --captions work/transcripts/my_ad_master.words.json
    .venv/bin/python tools/render.py work/edl/my_ad.yaml --captions auto  # transcribes the master itself
    .venv/bin/python tools/render.py work/edl/my_ad.yaml --ratio 4:5      # same cut reframed for Feed
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ROOT, RESOLUTIONS, SAFE_ZONES, audio_stream, display_size, even, ffmpeg,  # noqa: E402
                    find_font, fps as parse_fps, is_hdr, load_config, load_yaml, probe, run_ffmpeg,
                    safe_box, video_stream)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
RATIO_TOKEN = {"9:16": "9x16", "4:5": "4x5", "1:1": "1x1"}

ENC_INTER = ["-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p"]
ENC_FINAL = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p"]
ENC_PROXY = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p"]
AUD_ENC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
AUD_NORM = "aresample=48000:async=1,aformat=sample_fmts=fltp:channel_layouts=stereo"
HDR_TO_SDR = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
              "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")

CUT_FADE = 0.03  # seconds of audio fade at each cut boundary

DEFAULTS = {
    "hook_text_seconds": 3.0,
    "end_card_seconds": 2.5,
    "music_gain_db": -18.0,
    "music_fade_out": 1.0,
    "duck": True,
    "tighten_keep": 0.12,      # silence left on each side of a tightened gap, seconds
    "voice_highpass_hz": 80,
    "voice_denoise": False,
}


def edl_example() -> str:
    return """# Edit decision list for one ad. Paths are relative to the repo root.
name: HSV_reviews_lostjobs_question_30s_9x16_v1
ratio: "9:16"                 # 9:16 Reels/Stories, 4:5 Feed. Override with --ratio.
hook_text: "Huntsville roofers: 9 reviews?"   # on screen from frame 1, max ~7 words
hook_text_seconds: 3
clips:                        # A-roll in timeline order; in/out are seconds in the source
  - {src: raw/take3.mov, in: 12.40, out: 15.90, zoom: 1.0, focus: auto, slot: hook}   # slot: a name variants can swap
  - {src: raw/take3.mov, in: 21.10, out: 26.75, zoom: 1.10, tighten: 0.45}
  - {src: raw/take5.mov, in: 3.00, out: 8.20, push: 1.08}   # slow push from 1.0 to 1.08
  - {src: raw/screenshot.png, duration: 2.5, push: 1.12}    # still image, Ken Burns push
broll:                        # picture-only overlays on the timeline; the voice continues
  - {src: raw/phone_text.mov, at: 6.0, duration: 2.5, src_in: 0.0, label: "A text goes out"}
  - {src: raw/screen_recording.mov, at: 9.0, duration: 4.0, speaker_inset: {w: 0.40, x: 0.76, y: 0.70}}  # screen full frame, speaker in a corner inset
  - {src: raw/review_screenshot.heic, at: 14.0, duration: 2.0, pip: {w: 0.72, x: 0.5, y: 0.40}}  # picture-in-picture
callouts:                     # short on-screen text mid-video: a number, a re-hook, a label (rendered as animated cards)
  - {text: "$4,800 roof job (example)", at: 9.0, duration: 2.0, position: center, accent: true}
plates:                       # richer motion graphics (tools/plates.py): stat, compare, card, label, pip
  - {type: compare, title: "Same work. Different phone.", left: {label: You, value: 9}, right: {label: "The other guy", value: 140}, note: "Google reviews (example)", at: 4.0, duration: 3.0}
  - {type: stat, value: 140, suffix: " reviews", label: "your competitor (example)", at: 12.0, duration: 2.5}
  - {type: card, title: "You get", items: ["Review requests sent for you", "Replies written for you", "Monthly report by text"], at: 18.0, duration: 3.5}
lower_third: {text: "Bruce, Auburn AL", at: 1.0, duration: 3.0}
look: {contrast: 1.04, saturation: 1.08, sharpen: true}   # optional light grade on A-roll only
music: {src: audio/music/track.mp3, gain_db: -18, duck: true, fade_out: 1.0}
sfx:
  - {src: audio/sfx/whoosh.wav, at: 6.0, gain_db: -12}
end_card: {headline: "More reviews. More calls.", text: "Tap Learn More", subtext: "Huntsville contractors", seconds: 2.5, logo: true}
"""


# ---------- EDL ----------

def batch_dir_of(path: Path) -> Path:
    """The enclosing batch folder (has BATCH.md), else the file's own folder."""
    d = path.resolve().parent
    while d != d.parent:
        if (d / "BATCH.md").exists():
            return d
        d = d.parent
    return path.resolve().parent


def resolve(path: str, edl_dir: Path) -> Path:
    """Relative paths are tried against the repo root, the batch folder, the EDL folder, then cwd."""
    p = Path(path).expanduser()
    for base in (ROOT, batch_dir_of(edl_dir / "x"), edl_dir, Path.cwd()):
        cand = p if p.is_absolute() else base / p
        if cand.exists():
            return cand
    raise SystemExit(f"EDL references a file that does not exist: {path}")


def heic_to_png(src: Path, cache: Path) -> Path:
    """iPhone photos arrive as HEIC, which this ffmpeg cannot read. Convert once (pillow-heif, or sips on macOS)."""
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{src.stem}.png"
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    try:
        import pillow_heif
        from PIL import Image

        pillow_heif.register_heif_opener()
        img = Image.open(src)
        img = img.convert("RGB")
        from PIL import ImageOps
        ImageOps.exif_transpose(img).save(out)
        return out
    except ImportError:
        pass
    import shutil as _sh
    if _sh.which("sips"):
        subprocess.run(["sips", "-s", "format", "png", str(src), "--out", str(out)], check=True, capture_output=True)
        return out
    raise SystemExit(f"{src}: HEIC needs pillow-heif (.venv/bin/pip install pillow-heif) or macOS sips.")


def load_edl(path: Path, ratio_override: str | None = None) -> dict:
    edl = load_yaml(path)
    if not edl.get("name"):
        raise SystemExit("EDL needs a `name` (use the naming convention from the ad-batch skill).")
    if not edl.get("clips"):
        raise SystemExit("EDL needs at least one entry under `clips`.")
    ratio = ratio_override or str(edl.get("ratio") or "9:16")
    if ratio not in SAFE_ZONES:
        raise SystemExit(f"ratio {ratio!r} must be one of {list(SAFE_ZONES)}")
    edl["ratio"] = ratio
    name = edl["name"]
    for other, tok in RATIO_TOKEN.items():
        if other != ratio and f"_{tok}_" in name:
            name = name.replace(f"_{tok}_", f"_{RATIO_TOKEN[ratio]}_")
    edl["name"] = name
    edl_dir = path.resolve().parent
    for c in edl["clips"] + (edl.get("broll") or []):
        c["path"] = resolve(c["src"], edl_dir)
        if c["path"].suffix.lower() == ".heic":
            c["path"] = heic_to_png(c["path"], batch_dir_of(path) / "work" / "cuts" / "heic")
    for c in edl["clips"]:
        still = c["path"].suffix.lower() in IMAGE_EXT
        c["still"] = still
        if still:
            if not c.get("duration"):
                raise SystemExit(f"{c['src']}: a still image needs `duration`.")
            c["in"], c["out"] = 0.0, float(c["duration"])
        else:
            if "in" not in c or "out" not in c or float(c["out"]) <= float(c["in"]):
                raise SystemExit(f"{c['src']}: needs `in` and `out` with out > in.")
            c["in"], c["out"] = float(c["in"]), float(c["out"])
    for b in edl.get("broll") or []:
        b["still"] = b["path"].suffix.lower() in IMAGE_EXT
        if "at" not in b or "duration" not in b:
            raise SystemExit(f"broll {b['src']}: needs `at` and `duration`.")
    if edl.get("music"):
        edl["music"]["path"] = resolve(edl["music"]["src"], edl_dir)
    for s in edl.get("sfx") or []:
        s["path"] = resolve(s["src"], edl_dir)
    return edl


# ---------- geometry ----------

def ratio_of_size(w: int, h: int) -> str:
    """Exact 'w:h' ratio string for a pixel size (used for picture-in-picture segments of any shape)."""
    return f"{w}:{h}"


def crop_box(src_w: int, src_h: int, ratio: str, focus: tuple[float, float], zoom: float) -> tuple[int, int, int, int]:
    """(w, h, x, y) of the largest `ratio` box in the source, centered on focus, divided by zoom."""
    a, b = (int(x) for x in ratio.split(":"))
    cw = min(src_w, src_h * a / b)
    ch = cw * b / a
    cw, ch = cw / max(zoom, 1.0), ch / max(zoom, 1.0)
    x = min(max(focus[0] * src_w - cw / 2, 0), src_w - cw)
    y = min(max(focus[1] * src_h - ch / 2, 0), src_h - ch)
    return max(2, even(cw)), max(2, even(ch)), even(x), even(y)


def pick_resolution(ratio: str, crop_w: int) -> tuple[int, int]:
    """1440-class when the reframed source is at least 1440 px wide, else 1080-class. Never upscale soft footage."""
    big, small = RESOLUTIONS[ratio]
    return big if crop_w >= big[0] else small


def pick_fps(sources: list[dict]) -> int:
    for s in sources:
        if s.get("still"):
            continue
        f = parse_fps(s["vstream"].get("avg_frame_rate", "0/1")) or parse_fps(s["vstream"].get("r_frame_rate", "0/1"))
        if 23 <= f <= 26:
            return 25 if f > 24.5 else 24
        return 30
    return 30


YUNET = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"


def face_detector():
    """Return a callable(gray_or_bgr ndarray) -> list of (x, y, w, h), or None if OpenCV is missing."""
    try:
        import cv2
    except ImportError:
        return None
    if hasattr(cv2, "FaceDetectorYN") and YUNET.exists():
        try:
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)   # hide the "graph engine" notice
        except AttributeError:
            pass
        det = cv2.FaceDetectorYN.create(str(YUNET), "", (320, 320), 0.6, 0.3, 200)

        def yunet(img):
            h, w = img.shape[:2]
            det.setInputSize((w, h))
            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            _, faces = det.detect(img)
            return [tuple(int(v) for v in f[:4]) for f in (faces if faces is not None else [])]
        return yunet
    if hasattr(cv2, "CascadeClassifier"):
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        def haar(img):
            if img.ndim == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return [tuple(int(v) for v in f) for f in cascade.detectMultiScale(img, 1.1, 4, minSize=(40, 40))]
        return haar
    return None


def auto_focus(path: Path, t_in: float, t_out: float, samples: int = 5) -> tuple[float, float]:
    """Median face center (fractions of width/height) across a few frames. Falls back to upper-center."""
    detect = face_detector()
    if detect is None:
        print("WARNING: no face detector (OpenCV missing); using upper-center focus")
        return (0.5, 0.42)
    import numpy as np

    w, h = display_size(video_stream(probe(path)))
    sw = 640
    sh = even(h * sw / w)
    centers = []
    for i in range(samples):
        t = t_in + (t_out - t_in) * (i + 0.5) / samples
        res = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                              "-vf", f"scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                             capture_output=True)
        if len(res.stdout) < sw * sh * 3:
            continue
        img = np.frombuffer(res.stdout[: sw * sh * 3], np.uint8).reshape(sh, sw, 3)
        faces = detect(img)
        if faces:
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            centers.append(((x + fw / 2) / sw, (y + fh / 2) / sh))
    if not centers:
        return (0.5, 0.42)
    xs, ys = sorted(c[0] for c in centers), sorted(c[1] for c in centers)
    return (xs[len(xs) // 2], ys[len(ys) // 2])


# ---------- silence tightening ----------

def silences(path: Path, t_in: float, t_out: float, min_len: float, noise_db: float = -38.0) -> list[tuple[float, float]]:
    # silencedetect reports at info level, so raise verbosity for this call only.
    res = run_ffmpeg(["-v", "info", "-ss", f"{t_in:.3f}", "-t", f"{t_out - t_in:.3f}", "-i", str(path), "-vn",
                      "-af", f"silencedetect=n={noise_db}dB:d={min_len}", "-f", "null", "-"], check=False)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", res.stderr)]
    out = []
    for s, e in zip(starts, ends):
        out.append((t_in + max(s, 0.0), t_in + e))
    return out


def tighten_ranges(t_in: float, t_out: float, gaps: list[tuple[float, float]], keep: float) -> list[tuple[float, float]]:
    """Cut the middle out of each internal silence, leaving `keep` seconds on each side. Edges are left alone."""
    ranges, cur = [], t_in
    for s, e in gaps:
        if s <= t_in + keep or e >= t_out - keep:
            continue  # a pause at the very start or end is a cut point, not a gap to tighten
        if (e - s) <= 2 * keep:
            continue
        ranges.append((cur, s + keep))
        cur = e - keep
    ranges.append((cur, t_out))
    return [(a, b) for a, b in ranges if b - a > 0.05]


# ---------- segments ----------

def look_filter(look: dict | None) -> str | None:
    """Optional light grade: eq (contrast, brightness, saturation) and a gentle unsharp."""
    if not look:
        return None
    parts = []
    eq = []
    for key in ("contrast", "brightness", "saturation", "gamma"):
        if look.get(key) is not None:
            eq.append(f"{key}={float(look[key])}")
    if eq:
        parts.append("eq=" + ":".join(eq))
    if look.get("sharpen"):
        parts.append("unsharp=5:5:0.6:5:5:0.0")
    return ",".join(parts) or None


SETTLE_S = 0.25   # seconds a settle cut takes to come to rest


def video_filters(src_w: int, src_h: int, hdr: bool, ratio: str, out_w: int, out_h: int, fps: int,
                  focus: tuple[float, float], zoom: float, push: float | None, duration: float,
                  look: dict | None = None, settle: float | None = None) -> str:
    f = []
    if hdr:
        f.append(HDR_TO_SDR)
    cw, ch, x, y = crop_box(src_w, src_h, ratio, focus, zoom)
    f.append(f"crop={cw}:{ch}:{x}:{y}")
    if push and push > 1.0:
        # Slow push from 1.0 to `push` over the clip: scale grows per frame, a fixed center crop keeps the size.
        # (zoompan on video input is slow and memory hungry; scale with eval=frame is cheap.)
        d = max(duration, 0.1)
        grow = f"(1+({push - 1:.4f})*min(t,{d:.3f})/{d:.3f})"
        f.append(f"scale=w='trunc({out_w}*{grow}/2)*2':h='trunc({out_h}*{grow}/2)*2':eval=frame")
        f.append(f"crop={out_w}:{out_h}:(iw-{out_w})/2:(ih-{out_h})/2")
    elif settle and settle > 1.0:
        # Settle cut: the clip opens pushed in by `settle` and eases back to its framing over SETTLE_S.
        # Reads as a deliberate motion cut instead of a static jump, the way modern editors cut talking heads.
        ease = f"(1-pow(1-min(t,{SETTLE_S})/{SETTLE_S},3))"   # cubic ease-out
        grow = f"(1+({settle - 1:.4f})*(1-{ease}))"
        f.append(f"scale=w='trunc({out_w}*{grow}/2)*2':h='trunc({out_h}*{grow}/2)*2':eval=frame")
        f.append(f"crop={out_w}:{out_h}:(iw-{out_w})/2:(ih-{out_h})/2")
    else:
        f.append(f"scale={out_w}:{out_h}")
    lf = look_filter(look)
    if lf:
        f.append(lf)
    f += [f"fps={fps}", "setsar=1", "format=yuv420p"]
    return ",".join(f)


def render_segment(clip: dict, t_in: float, t_out: float, out: Path, ratio: str, out_w: int, out_h: int,
                   fps: int, enc: list[str], focus: tuple[float, float], timecode_from: float | None = None,
                   font: str | None = None) -> None:
    v = clip["vstream"]
    src_w, src_h = display_size(v)
    dur = t_out - t_in
    vf = video_filters(src_w, src_h, is_hdr(v), ratio, out_w, out_h, fps, focus,
                       float(clip.get("zoom") or 1.0), clip.get("push"), dur, clip.get("_look"), clip.get("_settle"))
    if timecode_from is not None and font:
        vf += (f",drawtext=fontfile='{font}':text='%{{pts\\:hms\\:{timecode_from:.3f}}}':fontsize={max(18, out_h // 30)}:"
               f"fontcolor=white:box=1:boxcolor=black@0.6:x=10:y=10")
    args = []
    if clip["still"]:
        args += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", str(clip["path"])]
        args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        args += ["-map", "0:v:0", "-map", "1:a:0"]
    else:
        args += ["-ss", f"{t_in:.3f}", "-t", f"{dur:.3f}", "-i", str(clip["path"])]
        if clip["astream"] is None:
            args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v:0", "-map", "1:a:0"]
        else:
            args += ["-map", "0:v:0", "-map", "0:a:0"]
    # 30 ms fades at every cut so hard cuts never click or pop.
    af = f"{AUD_NORM},afade=t=in:d={CUT_FADE},afade=t=out:st={max(0.0, dur - CUT_FADE):.3f}:d={CUT_FADE}"
    args += ["-vf", vf, "-af", af, *enc, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-shortest", "-video_track_timescale", "90000", str(out)]
    run_ffmpeg(args)


def render_end_card(card: dict, out: Path, out_w: int, out_h: int, fps: int, enc: list[str], cfg: dict,
                    font: str, tmp: Path) -> None:
    colors = (cfg.get("business") or {}).get("brand_colors") or {}
    bg = colors.get("primary", "#3B96F6").lstrip("#")
    accent = colors.get("accent", "#E55B13").lstrip("#")
    secs = float(card.get("seconds") or DEFAULTS["end_card_seconds"])
    box = safe_box(out_w, out_h, card["_ratio"])
    text_f = tmp / "endcard_text.txt"
    text_f.write_text(str(card.get("text") or "Tap Learn More"))
    size = max(28, round(out_h * 0.055))
    filters = []
    if card.get("headline"):
        head_f = tmp / "endcard_head.txt"
        head_f.write_text(wrap_text(str(card["headline"]), 20))
        filters.append(f"drawtext=fontfile='{font}':textfile='{head_f}':fontsize={round(size * 0.85)}:fontcolor=white:"
                       f"x=(w-text_w)/2:y=(h*0.36-text_h):line_spacing={round(size * 0.1)}")
    # CTA as a pill button in the accent color (the thing a thumb would tap)
    filters.append(f"drawtext=fontfile='{font}':textfile='{text_f}':fontsize={size}:fontcolor=white:"
                   f"x=(w-text_w)/2:y=(h*0.46-text_h/2):box=1:boxcolor=0x{accent}:boxborderw={round(size * 0.55)}")
    if card.get("subtext"):
        sub_f = tmp / "endcard_sub.txt"
        sub_f.write_text(str(card["subtext"]))
        filters.append(f"drawtext=fontfile='{font}':textfile='{sub_f}':fontsize={round(size * 0.6)}:fontcolor=white@0.92:"
                       f"x=(w-text_w)/2:y=(h*0.46+{round(size * 1.4)})")
    args = ["-f", "lavfi", "-t", f"{secs:.3f}", "-i", f"color=c=0x{bg}:s={out_w}x{out_h}:r={fps}",
            "-f", "lavfi", "-t", f"{secs:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    logo = ROOT / "brand" / "logo.png"
    maps = ["-map", "0:v:0", "-map", "1:a:0"]
    if card.get("logo") and logo.exists():
        args += ["-loop", "1", "-t", f"{secs:.3f}", "-i", str(logo)]
        lw = even(out_w * 0.28)
        fc = (f"[2:v]scale={lw}:-2[logo];[0:v][logo]overlay=x=(W-w)/2:y={box['top']}+{round(out_h * 0.04)}[bg];"
              f"[bg]{','.join(filters)},format=yuv420p[v]")
        args += ["-filter_complex", fc, "-map", "[v]", "-map", "1:a:0"]
    else:
        args += ["-vf", ",".join(filters) + ",format=yuv420p", *maps]
    args += [*enc, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest",
             "-video_track_timescale", "90000", str(out)]
    run_ffmpeg(args)


def render_end_card_html(card: dict, out: Path, out_w: int, out_h: int, fps: int, enc: list[str], cfg: dict, tmp: Path) -> None:
    """Animated end card (logo pop, headline, pulsing CTA button) rendered as a plate on the brand color."""
    import plates as pl  # noqa: WPS433

    secs = float(card.get("seconds") or DEFAULTS["end_card_seconds"])
    spec = {"type": "endcard", "headline": card.get("headline", ""), "text": card.get("text") or "Tap Learn More",
            "subtext": card.get("subtext", ""), "logo": card.get("logo", True), "duration": secs}
    mov = tmp / "end_card_plate.mov"
    r = pl.Renderer(out_w, out_h)
    try:
        r.render_mov(pl.build_html(spec, out_w, out_h, cfg), secs, fps, mov)
    finally:
        r.close()
    run_ffmpeg(["-i", str(mov), "-f", "lavfi", "-t", f"{secs:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                "-map", "0:v:0", "-map", "1:a:0", "-vf", "format=yuv420p", *enc, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-ac", "2", "-shortest", "-video_track_timescale", "90000", str(out)])


def concat(segments: list[Path], out: Path, tmp: Path) -> None:
    lst = tmp / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments))
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])


def duration_of(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


# ---------- editor defaults ----------

def apply_editor_defaults(edl: dict, cfg: dict) -> None:
    """What a trained editor does by reflex unless told otherwise (config `edit.*`, per-clip keys override):
    alternate framing on consecutive talking-head clips, tighten every pause, settle every cut after the first."""
    e = cfg.get("edit") or {}
    clips = edl["clips"]
    if e.get("auto_alternate_zoom", True):
        last_zoom = None
        for c in clips:
            if c["still"] or "zoom" in c or c.get("push"):
                last_zoom = None if c["still"] else float(c.get("zoom") or 1.0)
                continue
            c["zoom"] = float(e.get("alternate_zoom") or 1.08) if last_zoom == 1.0 else 1.0
            last_zoom = c["zoom"]
    auto_t = e.get("auto_tighten", 0.45)
    if auto_t:
        for c in clips:
            if not c["still"] and "tighten" not in c:
                c["tighten"] = float(auto_t)
    settle = e.get("settle_cuts", 1.04)
    if settle:
        for n, c in enumerate(clips):
            if n == 0 or c["still"] or c.get("push"):
                continue
            c["_settle"] = float(c["settle"]) if "settle" in c else float(settle)
    for c in clips:
        if c.get("settle") == 0:
            c["_settle"] = None


# ---------- motion plates (browser-rendered graphics) ----------

def plates_available(cfg: dict) -> bool:
    if str((cfg.get("graphics") or {}).get("engine") or "html") != "html":
        return False
    try:
        import playwright  # noqa: F401
        import plates  # noqa: F401
        return True
    except ImportError:
        return False


def plate_specs(edl: dict, cfg: dict) -> list[dict]:
    """Every graphic as a plate spec with `at` and `duration`, in render order (hook first, end card last)."""
    specs = []
    if edl.get("hook_text"):
        specs.append({"type": "hook", "text": str(edl["hook_text"]), "at": 0.0,
                      "duration": float(edl.get("hook_text_seconds") or DEFAULTS["hook_text_seconds"]),
                      "variant": str(edl.get("hook_variant") or "dark")})
    lt = edl.get("lower_third")
    if lt and lt.get("text"):
        text, sub = str(lt["text"]), str(lt.get("sub") or "")
        if not sub and "," in text:
            text, sub = (x.strip() for x in text.split(",", 1))
        specs.append({"type": "lower_third", "text": text, "sub": sub, "at": float(lt.get("at") or 1.0), "duration": float(lt.get("duration") or 3.0)})
    for co in edl.get("callouts") or []:
        specs.append({"type": "label", "text": str(co["text"]), "at": float(co["at"]), "duration": float(co.get("duration") or 2.0),
                      "position": str(co.get("position") or "center"), "variant": "accent" if co.get("accent") else str(co.get("variant") or "dark"),
                      "emoji": co.get("emoji", ""), "sfx": co.get("sfx", "pop")})
    for b in edl.get("broll") or []:
        if b.get("pip") and b.get("still") and b.get("_html_pip"):
            pip = b["pip"]
            specs.append({"type": "pip", "src": str(b["path"]), "at": float(b["at"]), "duration": float(b["duration"]),
                          "w": pip.get("w"), "y": pip.get("y"), "device": pip.get("device"), "zoom": pip.get("zoom"), "caption": b.get("label")})
    for pl in edl.get("plates") or []:
        sp = dict(pl)
        sp.setdefault("duration", 2.5)
        specs.append(sp)
    lead = float((cfg.get("graphics") or {}).get("lead_s") or 0.0)
    for sp in specs:
        if "at" not in sp:
            raise SystemExit(f"plate {sp.get('type')} needs `at`")
        if lead and float(sp["at"]) > 0:
            sp["at"] = round(max(0.0, float(sp["at"]) - lead), 3)   # cue graphics a few frames before the word
    return sorted(specs, key=lambda x: (float(x["at"]), x["type"] != "hook"))


def rounded_mask_and_shadow(w: int, h: int, radius: int, tmp: Path, tag: str) -> tuple[Path, Path, int]:
    """A rounded-rectangle alpha mask for an inset and a soft shadow PNG (returns mask, shadow, shadow padding)."""
    from PIL import Image, ImageDraw, ImageFilter

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    mask_p = tmp / f"mask_{tag}.png"
    mask.save(mask_p)
    pad = max(24, radius)
    sh = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + pad // 3, pad + w - 1, pad + h - 1 + pad // 3), radius=radius, fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(pad / 2))
    sh_p = tmp / f"shadow_{tag}.png"
    sh.save(sh_p)
    return mask_p, sh_p, pad


# ---------- composite ----------

def drawtext_block(font: str, textfile: Path, size: int, color: str, y_expr: str, start: float, end: float,
                   box_color: str | None = None, line_spacing: int = 0) -> str:
    box = f":box=1:boxcolor={box_color}:boxborderw={max(8, size // 3)}" if box_color else ""
    return (f"drawtext=fontfile='{font}':textfile='{textfile}':fontsize={size}:fontcolor={color}:"
            f"x=(w-text_w)/2:y={y_expr}:line_spacing={line_spacing}{box}:enable='between(t,{start:.3f},{end:.3f})'")


HOOK_SIZE = 0.046      # headline font size as a fraction of frame height
HOOK_WRAP = 18         # characters per headline line
LOWER_THIRD_GAP = 0.15  # fraction of frame height above the bottom safe zone; clears a two-line caption page


def hook_text_height(text: str, out_h: int) -> int:
    """Approximate pixel height of the wrapped headline block, box border included."""
    size = round(out_h * HOOK_SIZE)
    lines = wrap_text(text, HOOK_WRAP).count("\n") + 1
    return round(lines * size * 1.3 + max(8, size // 3) * 2)


def wrap_text(text: str, max_chars: int) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def composite(aroll: Path, edl: dict, out: Path, out_w: int, out_h: int, fps: int, total: float,
              cfg: dict, font: str, tmp: Path, enc: list[str], proxy: bool) -> dict:
    """B-roll, graphics, voice chain, music, SFX. Returns the timeline sidecar."""
    ratio = edl["ratio"]
    box = safe_box(out_w, out_h, ratio)
    colors = (cfg.get("business") or {}).get("brand_colors") or {}
    accent = "0x" + colors.get("accent", "#E55B13").lstrip("#")
    inputs = ["-i", str(aroll)]
    vchain, timeline = [], {"name": edl["name"], "ratio": ratio, "size": [out_w, out_h], "fps": fps,
                            "duration": total, "clips": edl["_timeline_clips"], "broll": [], "graphics": []}
    idx = 1
    cur = "[0:v]"
    n_insets = sum(1 for b in (edl.get("broll") or []) if b.get("speaker_inset") and not b.get("pip"))
    if n_insets:
        vchain.append(f"[0:v]split={n_insets + 1}[a0]" + "".join(f"[spk{i}]" for i in range(n_insets)))
        cur = "[a0]"
    inset_i = 0
    # B-roll overlays (picture only)
    use_html = (not proxy) and plates_available(cfg)
    for b in edl.get("broll") or []:
        at, dur = float(b["at"]), float(b["duration"])
        if use_html and b.get("pip") and b.get("still"):
            b["_html_pip"] = True   # rendered as a motion plate below (rounded frame, shadow, slow zoom)
            timeline["broll"].append({"src": b["src"], "at": at, "duration": dur, "label": b.get("label"), "pip": True, "engine": "html"})
            continue
        seg = tmp / f"broll_{idx}.mp4"
        clip = {"path": b["path"], "still": b["still"], "vstream": b["vstream"], "astream": None,
                "zoom": b.get("zoom") or 1.0, "push": b.get("push")}
        src_in = float(b.get("src_in") or 0.0)
        pip = b.get("pip")
        win = f"enable='between(t,{at:.3f},{at + dur:.3f})'"
        k = idx   # label of this B-roll's output; extra mask/shadow inputs bump idx below
        if pip:
            # Picture-in-picture video: rounded corners and a soft shadow (no hard border), scaled to a fraction of the width.
            bw, bh = display_size(b["vstream"])
            pw = even(out_w * float(pip.get("w") or 0.7))
            ph = even(pw * bh / bw)
            render_segment({**clip, "focus": None}, src_in, src_in + dur, seg, ratio_of_size(pw, ph), pw, ph, fps,
                           ENC_INTER, (0.5, 0.5))
            cx, cy = float(pip.get("x") or 0.5), float(pip.get("y") or 0.40)
            px, py = even(cx * out_w - pw / 2), even(cy * out_h - ph / 2)
            mask_p, sh_p, pad = rounded_mask_and_shadow(pw, ph, round(out_w * 0.035), tmp, f"pip{idx}")
            inputs += ["-i", str(seg), "-loop", "1", "-i", str(mask_p), "-loop", "1", "-i", str(sh_p)]
            vchain.append(f"[{idx}:v]setpts=PTS-STARTPTS+{at:.3f}/TB,format=rgba[bv{idx}]")
            vchain.append(f"[{idx + 1}:v]format=gray[bm{idx}]")
            vchain.append(f"[bv{idx}][bm{idx}]alphamerge[br{idx}]")
            vchain.append(f"{cur}[{idx + 2}:v]overlay=x={px - pad}:y={py - pad}:{win}[bs{idx}]")
            vchain.append(f"[bs{idx}][br{idx}]overlay=x={px}:y={py}:eof_action=pass:{win}[v{idx}]")
            idx += 2
        else:
            render_segment(clip, src_in, src_in + dur, seg, ratio, out_w, out_h, fps, ENC_INTER, (0.5, 0.5))
            inputs += ["-i", str(seg)]
            vchain.append(f"[{idx}:v]setpts=PTS-STARTPTS+{at:.3f}/TB[b{idx}]")
            vchain.append(f"{cur}[b{idx}]overlay=eof_action=pass:{win}[v{idx}]")
        cur = f"[v{k}]"
        ins = b.get("speaker_inset")
        if ins and not pip:
            # The screen is the set: full-frame B-roll with the speaker kept in a rounded inset in a corner
            # (reference: creator ads, Nov 2026). Taken from the A-roll itself, so lip sync is untouched.
            # Default: 40% wide, lower right, bottom edge 10% off the frame bottom (face lands near 60% height).
            iw_ = even(out_w * float(ins.get("w") or 0.40))
            ih_ = even(iw_ * out_h / out_w)
            cx, cy = float(ins.get("x") or 0.76), float(ins.get("y") or 0.70)
            px, py = even(cx * out_w - iw_ / 2), even(cy * out_h - ih_ / 2)
            mask_p, sh_p, pad = rounded_mask_and_shadow(iw_, ih_, round(out_w * 0.035), tmp, f"spk{idx}")
            inputs += ["-loop", "1", "-i", str(mask_p), "-loop", "1", "-i", str(sh_p)]
            vchain.append(f"[spk{inset_i}]scale={iw_}:{ih_},format=rgba[sp{idx}]")
            inset_i += 1
            vchain.append(f"[{idx + 1}:v]format=gray[sm{idx}]")
            vchain.append(f"[sp{idx}][sm{idx}]alphamerge[sr{idx}]")
            vchain.append(f"{cur}[{idx + 2}:v]overlay=x={px - pad}:y={py - pad}:{win}[ss{idx}]")
            vchain.append(f"[ss{idx}][sr{idx}]overlay=x={px}:y={py}:{win}[sv{idx}]")
            cur = f"[sv{idx}]"
            idx += 2
            b["_inset_done"] = True
        timeline["broll"].append({"src": b["src"], "at": at, "duration": dur, "label": b.get("label"), "pip": bool(pip),
                                  "speaker_inset": bool(b.get("_inset_done"))})
        if b.get("label") and not proxy:
            lf = tmp / f"broll_label_{idx}.txt"
            lf.write_text(wrap_text(str(b["label"]), 22))
            size = round(out_h * 0.034)
            y = box["top"] + round(out_h * 0.03)
            hook_secs = float(edl.get("hook_text_seconds") or DEFAULTS["hook_text_seconds"]) if edl.get("hook_text") else 0.0
            if at < hook_secs:  # the headline is still up: drop the label below it
                y += hook_text_height(str(edl["hook_text"]), out_h) + round(out_h * 0.02)
            vchain.append(f"{cur}{drawtext_block(font, lf, size, 'white', str(y), at, at + dur, 'black@0.55')}[l{idx}]")
            cur = f"[l{idx}]"
        idx += 1
    html_engine = (not proxy) and plates_available(cfg)
    if html_engine:
        # Browser-rendered motion plates: hook, callouts, lower third, cards, stats, pip images. Flat drawtext is the fallback.
        specs = plate_specs(edl, cfg)
        if specs:
            import plates as pl  # noqa: WPS433

            r = pl.Renderer(out_w, out_h)
            try:
                for n, sp in enumerate(specs):
                    mov = tmp / f"plate_{n:02d}_{sp['type']}.mov"
                    r.render_mov(pl.build_html(sp, out_w, out_h, cfg), float(sp["duration"]), fps, mov)
                    at, dur = float(sp["at"]), float(sp["duration"])
                    inputs += ["-i", str(mov)]
                    vchain.append(f"[{idx}:v]format=rgba,setpts=PTS-STARTPTS+{at:.3f}/TB[p{n}]")
                    vchain.append(f"{cur}[p{n}]overlay=format=auto:eof_action=pass:enable='between(t,{at:.3f},{at + dur:.3f})'[pv{n}]")
                    cur = f"[pv{n}]"
                    idx += 1
                    timeline["graphics"].append({"type": sp["type"], "text": sp.get("text") or sp.get("title") or sp.get("headline") or "",
                                                 "at": at, "duration": dur, "region": pl.region_of(sp), "engine": "html"})
            finally:
                r.close()
    if not proxy and not html_engine:
        # Headline hook text from frame 1, inside the top safe zone
        if edl.get("hook_text"):
            hf = tmp / "hook.txt"
            wrapped = wrap_text(str(edl["hook_text"]), HOOK_WRAP)
            if wrapped.count("\n") >= 2:
                print(f"WARNING: hook_text wraps to {wrapped.count(chr(10)) + 1} lines; shorten it to read in one glance")
            hf.write_text(wrapped)
            secs = float(edl.get("hook_text_seconds") or DEFAULTS["hook_text_seconds"])
            size = round(out_h * HOOK_SIZE)
            vchain.append(f"{cur}{drawtext_block(font, hf, size, 'white', f'{box['top']}+{round(out_h * 0.02)}', 0.0, secs, 'black@0.6', line_spacing=round(size * 0.15))}[hook]")
            cur = "[hook]"
            timeline["graphics"].append({"type": "hook_text", "text": edl["hook_text"], "at": 0.0, "duration": secs})
        # Callouts: short on-screen text mid-video (a number, a re-hook, a label). Centered, above the caption band.
        for n, co in enumerate(edl.get("callouts") or []):
            cf = tmp / f"callout_{n}.txt"
            cf.write_text(wrap_text(str(co["text"]), 16))
            at, dur = float(co["at"]), float(co.get("duration") or 2.0)
            size = round(out_h * float(co.get("size") or 0.05))
            pos = str(co.get("position") or "center")
            y = {"top": f"{box['top']}+{round(out_h * 0.02)}", "center": "(h*0.42-text_h/2)",
                 "lower": f"h-{box['bottom']}-{round(out_h * 0.12)}-text_h"}[pos]
            if pos == "top" and at < (float(edl.get("hook_text_seconds") or DEFAULTS["hook_text_seconds"]) if edl.get("hook_text") else 0.0):
                raise SystemExit(f"callout {co['text']!r} at {at}s collides with the hook text; use position: center")
            color = accent if co.get("accent") else "black@0.6"
            vchain.append(f"{cur}{drawtext_block(font, cf, size, 'white', y, at, at + dur, color, line_spacing=round(size * 0.15))}[co{n}]")
            cur = f"[co{n}]"
            timeline["graphics"].append({"type": "callout", "text": co["text"], "at": at, "duration": dur, "position": pos})
        lt = edl.get("lower_third")
        if lt and lt.get("text"):
            lf = tmp / "lower_third.txt"
            lf.write_text(str(lt["text"]))
            at, dur = float(lt.get("at") or 1.0), float(lt.get("duration") or 3.0)
            size = round(out_h * 0.028)
            # Sits above the caption band (two-line page plus padding) so the two never overlap.
            y = f"h-{box['bottom']}-{round(out_h * LOWER_THIRD_GAP)}-text_h"
            vchain.append(f"{cur}drawtext=fontfile='{font}':textfile='{lf}':fontsize={size}:fontcolor=white:"
                          f"x={box['side']}+{round(out_w * 0.02)}:y={y}:box=1:boxcolor={accent}@0.9:boxborderw={size // 2}:"
                          f"enable='between(t,{at:.3f},{at + dur:.3f})'[lt]")
            cur = "[lt]"
            timeline["graphics"].append({"type": "lower_third", "text": lt["text"], "at": at, "duration": dur})
    vchain.append(f"{cur}format=yuv420p[vout]")

    # Audio
    achain = []
    hp = int((cfg.get("audio") or {}).get("voice_highpass_hz") or DEFAULTS["voice_highpass_hz"])
    voice = [f"highpass=f={hp}"]
    if (cfg.get("audio") or {}).get("voice_denoise", DEFAULTS["voice_denoise"]):
        voice.append("afftdn=nf=-25")
    voice += ["acompressor=threshold=-18dB:ratio=2.5:attack=5:release=80:makeup=2", "deesser"]
    mix_inputs = []
    music = edl.get("music") if not proxy else None
    if music:
        achain.append(f"[0:a]{','.join(voice)},asplit=2[vo][vokey]")
        inputs += ["-stream_loop", "-1", "-i", str(music["path"])]
        gain = float(music.get("gain_db") if music.get("gain_db") is not None else DEFAULTS["music_gain_db"])
        fade = float(music.get("fade_out") if music.get("fade_out") is not None else DEFAULTS["music_fade_out"])
        m = (f"[{idx}:a]{AUD_NORM},atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={gain}dB,"
             f"afade=t=out:st={max(0.0, total - fade):.3f}:d={fade:.3f}[m0]")
        achain.append(m)
        if music.get("duck", DEFAULTS["duck"]):
            achain.append("[m0][vokey]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=350:level_sc=1:makeup=1[mus]")
        else:
            achain.append("[m0]anull[mus];[vokey]anullsink")
        mix_inputs = ["[vo]", "[mus]"]
        idx += 1
    else:
        achain.append(f"[0:a]{','.join(voice)}[vo]")
        mix_inputs = ["[vo]"]
    sfx_list = list(edl.get("sfx") or []) if not proxy else []
    gcfg = cfg.get("graphics") or {}
    if html_engine and gcfg.get("auto_sfx", True):
        import plates as pl  # noqa: WPS433
        import sfx as sfxmod  # noqa: WPS433

        defaults = sfxmod.ensure_defaults(tmp / "sfx")
        gain = float(gcfg.get("sfx_gain_db") if gcfg.get("sfx_gain_db") is not None else -14.0)
        for sp in plate_specs(edl, cfg):
            name = sp.get("sfx", pl.ENTRANCE_SFX.get(sp["type"]))
            if not name or float(sp["at"]) <= 0.0:
                continue
            custom = ROOT / "audio" / "sfx" / f"{name}.wav"
            sfx_list.append({"path": custom if custom.exists() else defaults.get(name, defaults["pop"]), "at": float(sp["at"]), "gain_db": gain, "src": name})
    for n, s in enumerate(sfx_list):
        inputs += ["-i", str(s["path"])]
        at_ms = int(round(float(s["at"]) * 1000))
        gain = float(s.get("gain_db") if s.get("gain_db") is not None else -10.0)
        achain.append(f"[{idx}:a]{AUD_NORM},volume={gain}dB,adelay={at_ms}|{at_ms}[sfx{n}]")
        mix_inputs.append(f"[sfx{n}]")
        idx += 1
    if len(mix_inputs) == 1:
        achain.append(f"{mix_inputs[0]}atrim=0:{total:.3f}[aout]")
    else:
        achain.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0,atrim=0:{total:.3f}[aout]")

    fc = ";".join(vchain + achain)
    (tmp / "filter_complex.txt").write_text(fc)
    run_ffmpeg([*inputs, "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]", *enc, "-c:a", "pcm_s16le",
                "-ar", "48000", "-ac", "2", "-t", f"{total:.3f}", str(out)])
    return timeline


# ---------- loudness + captions ----------

TP_HEADROOM_DB = 0.5   # loudnorm target sits this far under audio.true_peak_max_dbtp


def measure_loudnorm(path: Path, target: float, tp: float) -> dict:
    res = run_ffmpeg(["-v", "info", "-i", str(path), "-af", f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                     check=False)
    err = res.stderr
    try:
        return json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    except ValueError:
        raise RuntimeError("loudnorm measurement failed; is there an audio track?")


def loudnorm_filter(m: dict, target: float, tp: float) -> str:
    return (f"loudnorm=I={target}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def finalize(comp: Path, out: Path, lf: str, ass: Path | None, fonts_dir: Path, enc: list[str], fps: int) -> str:
    args = ["-i", str(comp)]
    if ass:
        args += ["-vf", f"ass='{ass.as_posix()}':fontsdir='{fonts_dir.as_posix()}'"]
    args += ["-af", lf, *enc, "-r", str(fps), *AUD_ENC, "-movflags", "+faststart", str(out)]
    res = run_ffmpeg(["-v", "warning", *args])
    return res.stderr


def build_captions(words_json: Path, out_w: int, out_h: int, ass_out: Path, cfg: dict, edl: dict | None = None) -> None:
    """Captions from the master transcript. The EDL may add `caption_keywords` and override `caption_style`."""
    import captions as cap  # noqa: WPS433 (local tool module)

    edl = edl or {}
    biz = cfg.get("business") or {}
    c = cfg.get("captions") or {}
    words = cap.apply_fixes(json.loads(words_json.read_text()), c.get("fixes") or {})
    keywords = {k.lower() for k in (c.get("keywords") or [])} | {k.lower() for k in (edl.get("caption_keywords") or [])}
    ass = cap.build_ass(words, out_w, out_h, font=biz.get("caption_font_name") or "Montserrat ExtraBold",
                        accent=(biz.get("brand_colors") or {}).get("accent", "#E55B13"),
                        max_words=max(2, min(5, int(c.get("words_per_chunk_max") or 4))),
                        uppercase=bool(c.get("uppercase")), keywords=keywords,
                        style=str(edl.get("caption_style") or c.get("style") or "chunk"))
    ass_out.write_text(ass)


ASS_STYLES = {"chunk", "highlight", "karaoke", "reveal", "hormozi"}
HTML_STYLES = {"pill", "highlight", "clean", "box"}


def build_caption_plate(words_json: Path, out_w: int, out_h: int, total: float, fps: int, out: Path, cfg: dict, edl: dict) -> list[dict]:
    """Word-timed captions as a transparent plate covering the whole ad. Returns the page list for QA."""
    import captions as cap  # noqa: WPS433
    import plates as pl  # noqa: WPS433

    c = cfg.get("captions") or {}
    words = cap.apply_fixes(json.loads(words_json.read_text()), c.get("fixes") or {})
    style = str(edl.get("caption_style") or c.get("style") or "pill")
    if style not in HTML_STYLES:
        style = {"chunk": "clean", "karaoke": "pill", "reveal": "pill", "hormozi": "pill"}.get(style, "pill")
    keywords = [k for k in (c.get("keywords") or [])] + [k for k in (edl.get("caption_keywords") or [])]
    spec = {"type": "captions", "words": words, "style": style, "keywords": keywords,
            "max_words": max(2, min(5, int(c.get("words_per_chunk_max") or 4))), "uppercase": bool(c.get("uppercase")),
            "duration": total}
    r = pl.Renderer(out_w, out_h)
    try:
        r.render_mov(pl.build_html(spec, out_w, out_h, cfg), total, fps, out)
    finally:
        r.close()
    chunks = cap.chunk(words, spec["max_words"])
    return [{"start": ch[0]["start"], "end": cap.page_end(chunks, n), "text": " ".join(w["word"] for w in ch)} for n, ch in enumerate(chunks)]


def finalize_with_plate(comp: Path, out: Path, lf: str, plate: Path, enc: list[str], fps: int) -> None:
    run_ffmpeg(["-i", str(comp), "-i", str(plate), "-filter_complex",
                "[1:v]format=rgba[c];[0:v][c]overlay=format=auto:eof_action=pass,format=yuv420p[v]",
                "-map", "[v]", "-map", "0:a:0", "-af", lf, *enc, "-r", str(fps), *AUD_ENC, "-movflags", "+faststart", str(out)])


def transcribe_master(master: Path, out_dir: Path) -> Path | None:
    import transcribe as tr  # noqa: WPS433

    backend = tr.pick_backend("auto")
    if backend is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    tr.transcribe_file(master, out_dir, backend=backend, model=None, prompt=tr.DEFAULT_PROMPT)
    return out_dir / f"{master.stem}.words.json"


def timeline_of(edl_path: Path, ratio: str | None = None) -> list[dict]:
    """Clip map (src, src_in, src_out, at, duration) for an EDL without rendering video.

    Uses the same tightening and still-duration rules as render(), so word timings from
    source transcripts can be mapped onto the master timeline (see tools/make_sample.py).
    """
    cfg = load_config()
    edl = load_edl(edl_path, ratio)
    apply_editor_defaults(edl, cfg)
    keep = float((cfg.get("edit") or {}).get("tighten_keep") or DEFAULTS["tighten_keep"])
    out, t = [], 0.0
    for c in edl["clips"]:
        ranges = [(c["in"], c["out"])]
        if c.get("tighten") and not c["still"]:
            ranges = tighten_ranges(c["in"], c["out"], silences(c["path"], c["in"], c["out"], float(c["tighten"])), keep)
        for a, b in ranges:
            out.append({"src": c["src"], "src_in": round(a, 3), "src_out": round(b, 3), "at": round(t, 3), "duration": round(b - a, 3)})
            t += b - a
    card = edl.get("end_card")
    if card:
        out.append({"src": "end_card", "at": round(t, 3), "duration": float(card.get("seconds") or DEFAULTS["end_card_seconds"])})
    return out


# ---------- main ----------

def render(edl_path: Path, ratio: str | None, captions_arg: str | None, proxy: bool, keep_tmp: bool,
           out_dir: Path | None) -> Path:
    cfg = load_config()
    edl = load_edl(edl_path, ratio)
    ratio = edl["ratio"]
    batch_dir = batch_dir_of(edl_path)
    exports = out_dir or (batch_dir / ("work/proxies" if proxy else "exports"))
    cuts = batch_dir / "work" / "cuts"
    exports.mkdir(parents=True, exist_ok=True)
    cuts.mkdir(parents=True, exist_ok=True)

    for c in edl["clips"] + (edl.get("broll") or []):
        info = probe(c["path"])
        c["vstream"] = video_stream(info)
        c["astream"] = audio_stream(info)
        if c["vstream"] is None:
            raise SystemExit(f"{c['src']}: no video stream")

    first = edl["clips"][0]
    fw, fh = display_size(first["vstream"])
    cw, *_ = crop_box(fw, fh, ratio, (0.5, 0.5), 1.0)
    out_w, out_h = pick_resolution(ratio, cw)
    if proxy:
        out_w, out_h = even(540), even(540 * out_h / out_w)
    fps = pick_fps(edl["clips"])
    enc = ENC_PROXY if proxy else ENC_INTER
    font_name = (cfg.get("business") or {}).get("caption_font_name") or "Montserrat ExtraBold"
    font, exact = find_font(font_name)
    if not font:
        raise SystemExit(f"No font file found for {font_name!r}. Put the .ttf/.otf in brand/fonts/.")
    if not exact:
        print(f"WARNING: brand font {font_name!r} not in brand/fonts; drawtext is using {font}")

    tmp_ctx = tempfile.TemporaryDirectory(prefix="render_", dir=str(cuts))
    tmp = Path(tmp_ctx.name)
    try:
        segments, t = [], 0.0
        timeline_clips = []
        keep = float((cfg.get("edit") or {}).get("tighten_keep") or DEFAULTS["tighten_keep"])
        apply_editor_defaults(edl, cfg)
        look = edl.get("look") or (cfg.get("edit") or {}).get("look")
        for n, c in enumerate(edl["clips"]):
            c["_look"] = None if c["still"] else look
            src_w, src_h = display_size(c["vstream"])
            focus = c.get("focus", "auto" if (src_w / src_h) > (out_w / out_h) * 1.05 and not c["still"] else [0.5, 0.5])
            if focus == "auto":
                focus = auto_focus(c["path"], c["in"], c["out"])
            focus = (float(focus[0]), float(focus[1]))
            ranges = [(c["in"], c["out"])]
            if c.get("tighten") and not c["still"]:
                gaps = silences(c["path"], c["in"], c["out"], float(c["tighten"]))
                ranges = tighten_ranges(c["in"], c["out"], gaps, keep)
            for k, (a, b) in enumerate(ranges):
                seg = tmp / f"seg_{n:02d}_{k:02d}.mp4"
                render_segment(c, a, b, seg, ratio, out_w, out_h, fps, enc, focus,
                               timecode_from=t if proxy else None, font=font)
                d = duration_of(seg)
                timeline_clips.append({"src": c["src"], "src_in": round(a, 3), "src_out": round(b, 3),
                                       "at": round(t, 3), "duration": round(d, 3), "focus": [round(focus[0], 3), round(focus[1], 3)],
                                       "zoom": c.get("zoom") or 1.0, "push": c.get("push")})
                t += d
                segments.append(seg)
        card = edl.get("end_card")
        if card and not proxy:
            seg = tmp / "end_card.mp4"
            if plates_available(cfg):
                render_end_card_html(card, seg, out_w, out_h, fps, enc, cfg, tmp)
            else:
                render_end_card({**card, "_ratio": ratio}, seg, out_w, out_h, fps, enc, cfg, font, tmp)
            timeline_clips.append({"src": "end_card", "at": round(t, 3), "duration": round(duration_of(seg), 3)})
            t += duration_of(seg)
            segments.append(seg)
        edl["_timeline_clips"] = timeline_clips
        aroll = tmp / "aroll.mp4"
        concat(segments, aroll, tmp)
        total = duration_of(aroll)

        comp = tmp / "comp.mov"
        timeline = composite(aroll, edl, comp, out_w, out_h, fps, total, cfg, font, tmp, enc, proxy)

        if proxy:
            out = exports / f"{edl['name']}_proxy.mp4"
            run_ffmpeg(["-i", str(comp), "-c:v", "copy", *AUD_ENC, "-movflags", "+faststart", str(out)])
            print(f"Proxy: {out} ({total:.2f}s)")
            return out

        audio_cfg = cfg.get("audio") or {}
        target, tp_max = float(audio_cfg.get("target_lufs", -14)), float(audio_cfg.get("true_peak_max_dbtp", -1.0))
        # Aim the true peak 0.5 dB under the ceiling: AAC encoding adds up to about 0.3 dB of overshoot,
        # and QA measures the encoded file against the ceiling itself.
        tp = tp_max - TP_HEADROOM_DB
        lf = loudnorm_filter(measure_loudnorm(comp, target, tp), target, tp) + f",alimiter=limit={10 ** (tp / 20):.4f}:level=false:attack=2:release=50"

        master = cuts / f"{edl['name']}_master.mp4"
        finalize(comp, master, lf, None, ROOT / "brand" / "fonts", ENC_INTER, fps)
        print(f"Master (no captions): {master} ({total:.2f}s, {out_w}x{out_h}@{fps})")

        words = None
        if captions_arg == "auto":
            words = transcribe_master(master, batch_dir / "work" / "transcripts")
            if words is None:
                print("No transcription backend available (mlx-whisper / faster-whisper / openai-whisper). "
                      f"Transcribe the master elsewhere, then re-run with --captions <words.json>.")
        elif captions_arg:
            words = Path(captions_arg)
            if not words.exists():
                raise SystemExit(f"{words} not found")
        if words is None:
            if captions_arg is None:
                print("Next: .venv/bin/python tools/transcribe.py", master, "--out", batch_dir / "work" / "transcripts",
                      "\n      then re-run with --captions", batch_dir / "work" / "transcripts" / f"{master.stem}.words.json")
            return master

        final = exports / f"{edl['name']}.mp4"
        ccfg = cfg.get("captions") or {}
        cap_engine = str(edl.get("caption_engine") or ccfg.get("engine") or "html")
        if cap_engine == "html" and plates_available(cfg):
            cap_mov = cuts / f"{edl['name']}_captions.mov"
            pages = build_caption_plate(words, out_w, out_h, total, fps, cap_mov, cfg, edl)
            (cuts / f"{edl['name']}.captions.json").write_text(json.dumps(pages, indent=1))
            finalize_with_plate(comp, final, lf, cap_mov, ENC_FINAL, fps)
            timeline["captions"] = {"words_json": str(words), "plate": str(cap_mov), "pages": str(cuts / f"{edl['name']}.captions.json"),
                                    "engine": "html", "style": str(edl.get("caption_style") or ccfg.get("style") or "pill")}
        else:
            ass = cuts / f"{edl['name']}.ass"
            build_captions(words, out_w, out_h, ass, cfg, edl)
            log = finalize(comp, final, lf, ass, ROOT / "brand" / "fonts", ENC_FINAL, fps)
            if re.search(r"fontselect|Using default font|font.*not found", log, re.I):
                print("WARNING: libass could not load the caption font; check brand/fonts and business.caption_font_name:\n" + log)
            timeline["captions"] = {"words_json": str(words), "ass": str(ass), "engine": "ass",
                                    "style": str(edl.get("caption_style") or ccfg.get("style") or "chunk")}
        (exports / f"{edl['name']}.render.json").write_text(json.dumps(timeline, indent=1))
        print(f"Final: {final} ({total:.2f}s, {out_w}x{out_h}@{fps}); sidecar {exports / (edl['name'] + '.render.json')}")
        return final
    finally:
        if keep_tmp:
            print(f"Kept intermediates in {tmp}")
            tmp_ctx._finalizer.detach()  # noqa: SLF001
        else:
            tmp_ctx.cleanup()


def storyboard(edl_path: Path, ratio: str | None) -> Path:
    """The plan before the build: every graphic at 40% of its life over the clip it sits on, tiled with timecodes."""
    import plates as pl  # noqa: WPS433
    from PIL import Image, ImageDraw

    cfg = load_config()
    edl = load_edl(edl_path, ratio)
    batch_dir = batch_dir_of(edl_path)
    for c in edl["clips"] + (edl.get("broll") or []):
        info = probe(c["path"])
        c["vstream"], c["astream"] = video_stream(info), audio_stream(info)
    fw, fh = display_size(edl["clips"][0]["vstream"])
    cw, *_ = crop_box(fw, fh, edl["ratio"], (0.5, 0.5), 1.0)
    out_w, out_h = pick_resolution(edl["ratio"], cw)
    tl = timeline_of(edl_path, ratio)
    for b in edl.get("broll") or []:
        if b.get("pip") and b.get("still"):
            b["_html_pip"] = True
    specs = plate_specs(edl, cfg)
    tmp = batch_dir / "work" / "storyboard_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    def frame_at(t: float) -> Image.Image:
        seg = next((c for c in tl if c["at"] <= t < c["at"] + c["duration"] and c["src"] != "end_card"), None)
        if seg is None:
            return Image.new("RGB", (out_w, out_h), (59, 150, 246))
        clip = next(c for c in edl["clips"] if c["src"] == seg["src"])
        src_t = seg["src_in"] + (t - seg["at"])
        png = tmp / "f.png"
        sw, sh = display_size(clip["vstream"])
        bw, bh, bx, by = crop_box(sw, sh, edl["ratio"], (0.5, 0.42), float(clip.get("zoom") or 1.0))
        args = ["-loop", "1", "-t", "0.1", "-i", str(clip["path"])] if clip["still"] else ["-ss", f"{src_t:.3f}", "-i", str(clip["path"])]
        run_ffmpeg([*args, "-frames:v", "1", "-vf", f"crop={bw}:{bh}:{bx}:{by},scale={out_w}:{out_h}", str(png)])
        return Image.open(png).convert("RGB")

    tiles = []
    r = pl.Renderer(out_w, out_h)
    try:
        for sp in specs:
            t = float(sp["at"]) + min(0.6, float(sp["duration"]) * 0.4)
            base = frame_at(t)
            still = tmp / "p.png"
            r.render_still(pl.build_html(sp, out_w, out_h, cfg), min(0.6, float(sp["duration"]) * 0.4), still)
            base.paste(Image.open(still).convert("RGBA"), (0, 0), Image.open(still).convert("RGBA"))
            tiles.append((f"{t:.1f}s {sp['type']}", base))
    finally:
        r.close()
    for seg in tl:
        if seg["src"] != "end_card":
            tiles.append((f"{seg['at']:.1f}s clip {Path(seg['src']).name}", frame_at(seg["at"] + 0.05)))
    tiles.sort(key=lambda x: float(x[0].split("s")[0]))
    tw = 360
    th = round(out_h * tw / out_w)
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 30) + 8), (32, 34, 40))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(tiles):
        x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 30)
        sheet.paste(im.resize((tw, th)), (x, y + 22))
        d.text((x, y + 4), label, fill=(230, 230, 230))
    out = batch_dir / "work" / f"storyboard_{edl['name']}.png"
    sheet.save(out)
    import shutil as _sh
    _sh.rmtree(tmp, ignore_errors=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl", nargs="?", help="EDL yaml")
    ap.add_argument("--ratio", help="override the EDL ratio: 9:16, 4:5 or 1:1")
    ap.add_argument("--all-ratios", action="store_true",
                    help="render every ratio in config batch_defaults.aspect_ratios; the timeline is identical, so the "
                         "first master is transcribed once and its words are reused for the other ratios")
    ap.add_argument("--captions", help="'auto' to transcribe the master, or a path to a words.json")
    ap.add_argument("--proxy", action="store_true", help="fast 540 px rough cut with timecode, no music or graphics")
    ap.add_argument("--out-dir", help="override the output folder")
    ap.add_argument("--keep-tmp", action="store_true", help="keep intermediate files for debugging")
    ap.add_argument("--storyboard", action="store_true",
                    help="no render: one still per graphic plus the first frame of every clip, tiled into work/storyboard_<name>.png")
    ap.add_argument("--example", action="store_true", help="print an example EDL and exit")
    args = ap.parse_args()
    if args.example:
        print(edl_example(), end="")
        return 0
    if not args.edl:
        ap.error("edl is required (or --example)")
    out_dir = Path(args.out_dir) if args.out_dir else None
    if args.storyboard:
        print(storyboard(Path(args.edl), args.ratio))
        return 0
    if not args.all_ratios:
        render(Path(args.edl), args.ratio, args.captions, args.proxy, args.keep_tmp, out_dir)
        return 0
    ratios = [str(r) for r in ((load_config().get("batch_defaults") or {}).get("aspect_ratios") or ["9:16", "4:5"])]
    captions_arg = args.captions
    for ratio in ratios:
        out = render(Path(args.edl), ratio, captions_arg, args.proxy, args.keep_tmp, out_dir)
        if captions_arg == "auto" and not args.proxy:
            # Reuse the first ratio's transcript: same cuts, same timeline, same words.
            sidecar = out.parent / f"{out.stem}.render.json"
            if sidecar.exists():
                captions_arg = json.loads(sidecar.read_text()).get("captions", {}).get("words_json") or captions_arg
    return 0


if __name__ == "__main__":
    sys.exit(main())
