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
    captions     word-timed captions: pill (spoken word in an accent pill), highlight, clean, box, word
    words        words landing one at a time at their own sizes, on paper / dark / nothing (reference 4)
    fan          cards spread in an arc over the head (images or text, view-count badges), or a scatter swarm
    steps        numbered checklist that completes itself row by row with progress pills
    timer        running clock in a dark card with a red label, optional note pill
    quote        a real comment or review as a plain white card (avatar initials, name, time, text)
    files        grid of document icons with a badge letter, label and sub line
    tracks       rows of labelled blocks (timeline or schedule) with a bright window and share label
    bezel        phone or browser frame drawn around a video inset ffmpeg placed
    toast        small white notice card with an optional title and dot

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
    "step": 0.04, "grid": 0.05, "before_after": 0.08, "chips": 0.042, "frame_label": 0.026,
    "takeover": 0.14, "strike": 0.046, "progress": 0.0, "backdrop": 0.0, "words": 0.075, "toast": 0.03,
    "fan": 0.03, "steps": 0.03, "timer": 0.06, "quote": 0.034, "files": 0.024, "tracks": 0.026, "bezel": 0.0,
}
ENTRANCE_SFX = {"label": "pop", "stat": "ding", "compare": "pop", "card": "pop", "pip": "pop",
                "lower_third": "click", "hook": None, "endcard": "riser", "captions": None,
                "step": "click", "grid": "pop", "before_after": "thud", "chips": "click", "frame_label": "click",
                "takeover": "thud", "strike": "pop", "progress": None, "backdrop": None, "words": "click", "toast": "pop",
                "fan": "swipe", "steps": "click", "timer": "click", "quote": "pop", "files": "pop", "tracks": "click", "bezel": None}
