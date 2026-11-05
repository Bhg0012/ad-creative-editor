"""Static image ads from a real photo or a frame of a finished ad.

Layout: image cover-cropped to the ratio, a dark gradient over the lower half for
legibility, headline (the hook, max about 7 words) and optional sub line above a CTA pill
in the accent color, all inside the safe zone. Logo top-left if brand/logo.png exists.

Usage:
    .venv/bin/python tools/statics.py --image brand/proof/site.jpg --headline "Huntsville roofers: 9 reviews?" \
        --sub "We fix that in 30 days" --cta "Tap Learn More" --ratio 4:5 --out statics/HSV_reviews_static_4x5_v1.png
    .venv/bin/python tools/statics.py --frame-from exports/ad.mp4 --at 2.5 --headline "..." --ratio 9:16 --out ...
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESOLUTIONS, ROOT, ffmpeg, find_font, load_config, safe_box  # noqa: E402


def cover_crop(img, w: int, h: int, focus=(0.5, 0.5)):
    from PIL import Image

    sw, sh = img.size
    scale = max(w / sw, h / sh)
    img = img.resize((max(w, round(sw * scale)), max(h, round(sh * scale))), Image.LANCZOS)
    nw, nh = img.size
    x = min(max(round(focus[0] * nw - w / 2), 0), nw - w)
    y = min(max(round(focus[1] * nh - h / 2), 0), nh - h)
    return img.crop((x, y, x + w, y + h))


def wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def build(image: Path, ratio: str, headline: str, sub: str | None, cta: str | None, out: Path,
          focus=(0.5, 0.5), logo: bool = True) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    cfg = load_config()
    biz = cfg.get("business") or {}
    colors = biz.get("brand_colors") or {}
    accent = colors.get("accent", "#E55B13")
    w, h = RESOLUTIONS[ratio][0]
    box = safe_box(w, h, ratio)
    font_path, exact = find_font(biz.get("caption_font_name") or "Montserrat ExtraBold")
    if not font_path:
        raise SystemExit("No font found; put the brand font in brand/fonts/.")
    if not exact:
        print(f"WARNING: brand font not in brand/fonts; using {font_path}")

    img = cover_crop(Image.open(image).convert("RGB"), w, h, focus)
    # Gradient: transparent at 40% height to 75% black at the bottom
    grad = Image.new("L", (1, h), 0)
    for y in range(h):
        f = max(0.0, (y / h - 0.40) / 0.60)
        grad.putpixel((0, y), int(255 * 0.75 * f))
    img.paste(Image.new("RGB", (w, h), "black"), (0, 0), grad.resize((w, h)))
    draw = ImageDraw.Draw(img)

    side = box["side"] + round(w * 0.03)
    max_w = w - 2 * side
    head_font = ImageFont.truetype(font_path, round(h * 0.068))
    sub_font = ImageFont.truetype(font_path, round(h * 0.036))
    cta_font = ImageFont.truetype(font_path, round(h * 0.034))
    stroke = max(3, round(h * 0.004))

    y = h - box["bottom"] - round(h * 0.03)
    if cta:
        tw = draw.textlength(cta, font=cta_font)
        pw, ph = round(tw + h * 0.05), round(h * 0.034 * 2.1)
        px, py = (w - pw) // 2, y - ph
        draw.rounded_rectangle((px, py, px + pw, py + ph), radius=ph // 2, fill=accent)
        draw.text((w / 2, py + ph / 2), cta, font=cta_font, fill="white", anchor="mm")
        y = py - round(h * 0.035)
    if sub:
        for line in reversed(wrap(draw, sub, sub_font, max_w)):
            y -= round(h * 0.036 * 1.3)
            draw.text((w / 2, y), line, font=sub_font, fill="white", anchor="ma", stroke_width=stroke, stroke_fill="black")
        y -= round(h * 0.02)
    for line in reversed(wrap(draw, headline, head_font, max_w)):
        y -= round(h * 0.068 * 1.2)
        draw.text((w / 2, y), line, font=head_font, fill="white", anchor="ma", stroke_width=stroke, stroke_fill="black")
    if y < box["top"]:
        print("WARNING: headline runs into the top safe zone; shorten it")

    logo_path = ROOT / "brand" / "logo.png"
    if logo and logo_path.exists():
        lg = Image.open(logo_path).convert("RGBA")
        lw = round(w * 0.22)
        lg = lg.resize((lw, round(lg.height * lw / lg.width)))
        img.paste(lg, (side, box["top"] + round(h * 0.02)), lg)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


def frame_from(video: Path, at: float, tmp: Path) -> Path:
    png = tmp / "frame.png"
    subprocess.run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", str(png)],
                   check=True)
    return png


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image")
    src.add_argument("--frame-from", help="video to grab a frame from")
    ap.add_argument("--at", type=float, default=0.0, help="seconds into the video for --frame-from")
    ap.add_argument("--headline", required=True)
    ap.add_argument("--sub")
    ap.add_argument("--cta", default="Tap Learn More")
    ap.add_argument("--ratio", default="4:5", choices=list(RESOLUTIONS))
    ap.add_argument("--focus", default="0.5,0.5", help="crop focus as x,y fractions")
    ap.add_argument("--no-logo", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    focus = tuple(float(v) for v in args.focus.split(","))
    with tempfile.TemporaryDirectory() as td:
        image = Path(args.image) if args.image else frame_from(Path(args.frame_from), args.at, Path(td))
        out = build(image, args.ratio, args.headline, args.sub, args.cta, Path(args.out), focus, not args.no_logo)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
