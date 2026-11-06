"""Motion plates: browser-rendered graphics with real easing, composited over the cut.

Each plate is an HTML template (tools/plates/*.html) filled from a small spec, rendered
frame by frame in headless Chromium with a transparent background, and encoded as a
ProRes 4444 .mov (alpha preserved) that tools/render.py overlays at the right time.
Every template shares tools/plates/theme.css, so one change restyles every graphic.

Plate types:
    label        rounded callout, dark / light / accent, optional emoji
    stat         big number counting up with a label ("140 reviews")
    compare      two bars growing with values ("You: 9" vs "Them: 140")
    card         title plus up to 5 ticked lines appearing one by one
    pip          screenshot or photo in a rounded frame (optional phone bezel), slow zoom
    lower_third  name tag sliding in from the left
    hook         headline on frame 1 (instant on, animated off)
    endcard      brand background, logo pop, headline, pulsing CTA button, subtext
    captions     word-timed captions: pill (spoken word in an accent pill), highlight, clean

Usage:
    .venv/bin/python tools/plates.py render spec.yaml --size 1080x1920 --out plate.mov
    .venv/bin/python tools/plates.py still spec.yaml --size 1080x1920 --at 0.6 --out frame.png
    .venv/bin/python tools/plates.py demo --size 1080x1920 --out work/plates_demo   # one still per type
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, ffmpeg, find_font, load_config, load_yaml, ratio_of, safe_box  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent / "plates"
SIZES = {  # font size as a fraction of frame height
    "label": 0.046, "stat": 0.11, "compare": 0.044, "card": 0.042, "pip": 0.03,
    "lower_third": 0.034, "hook": 0.046, "endcard": 0.056, "captions": 0.044,
}
ENTRANCE_SFX = {"label": "pop", "stat": "ding", "compare": "whoosh", "card": "pop", "pip": "whoosh",
                "lower_third": "click", "hook": None, "endcard": "riser", "captions": None}
REGION = {"top": "top", "center": "center", "lower": "lower"}


def chromium_path() -> str | None:
    env = os.environ.get("AD_CHROMIUM")
    if env and Path(env).exists():
        return env
    for p in ("/opt/pw-browsers/chromium",):
        if Path(p).exists():
            return p
    return None


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def emph(s: str) -> str:
    """*word* -> accent <em>word</em> (used by hook and endcard headlines)."""
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", esc(s))


def data_uri(path: str | Path | None, mime: str | None = None) -> str:
    """Inline a file as a data URI. Headless pages built from a string cannot always read file:// URLs."""
    import base64
    import mimetypes

    if not path:
        return ""
    p = Path(path)
    mime = mime or mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


_FONT_CACHE: dict[str, str] = {}


def font_uri(name: str) -> str:
    if name not in _FONT_CACHE:
        path, _ = find_font(name)
        _FONT_CACHE[name] = data_uri(path, "font/ttf") if path else ""
    return _FONT_CACHE[name]


def theme(width: int, height: int, duration: float, cfg: dict) -> str:
    ratio = ratio_of(width, height) or "9:16"
    box = safe_box(width, height, ratio)
    biz = cfg.get("business") or {}
    colors = biz.get("brand_colors") or {}
    heavy = font_uri(biz.get("caption_font_name") or "Montserrat ExtraBold")
    bold = font_uri("Montserrat Bold") or heavy
    css = (TEMPLATES / "theme.css").read_text()
    for k, v in {
        "font_url": heavy, "font_bold_url": bold,
        "primary": colors.get("primary", "#3B96F6"), "accent": colors.get("accent", "#E55B13"),
        "width": width, "height": height, "safe_top": box["top"], "safe_bottom": box["bottom"], "safe_side": box["side"],
        "duration": f"{duration:.3f}",
    }.items():
        css = css.replace("{{" + k + "}}", str(v))
    return css


def fill(name: str, values: dict) -> str:
    t = (TEMPLATES / f"{name}.html").read_text()
    values = {**values, "harness": (TEMPLATES / "harness.js").read_text()}
    for k, v in values.items():
        t = t.replace("{{" + k + "}}", str(v))
    return re.sub(r"\{\{[a-z_]+\}\}", "", t)


def region_of(spec: dict) -> str:
    """Where the plate sits, for QA (face overlap) and the sidecar."""
    kind = spec["type"]
    if kind in ("hook",):
        return "top"
    if kind in ("lower_third", "captions"):
        return "lower"
    if kind in ("endcard",):
        return "full"
    pos = str(spec.get("position") or "center")
    return pos if pos in REGION else "center"


def pos_class(spec: dict) -> tuple[str, str]:
    pos = str(spec.get("position") or "center")
    if pos in REGION:
        return f"pos-{pos}", ""
    try:
        y = float(pos)
        return "", f"top: {y * 100:.1f}%;"
    except ValueError:
        return "pos-center", ""