REGION = {"top": "top", "center": "center", "lower": "lower"}
PAPER_BG = "#f3f0ea"    # cream dotted-grid sheet (reference 4)
PAPER_INK = "#4a1c1c"   # the deep maroon type on it


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
    cap_font = (cfg.get("captions") or {}).get("font_name")
    caption = font_uri(cap_font) if cap_font else heavy
    css = (TEMPLATES / "theme.css").read_text()
    for k, v in {
        "font_url": heavy, "font_bold_url": bold, "caption_font_url": caption or heavy,
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
    if kind in ("hook", "step"):
        return "top"
    if kind in ("lower_third", "captions"):
        return "lower"
    if kind in ("endcard", "frame_label", "takeover", "progress", "backdrop", "words", "bezel"):
        return "full"
    if kind in ("fan", "steps", "files", "tracks"):
        return "top"
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
        text = str(spec.get("text", ""))
        if variant == "boxes":
            words = []
            for i, w in enumerate(text.split()):
                acc = w.startswith("*") and w.endswith("*") and len(w) > 2
                words.append(f'<span class="bw{" acc" if acc else ""}" style="animation-delay:{0.06 * i:.2f}s">{esc(w.strip("*"))}</span>')
            body = "".join(words)
        else:
            body = emph(text)
        return fill("label", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                              "text": body, "emoji": esc(spec.get("emoji", ""))})
    if kind == "stat":
        thumbs = spec.get("thumbs") or []
        thumbs_html = ('<div class="thumbs">' + "".join(f'<img src="{data_uri(t)}" style="animation-delay:{0.3 + 0.12 * i:.2f}s">'
                                                        for i, t in enumerate(thumbs[:4])) + "</div>") if thumbs else ""
        value = float(spec.get("value") or 0)
        return fill("stat", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                             "value": value, "decimals": 1 if value != int(value) else 0, "prefix": esc(spec.get("prefix", "")),
                             "suffix": esc(spec.get("suffix", "")), "label": esc(spec.get("label", "")), "thumbs_html": thumbs_html})
    if kind == "step":
        return fill("step", {"theme": th, "size": size, "variant": variant, "pos": pos or "pos-top", "style": style,
                             "number": esc(spec.get("number", "")), "text": esc(spec.get("text", ""))})
    if kind == "grid":
        images = list(spec.get("images") or [])
        cols = int(spec.get("cols") or min(6, max(3, round(len(images) ** 0.5 * 1.3))))
        cells = "".join(f'<div class="cell" style="animation-delay:{0.08 * i:.2f}s"><img src="{data_uri(im)}"><span class="tag">{esc(spec.get("tag", "cut"))} {i + 1}</span></div>'
                        for i, im in enumerate(images))
        return fill("grid", {"theme": th, "size": size, "pos": pos or "pos-center", "cols": cols, "cells_html": cells,
                             "count": esc(spec.get("count", len(images))), "text": esc(spec.get("text", "")),
                             "head_delay": f"{0.08 * len(images) + 0.1:.2f}"})
    if kind == "before_after":
        import random

        rnd = random.Random(7)
        bars = "".join(f'<i style="height:{rnd.randint(18, 100)}%;animation-delay:{0.15 + 0.012 * i:.3f}s"></i>' for i in range(42))
        good = spec.get("good", "to")   # which side is the improvement; colors the "to" value
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        accent = colors.get("accent", "#E55B13")
        return fill("before_after", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                                     "label": esc(spec.get("label", "")), "from": esc(spec.get("from", "")), "to": esc(spec.get("to", "")),
                                     "sub": esc(spec.get("sub", "")), "bars_html": bars,
                                     "tag_color": "#d12d3a" if spec.get("bad") else accent,
                                     "wave_color": "#2fd27a" if good == "to" else accent, "to_color": "#2fd27a" if good == "to" else accent})
    if kind == "chips":
        items = spec.get("items") or []
        cols = int(spec.get("cols") or min(3, len(items)) or 1)
        chips = []
        for i, it in enumerate(items[:9]):
            if isinstance(it, dict):
                b, sm = it.get("text", ""), it.get("sub", "")
            else:
                b, sm = str(it), ""
            ck = '<span class="ck">&#10003;</span>' if (isinstance(it, dict) and it.get("check")) else ""
            chips.append(f'<div class="chip" style="animation-delay:{0.25 + 0.12 * i:.2f}s">{ck}<b>{esc(b)}</b>' + (f"<small>{esc(sm)}</small>" if sm else "") + "</div>")
        return fill("chips", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style, "cols": cols,
                              "title": emph(spec.get("title", "")).replace("<em>", '<span class="acc">').replace("</em>", "</span>"),
                              "chips_html": "".join(chips)})
    if kind == "takeover":
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        bg_key = str(spec.get("bg") or "dark")
        bg = {"dark": "#0f1115", "primary": colors.get("primary", "#3B96F6"), "accent": colors.get("accent", "#E55B13"),
              "light": "#f5f5f7", "paper": PAPER_BG, "none": "transparent"}.get(bg_key, bg_key)
        color = str(spec.get("color") or {"light": "#0f1115", "paper": PAPER_INK}.get(bg_key, "#ffffff"))
        return fill("takeover", {"theme": th, "size": size, "bg": bg, "color": color, "text": emph(spec.get("text", "")),
                                 "sub": esc(spec.get("sub", "")), "dots_html": '<div class="dots"></div>' if bg_key == "paper" else ""})
    if kind == "strike":
        items = [str(x) for x in (spec.get("items") or [])][:5]
        rows = "".join(f'<div class="row dead" style="animation-delay:{0.2 + 0.3 * i:.2f}s">{esc(x)}<i style="animation-delay:{0.2 + 0.3 * len(items) + 0.22 * i:.2f}s"></i></div>'
                       for i, x in enumerate(items))
        return fill("strike", {"theme": th, "size": size, "variant": variant, "pos": pos, "style": style,
                               "title": esc(spec.get("title", "")), "rows_html": rows, "answer": esc(spec.get("answer", "")),
                               "answer_delay": f"{0.2 + 0.3 * len(items) + 0.22 * len(items) + 0.25:.2f}"})
    if kind == "progress":
        return fill("progress", {"theme": th})
    if kind == "backdrop":
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        style = str(spec.get("style") or "navy")
        bg, bg2 = ("#0b1020", "#141c33") if style != "paper" else (PAPER_BG, PAPER_BG)
        return fill("backdrop", {"theme": th, "bg": str(spec.get("bg") or bg), "bg2": str(spec.get("bg2") or bg2),
                                 "glow": colors.get("primary", "#3B96F6"), "style": style})
    if kind == "words":
        # Words land one at a time over the first 70% of the plate, each at its own size, like a thought being typed.
        words = [str(w) for w in (spec.get("words") or str(spec.get("text", "")).split())][:12]
        n = max(1, len(words))
        window = duration * 0.7 if not spec.get("step") else float(spec["step"]) * n
        scales = [1.0, 1.45, 0.85, 1.25, 1.0, 1.6, 0.9, 1.3]
        parts = []
        for i, w in enumerate(words):
            delay = (window / n) * i
            parts.append(f'<span class="wd" style="font-size:{round(size * scales[i % len(scales)])}px;animation-delay:{delay:.3f}s">{emph(w)}</span>')
        bg_key = str(spec.get("bg") or "paper")
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        bg = {"paper": PAPER_BG, "dark": "#0f1115", "none": "transparent", "primary": colors.get("primary", "#3B96F6")}.get(bg_key, bg_key)
        color = str(spec.get("color") or {"paper": PAPER_INK, "dark": "#ffffff", "none": "#ffffff"}.get(bg_key, "#ffffff"))
        chip = spec.get("chip")
        chip_html = f'<div class="chip"><span class="dot"></span>{esc(chip)}</div>' if chip else ""
        return fill("words", {"theme": th, "size": size, "bg": bg, "color": color, "words_html": " ".join(parts), "chip_html": chip_html,
                              "chip_delay": f"{window + 0.1:.3f}", "dots_html": '<div class="dots"></div>' if bg_key == "paper" else ""})
    if kind == "fan":
        import math as _m
        items = list(spec.get("images") or spec.get("cards") or [])
        scatter = bool(spec.get("scatter"))
        n = max(1, len(items))
        spread = float(spec.get("spread") or min(110, 26 * n))
        radius = height * float(spec.get("radius") or 0.21)
        cy = round(height * float(spec.get("y") or 0.42))
        cards = []
        seed = 7
        for i, it in enumerate(items[:40 if scatter else 9]):
            if scatter:
                seed = (seed * 1103515245 + 12345) % (2 ** 31)
                ang, r, rot = (seed % 360), height * (0.08 + 0.34 * ((seed >> 8) % 1000) / 1000), ((seed >> 16) % 80) - 40
            else:
                ang = -spread / 2 + spread * (i / max(1, n - 1)) if n > 1 else 0.0
                r, rot = -radius, 0.0
            if isinstance(it, dict):
                src, text, badge, dark = it.get("src"), it.get("text"), it.get("badge"), it.get("dark")
            elif str(it).lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".heic")):
                src, text, badge, dark = str(it), None, None, False
            else:
                src, text, badge, dark = None, str(it), None, False
            inner = f'<img src="{data_uri(src)}">' if src else f'<div class="txt">{emph(text or "")}</div>'
            if badge:
                inner += f'<div class="badge">{esc(badge)}</div>'
            delay = 0.05 * i if not scatter else 0.02 * i
            cards.append(f'<div class="c {"dark" if dark else ""}" style="--th:{ang:.1f}deg;--r:{r:.0f}px;--rot:{rot:.1f}deg;z-index:{100 - abs(int(ang))};animation-delay:{delay:.2f}s">{inner}</div>')
        return fill("fan", {"theme": th, "size": size, "cy": cy, "card_w": round(width * float(spec.get("w") or 0.27)),
                            "chip_w": round(width * 0.17), "mode": "scatter" if scatter else "", "cards_html": "".join(cards)})
    if kind == "steps":
        items = [it if isinstance(it, dict) else {"text": str(it)} for it in (spec.get("items") or [])][:10]
        n = max(1, len(items))
        step = float(spec.get("step") or (duration * 0.82 / n))
        rows = []
        for i, it in enumerate(items):
            thumb = f'<div class="thumb"><img src="{data_uri(it["image"])}"></div>' if it.get("image") else ""
            rows.append(f'<div class="row" style="animation-delay:{0.06 * i:.2f}s"><span class="n">{i + 1}</span><span class="t">{esc(it.get("text", ""))}</span>{thumb}<span class="bar"><i></i></span></div>')
        title = f'<div class="title">{esc(spec["title"])}</div>' if spec.get("title") else ""
        top = round(height * float(spec.get("y") or 0.07))
        return fill("steps", {"theme": th, "size": size, "top": top, "title_html": title, "rows_html": "".join(rows),
                              "step": f"{step:.3f}", "start": f"{float(spec.get('start') or 0.3):.3f}"})
    if kind == "timer":
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        note = spec.get("note")
        note_html = ""
        if note:
            when = esc(spec.get("note_time") or "")
            note_html = f'<div class="note {pos or "pos-center"}" style="{style}"><span class="dot"></span>' + (f"<b>{when}</b>" if when else "") + f"{esc(note)}</div>"
        return fill("timer", {"theme": th, "size": size, "pos": pos or "pos-center", "style": style, "label": esc(spec.get("label", "time spent")),
                              "color": str(spec.get("color") or "#ff4d4d"), "from": f"{float(spec.get('from') or 0):.1f}",
                              "rate": f"{float(spec.get('rate') or 60):.2f}", "note_html": note_html})
    if kind == "quote":
        name = str(spec.get("name") or "Customer")
        avatar = f'<img src="{data_uri(spec["avatar"])}">' if spec.get("avatar") else esc("".join(w[0] for w in name.split()[:2]).upper())
        foot = []
        if spec.get("likes") is not None:
            foot.append(f'<span><span class="heart">&#9829;</span> {esc(str(spec["likes"]))}</span>')
        if spec.get("source"):
            foot.append(f"<span>{esc(spec['source'])}</span>")
        return fill("quote", {"theme": th, "size": size, "pos": pos or "pos-center", "style": style, "avatar": avatar, "name": esc(name),
                              "when": esc(spec.get("when") or ""), "text": emph(spec.get("text", "")), "foot_html": "".join(foot)})
    if kind == "files":
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        items = [it if isinstance(it, dict) else {"label": str(it)} for it in (spec.get("items") or [])][:12]
        cols = int(spec.get("cols") or (5 if len(items) > 6 else min(4, max(2, len(items)))))
        files = []
        for i, it in enumerate(items):
            files.append(f'<div class="f" style="animation-delay:{0.07 * i:.2f}s"><div class="ic"><b>{esc(str(it.get("badge") or spec.get("badge") or "A"))[:2]}</b></div>'
                         f'<div class="lbl">{esc(it.get("label", ""))}</div>' + (f'<div class="sub">{esc(str(it["sub"]))}</div>' if it.get("sub") else "") + "</div>")
        return fill("files", {"theme": th, "size": size, "cols": cols, "top": round(height * float(spec.get("y") or 0.07)),
                              "badge_bg": str(spec.get("badge_bg") or colors.get("primary", "#3B96F6")), "files_html": "".join(files)})
    if kind == "tracks":
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        palette = [colors.get("primary", "#3B96F6"), "#a56cf5", colors.get("accent", "#E55B13"), "#2ecc71", "#f5c542", "#ff5c8a"]
        rows = spec.get("rows")
        if not rows:
            rows = [{"label": "V4", "blocks": [[0.02, 0.1, "Graphic"], [0.3, 0.1, "Graphic"], [0.55, 0.08, "Graphic"], [0.8, 0.1, "Graphic"]]},
                    {"label": "V3", "blocks": [[0.08, 0.12, "B-roll"], [0.44, 0.1, "B-roll"], [0.7, 0.12, "B-roll"]]},
                    {"label": "V1", "blocks": [[0.0, 0.18, "Take 1"], [0.19, 0.22, "Take 2"], [0.42, 0.2, "Take 3"], [0.63, 0.17, "Take 4"], [0.81, 0.19, "Take 5"]]},
                    {"label": "A1", "blocks": [[0.0, 1.0, "Voice"]]},
                    {"label": "A2", "blocks": [[0.0, 0.3, "Music"], [0.32, 0.68, "Music"]]}]
        rows_html = []
        for ri, r in enumerate(rows[:7]):
            c = str(r.get("color") or palette[ri % len(palette)])
            blocks = []
            for bi, b in enumerate(r.get("blocks") or []):
                x, w = float(b[0]), float(b[1])
                lab = esc(str(b[2])) if len(b) > 2 else ""
                blocks.append(f'<div class="b" style="--c:{c};left:{x * 100:.1f}%;width:{w * 100:.1f}%;animation-delay:{0.1 + 0.04 * bi + 0.08 * ri:.2f}s"><span>{lab}</span></div>')
            rows_html.append(f'<div class="row"><div class="lab">{esc(str(r.get("label", "")))}</div><div class="lane">{"".join(blocks)}</div></div>')
        hl = spec.get("highlight")   # {from, to, label}: everything outside the window dims, the label lands in the middle
        dim_html = share_html = ""
        if hl:
            a, b = float(hl.get("from", 0)), float(hl.get("to", 0.1))
            dim_html = (f'<div class="dim" style="left:0;width:calc(3.2em + 10px + ({a * 100:.1f}% - 3.2em * {a:.3f}))"></div>' if a > 0 else "") + \
                       f'<div class="dim" style="right:0;left:calc(3.2em + 10px + {b * 100:.1f}%)"></div>'
            if hl.get("label"):
                share_html = f'<div class="share">{esc(str(hl["label"]))}</div>'
        row_h = round(height * 0.04)
        return fill("tracks", {"theme": th, "size": size, "top": round(height * float(spec.get("y") or 0.1)), "row_h": row_h,
                               "rows_html": "".join(rows_html), "dim_html": dim_html, "share_html": share_html,
                               "dim_delay": f"{float(spec.get('dim_delay') or 0.9):.2f}"})
    if kind == "bezel":
        x, y, w, h = (int(spec[k]) for k in ("x", "y", "w", "h"))
        if str(spec.get("device") or "phone") == "browser":
            frame = f'<div class="browser"><div class="bar"><i></i><i></i><i></i><span>{esc(spec.get("title") or "")}</span></div></div>'
        else:
            frame = '<div class="phone"><div class="notch"></div></div>'
        return fill("bezel", {"theme": th, "x": x, "y": y, "w": w, "h": h, "bw": max(10, round(w * 0.03)), "radius": max(24, round(w * 0.12)),
                              "bar_h": max(28, round(h * 0.07)), "frame_html": frame})
    if kind == "toast":
        colors = (cfg.get("business") or {}).get("brand_colors") or {}
        title = spec.get("title")
        title_html = f'<div class="title"><span class="dot"></span>{esc(title)}</div>' if title else ""
        return fill("toast", {"theme": th, "size": size, "pos": pos or "pos-center", "style": style, "title_html": title_html,
                              "text": esc(spec.get("text", "")), "dot": str(spec.get("dot") or colors.get("accent", "#E55B13"))})
    if kind == "frame_label":
        return fill("frame_label", {"theme": th, "size": size, "text": esc(spec.get("text", "raw footage")),
                                    "dot_color": "#ff3b30" if spec.get("rec", True) else "#2fd27a",
                                    "show_time": "true" if spec.get("timecode", True) else "false",
                                    "base_time": float(spec.get("timecode_from") or 0.0)})
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
        device = {"phone": "phone", "browser": "browser"}.get(str(spec.get("device") or ""), "cutout" if str(spec.get("style") or "") == "cutout" else "")
        frac = float(spec.get("w") or (0.58 if device else 0.78))
        frame_w = round(width * frac)
        frame_h = round(frame_w * ih / iw) + (28 if device == "phone" else (40 if device == "browser" else 0))
        cy = float(spec.get("y") or 0.42)
        top = round(cy * height - frame_h / 2)
        top = max(safe_box(width, height, ratio_of(width, height) or "9:16")["top"], top)
        caption = spec.get("caption")
        cap_html = (f'<div class="cap dark" style="top:{top + frame_h}px">{esc(caption)}</div>' if caption else "")
        stamp_html = f'<div class="stamp">{esc(spec["stamp"])}</div>' if spec.get("stamp") else ""
        hl = spec.get("highlight")   # fractions of the image: {x, y, w, h}
        hl_vals = {"hl_html": "", "hl_x": 0, "hl_y": 0, "hl_w": 0, "hl_h": 0}
        if hl:
            hl_vals = {"hl_html": '<div class="hl"></div>', "hl_x": round(frame_w * float(hl.get("x", 0.05))),
                       "hl_y": round(frame_w * ih / iw * float(hl.get("y", 0.4))), "hl_w": round(frame_w * float(hl.get("w", 0.9))),
                       "hl_h": round(frame_w * ih / iw * float(hl.get("h", 0.06)))}
        radius = spec.get("radius")
        return fill("pip", {"theme": th, "size": size, "frame_w": frame_w, "frame_radius": 36 if radius is None else int(radius), "device": device,
                            "float": "float" if spec.get("float") else "",
                            "bar_html": f'<div class="bar"><i></i><i></i><i></i><span>{esc(spec.get("title") or "")}</span></div>' if device == "browser" else "",
                            "src": data_uri(src), "top": top, "zoom": float(spec.get("zoom") or (1.0 if spec.get("highlight") else 1.06)),
                            "origin": str(spec.get("origin") or "50% 40%"), "caption_html": cap_html, "stamp_html": stamp_html,
                            "stamp_top": top + frame_h // 2, **hl_vals})
    if kind == "lower_third":
        return fill("lower_third", {"theme": th, "size": size, "text": esc(spec.get("text", "")), "sub": esc(spec.get("sub", ""))})
    if kind == "hook":
        kicker = f'<span class="kicker">{esc(spec["kicker"])}</span>' if spec.get("kicker") else ""
        sub = f'<span class="sub">{esc(spec["sub"])}</span>' if spec.get("sub") else ""
        return fill("hook", {"theme": th, "size": size, "variant": variant, "text": emph(spec.get("text", "")),
                             "uc": "uc" if spec.get("uppercase") else "", "kicker_html": kicker, "sub_html": sub})
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
    neg = {k.lower() for k in (spec.get("keywords_neg") or [])}   # costs, pain: red
    pos = {k.lower() for k in (spec.get("keywords_pos") or [])}   # wins, outcomes: green
    keywords |= neg | pos
    chunks = cap.chunk(words, 1 if style == "word" else int(spec.get("max_words") or 4))
    pages = []
    for n, c in enumerate(chunks):
        start, end = c[0]["start"], cap.page_end(chunks, n)
        k = cap.pick_keyword(c, keywords) if style != "pill" else None
        if style == "word" and c and re.sub(r"[^\w$%']", "", c[0]["word"]).lower() not in keywords:
            k = None   # one word per page: colour it only when it is a listed keyword
        if style == "box" and k is None and c:
            k = max(range(len(c)), key=lambda i: len(c[i]["word"]))   # box style always marks one word
        spans = []
        for i, w in enumerate(c):
            w_start = w["start"] if i else start
            w_end = c[i + 1]["start"] if i + 1 < len(c) else end
            cls = "w on" + (" key" if i == k else "")
            if i == k:
                plain = re.sub(r"[^\w$%']", "", w["word"]).lower()
                cls += " neg" if plain in neg else (" pos" if plain in pos else "")
            spans.append(f'<span class="{cls}" style="animation-delay:{w_start:.3f}s;--wlen:{max(0.05, w_end - w_start):.3f}s">{esc(w["word"])}</span>')
        pages.append(f'<div class="page" style="animation-delay:{start:.3f}s;--len:{max(0.05, end - start):.3f}s">'
                     f'<div class="inner" style="animation-delay:{start:.3f}s">{" ".join(spans)}</div></div>')
    high = str(spec.get("position") or "lower") == "high"
    hook_until = float(spec.get("hook_until") or 0.0)
    pages_html = "\n".join(pages)
    if high and hook_until > 0 and chunks:
        # While the hook card is up the captions stay low (the hook owns the top); they move above the head after it leaves.
        n_low = sum(1 for c in chunks if c[0]["start"] < hook_until)
        pages_html = ("\n".join(pages[:n_low]) + f'\n</div><div class="cap style-{style} {"uc" if spec.get("uppercase") else ""} high">\n'
                      + "\n".join(pages[n_low:]))
        high = False
    position = "high" if high else ("mid" if str(spec.get("position") or "") == "mid" else "")
    return fill("captions", {"theme": th, "size": size, "style": style, "uc": "uc" if spec.get("uppercase") else "",
                             "position": position, "pages_html": pages_html})


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
        {"type": "step", "number": "03", "text": "Give it a style", "duration": 2.5},
        {"type": "label", "text": "THE *MOTION* GRAPHICS", "variant": "boxes", "position": "lower", "duration": 2},
        {"type": "before_after", "label": "Dead space", "bad": True, "from": "12.5s", "to": "4.9s", "sub": "pauses removed", "duration": 2.5},
        {"type": "chips", "title": "Sound *effects*", "items": [{"text": "Pop", "sub": "pop.wav"}, {"text": "Click", "sub": "click.wav"}, {"text": "Thud", "sub": "thud.wav"},
                                                               {"text": "Ding", "sub": "ding.wav"}, {"text": "Swipe", "sub": "swipe.wav"}, {"text": "Sub", "sub": "sub.wav"}], "duration": 3},
        {"type": "frame_label", "text": "Raw footage", "timecode_from": 12.0, "duration": 2.5},
        {"type": "takeover", "text": "*Nine*\nreviews.", "sub": "example", "bg": "dark", "duration": 1.4},
        {"type": "strike", "title": "What everyone tries", "items": ["Asking in person", "A sign at the counter", "Hoping"], "answer": "A text, the same day", "duration": 4},
        {"type": "words", "words": ["because", "we're", "gonna", "*text*", "them"], "chip": "AuburnSEO", "duration": 2.4},
        {"type": "toast", "title": "Review request", "text": "Sent to 14 customers (example).", "position": "0.30", "duration": 2},
        {"type": "hook", "kicker": "Building a", "text": "Review machine", "sub": "for Huntsville roofers", "variant": "clean", "duration": 3},
        {"type": "fan", "cards": [{"text": "Review request sent", "badge": "day 1"}, {"text": "Reply written for you", "badge": "day 2"}, {"text": "5 stars posted", "badge": "day 3"}], "duration": 3},
        {"type": "steps", "title": "What happens", "items": ["Customer finishes the job", "Text goes out", "Review lands on Google", "Reply posted for you"], "duration": 4},
        {"type": "timer", "label": "Time spent chasing reviews", "from": 0, "rate": 90, "note": "Ask in person", "note_time": "0:03", "duration": 3},
        {"type": "quote", "name": "Customer", "when": "example", "text": "Got *three* new reviews the first week.", "likes": 3, "source": "with permission", "duration": 3},
        {"type": "files", "items": [{"label": "Roof repair", "sub": "2019"}, {"label": "Gutter job", "sub": "2021"}, {"label": "Re-roof", "sub": "2023"}, {"label": "Storm damage", "sub": "2024"}], "badge": "R", "duration": 3},
        {"type": "tracks", "highlight": {"from": 0, "to": 0.1, "label": "10%"}, "duration": 3},
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