def build_html(spec: dict, width: int, height: int, cfg: dict) -> str:
    kind = spec["type"]
    duration = float(spec.get("duration") or 2.0)
    th = theme(width, height, duration, cfg)
    size = round(height * float(spec.get("size") or SIZES[kind]))
    variant = str(spec.get("variant") or ("accent" if spec.get("accent") else "dark"))
    pos, style = pos_class(spec)
    if kind == "label":
        return fill("label", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                              "text": esc(spec.get("text", "")), "emoji": esc(spec.get("emoji", ""))})
    if kind == "stat":
        return fill("stat", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                             "value": int(spec.get("value") or 0), "prefix": esc(spec.get("prefix", "")),
                             "suffix": esc(spec.get("suffix", "")), "label": esc(spec.get("label", ""))})
    if kind == "compare":
        left, right = spec.get("left") or {}, spec.get("right") or {}
        lv, rv = float(left.get("value") or 0), float(right.get("value") or 0)
        mx = max(lv, rv, 1)
        return fill("compare", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                                "title": esc(spec.get("title", "")), "left_label": esc(left.get("label", "")),
                                "right_label": esc(right.get("label", "")), "left_value": esc(left.get("display", left.get("value", ""))),
                                "right_value": esc(right.get("display", right.get("value", ""))),
                                "left_pct": round(100 * lv / mx), "right_pct": round(100 * rv / mx), "note": esc(spec.get("note", ""))})
    if kind == "card":
        items = [str(x) for x in (spec.get("items") or [])][:5]
        items_html = "".join(f'<div class="item" style="animation-delay:{0.35 + i * 0.28:.2f}s"><div class="tick">&#10003;</div><div>{esc(x)}</div></div>'
                             for i, x in enumerate(items))
        return fill("card", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                             "title": esc(spec.get("title", "")), "items_html": items_html})
    if kind == "pip":
        from PIL import Image

        src = Path(spec["src"]).resolve()
        with Image.open(src) as im:
            iw, ih = im.size
        device = "phone" if spec.get("device") == "phone" else ""
        frac = float(spec.get("w") or (0.58 if device else 0.78))
        frame_w = round(width * frac)
        frame_h = round(frame_w * ih / iw) + (28 if device else 0)
        cy = float(spec.get("y") or 0.42)
        top = round(cy * height - frame_h / 2)
        top = max(safe_box(width, height, ratio_of(width, height) or "9:16")["top"], top)
        caption = spec.get("caption")
        cap_html = (f'<div class="cap dark" style="top:{top + frame_h}px">{esc(caption)}</div>' if caption else "")
        return fill("pip", {"theme": th, "size": size, "frame_w": frame_w, "frame_radius": 36, "device": device,
                            "src": data_uri(src), "top": top, "zoom": float(spec.get("zoom") or 1.06),
                            "origin": str(spec.get("origin") or "50% 40%"), "caption_html": cap_html})
    if kind == "lower_third":
        return fill("lower_third", {"theme": th, "size": size, "text": esc(spec.get("text", "")), "sub": esc(spec.get("sub", ""))})
    if kind == "hook":
        return fill("hook", {"theme": th, "size": size, "variant": variant, "text": emph(spec.get("text", ""))})
    if kind == "endcard":
        logo = ROOT / "brand" / "logo.png"
        logo_html = f'<img class="logo" src="{data_uri(logo)}">' if (spec.get("logo", True) and logo.exists()) else ""
        return fill("endcard", {"theme": th, "size": size, "logo_html": logo_html, "headline": emph(spec.get("headline", "")),
                                "text": esc(spec.get("text", "Tap Learn More")), "subtext": esc(spec.get("subtext", ""))})
    if kind == "captions":
        return captions_html(spec, th, size)
    raise SystemExit(f"unknown plate type {kind!r}; see tools/plates.py")


def captions_html(spec: dict, th: str, size: int) -> str:
    """Word-timed caption pages from a words.json list. Styles: pill, highlight, clean."""
    import captions as cap  # noqa: WPS433

    words = spec["words"]
    style = str(spec.get("style") or "pill")
    keywords = {k.lower() for k in (spec.get("keywords") or [])}
    chunks = cap.chunk(words, int(spec.get("max_words") or 4))
    pages = []
    for n, c in enumerate(chunks):
        start, end = c[0]["start"], cap.page_end(chunks, n)
        k = cap.pick_keyword(c, keywords) if style != "pill" else None
        spans = []
        for i, w in enumerate(c):
            w_start = w["start"] if i else start
            w_end = c[i + 1]["start"] if i + 1 < len(c) else end
            cls = "w on" + (" key" if i == k else "")
            spans.append(f'<span class="{cls}" style="animation-delay:{w_start:.3f}s;--wlen:{max(0.05, w_end - w_start):.3f}s">{esc(w["word"])}</span>')
        pages.append(f'<div class="page" style="animation-delay:{start:.3f}s;--len:{max(0.05, end - start):.3f}s">'
                     f'<div class="inner" style="animation-delay:{start:.3f}s">{" ".join(spans)}</div></div>')
    return fill("captions", {"theme": th, "size": size, "style": style, "uc": "uc" if spec.get("uppercase") else "",
                             "pages_html": "\n".join(pages)})


class Renderer:
    """One headless browser for many plates."""

    def __init__(self, width: int, height: int):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        kwargs = {"args": ["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"]}
        path = chromium_path()
        if path:
            kwargs["executable_path"] = path
        self.browser = self._pw.chromium.launch(**kwargs)
        self.page = self.browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        self.width, self.height = width, height

    def load(self, html_text: str) -> None:
        # A fresh page per plate: Chromium sometimes stops painting static text on a reused page after
        # several documents with paused animations (verified), and a new page costs about 50 ms.
        old = self.page
        self.page = self.browser.new_page(viewport={"width": self.width, "height": self.height}, device_scale_factor=1)
        old.close()
        self.page.set_content(html_text, wait_until="load")
        # Fonts load lazily and text is invisible while a font is pending, so force every face to load first.
        self.page.evaluate("""async () => {
            try { await Promise.all([document.fonts.load('800 40px Brand'), document.fonts.load('700 40px Brand')]); } catch (e) {}
            await document.fonts.ready;
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        }""")
        if not self.page.evaluate("document.fonts.check('800 40px Brand')"):
            print("WARNING: brand font did not load in the plate renderer; check brand/fonts")

    def frame(self, t: float) -> bytes:
        self.page.evaluate(f"window.__seek({t:.4f})")
        return self.page.screenshot(type="png", omit_background=True)

    def render_mov(self, html_text: str, duration: float, fps: int, out: Path) -> Path:
        self.load(html_text)
        n = max(1, int(round(duration * fps)))
        out.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([ffmpeg(), "-nostdin", "-hide_banner", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps),
                                 "-c:v", "png", "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                                 "-video_track_timescale", "90000", str(out)], stdin=subprocess.PIPE)
        for i in range(n):
            proc.stdin.write(self.frame(i / fps))
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed encoding plate {out}")
        return out

    def render_still(self, html_text: str, t: float, out: Path) -> Path:
        self.load(html_text)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(self.frame(t))
        return out

    def close(self) -> None:
        self.browser.close()
        self._pw.stop()


def demo_specs() -> list[dict]:
    img = ROOT / "tools" / "models" / "README.md"  # placeholder replaced below
    return [
        {"type": "hook", "text": "Huntsville roofers:\n*9 reviews* vs 140?", "duration": 3},
        {"type": "label", "text": "A review request goes out", "emoji": "", "position": "top", "duration": 2.2},
        {"type": "label", "text": "$4,800 job (example)", "accent": True, "duration": 2},
        {"type": "stat", "value": 140, "suffix": " reviews", "label": "your competitor (example)", "duration": 2.5},
        {"type": "compare", "title": "Same work. Different phone.", "left": {"label": "You", "value": 9}, "right": {"label": "The other guy", "value": 140},
         "note": "Google reviews (example numbers)", "duration": 3},
        {"type": "card", "title": "You get", "items": ["Review requests sent for you", "Replies written for you", "Monthly report by text"], "duration": 3},
        {"type": "lower_third", "text": "Bruce", "sub": "AuburnSEO, Auburn AL", "duration": 3},
        {"type": "endcard", "headline": "More reviews.\nMore calls.", "text": "Tap Learn More", "subtext": "Huntsville contractors", "duration": 2.5},
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("render", "still", "demo"))
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--at", type=float, default=0.6, help="seconds into the plate for a still")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    width, height = (int(x) for x in args.size.lower().split("x"))
    cfg = load_config()
    r = Renderer(width, height)
    try:
        if args.cmd == "demo":
            out_dir = Path(args.out)
            for i, spec in enumerate(demo_specs()):
                r.render_still(build_html(spec, width, height, cfg), min(args.at, float(spec["duration"]) * 0.4), out_dir / f"{i:02d}_{spec['type']}.png")
            print(f"Wrote demo stills to {out_dir}")
            return 0
        spec = load_yaml(Path(args.spec)) if args.spec.endswith((".yaml", ".yml")) else json.loads(Path(args.spec).read_text())
        if spec.get("type") == "captions" and isinstance(spec.get("words"), str):
            spec["words"] = json.loads(Path(spec["words"]).read_text())
        h = build_html(spec, width, height, cfg)
        if args.cmd == "still":
            print(r.render_still(h, args.at, Path(args.out)))
        else:
            print(r.render_mov(h, float(spec.get("duration") or 2.0), args.fps, Path(args.out)))
        return 0
    finally:
        r.close()


if __name__ == "__main__":
    sys.exit(main())
