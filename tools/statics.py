"""Static image ads from a real photo or a frame of a finished ad.

Layout: image cover-cropped to the ratio, a dark gradient over the lower half for
legibility, headline (the hook, max about 7 words) and optional sub line above a CTA pill
in the accent color, all inside the safe zone. Logo top-left if brand/logo.png exists.

Templates (`--template`, rendered in the same browser engine as the motion plates, so they share the
design system and the safe zone): headliner, problem, question, mythbuster, versus, listicle, howitworks,
quote, postit, letter, lofi. The default (no --template) is the photo + gradient + headline layout above.
Rules they follow: hook biggest, then the qualifier, then what it is, then the proof; `*word*` highlights the
one key word (accent), `!word!` marks a pain word in red; at most 3 text elements; readable at 360 px.
`lofi` puts NO text on the photo: the headline belongs in the primary text (Sabri Suby V13, raw founder photo).
Real assets only: a quote is a real customer's exact words with written permission (compliance).

    .venv/bin/python tools/statics.py --template headliner --headline "Huntsville roofers: *9 reviews*?" --sub "The guy down the road has 140" --out statics/x.png
    .venv/bin/python tools/statics.py --template listicle --headline "3 reasons roofers lose the call" --items "Fewer reviews" "Old photos" "No replies" --out ...
    .venv/bin/python tools/statics.py --template versus --headline "Asking in person vs a text" --left "Asking|You forget|They forget" --right "A text|Sent for you|Same day" --out ...
    .venv/bin/python tools/statics.py --template mythbuster --headline "Word of mouth is enough" --sub "People check Google before they call you back" --out ...
    .venv/bin/python tools/statics.py --template quote --headline "Exact words from a real review" --name "First name, trade, city" --image brand/proof/face.jpg --out ...

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


TEMPLATES = ("headliner", "problem", "question", "mythbuster", "versus", "listicle", "howitworks", "quote", "postit", "letter", "lofi")


def _rich(text: str) -> str:
    import html
    import re

    t = html.escape(text or "")
    t = re.sub(r"\*([^*]+)\*", r'<span class="hl">\1</span>', t)          # key word in an accent box
    t = re.sub(r"!([^!]+)!", r'<span class="hl" style="background:#d12d3a">\1</span>', t)   # pain word in red
    return t


def template_html(spec: dict, w: int, h: int, cfg: dict) -> str:
    """HTML for one static template, filled into tools/plates/static.html."""
    import html

    import plates as pl  # noqa: WPS433

    kind = spec["template"]
    head = _rich(spec.get("headline", ""))
    sub = html.escape(spec.get("sub") or "")
    cta = html.escape(spec.get("cta") or "")
    qual = html.escape(spec.get("qualifier") or "")
    img = spec.get("image")
    uri = pl.data_uri(img) if img else ""
    items = [html.escape(x) for x in (spec.get("items") or [])][:5]
    words = len((spec.get("headline") or "").split())
    hsize = round(h * (0.085 if words <= 5 else 0.07 if words <= 8 else 0.058))
    v = {"bg": "#0f1115", "ink": "#ffffff", "hl": "var(--accent)", "justify": "flex-end", "shadow": "", "bg_html": "", "hsize": hsize}
    cta_html = f'<div class="cta">{cta}</div>' if cta else ""
    q_html = f'<div class="q">{qual}</div>' if qual else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    if kind in ("headliner", "question"):
        if uri:
            v["bg_html"] = f'<div class="photo dim" style="background-image:url({uri})"></div>'
            v["shadow"] = "shadow"
        else:
            v["bg"] = cfg.get("business", {}).get("brand_colors", {}).get("primary", "#3B96F6") if kind == "question" else "#0f1115"
        v["justify"] = "center" if not uri else "flex-end"
        body = f'{q_html}<div class="h">{head}</div>{sub_html}{cta_html}'
    elif kind == "problem":
        # problem in the top half in plain words, the photo in the bottom half (Alessio Cordeddu V5)
        v.update(bg="#f3f0ea", ink="#1f1b16", justify="flex-start")
        if uri:
            v["bg_html"] = f'<div class="photo half" style="background-image:url({uri})"></div>'
        body = f'<div class="split-top">{q_html}<div class="h">{head}</div>{sub_html}</div><div style="flex:1"></div>{cta_html}'
    elif kind == "mythbuster":
        v.update(bg="#f3f0ea", ink="#1f1b16", justify="center")
        v["bg_html"] = '<div class="paper"></div>'
        body = (f'{q_html}<div class="myth"><span class="tag bad">Myth</span><br><s>{html.escape(spec.get("headline", ""))}</s></div>'
                f'<div class="myth"><span class="tag good">Truth</span><br>{sub}</div>{cta_html}')
    elif kind == "versus":
        v.update(bg="#ffffff", ink="#0f1115", justify="center")
        left = [html.escape(x) for x in (spec.get("left") or "").split("|") if x]
        right = [html.escape(x) for x in (spec.get("right") or "").split("|") if x]
        col = lambda rows, win: (f'<div class="col{" win" if win else ""}"><b>{rows[0] if rows else ""}</b>'
                                 + "".join(f"<div>{'&#10003;' if win else '&#10007;'} {r}</div>" for r in rows[1:5]) + "</div>")
        body = f'{q_html}<div class="h" style="font-size:{round(hsize * .72)}px">{head}</div><div class="vs">{col(left, False)}{col(right, True)}</div>{cta_html}'
    elif kind in ("listicle", "howitworks"):
        v.update(bg="#0f1115", justify="center")
        if uri:
            v["bg_html"] = f'<div class="photo dim" style="background-image:url({uri});opacity:.55"></div>'
        rows = "".join(f'<div class="row"><span class="num">{i + 1}</span><span>{x}</span></div>' for i, x in enumerate(items[:3 if kind == "howitworks" else 5]))
        body = f'{q_html}<div class="h" style="font-size:{round(hsize * .78)}px">{head}</div><div class="list">{rows}</div>{cta_html}'
    elif kind == "quote":
        v.update(bg="#ffffff", ink="#0f1115", justify="center")
        who = html.escape(spec.get("name") or "")
        face = (f'<div style="width:22%;aspect-ratio:1;border-radius:50%;background:center/cover url({uri});box-shadow:var(--shadow)"></div>' if uri else "")
        body = f'{face}<div class="quote">{html.escape(spec.get("headline", ""))}</div><div class="who">{who}</div>{cta_html}'
    elif kind == "postit":
        v.update(justify="center")
        if uri:
            v["bg_html"] = f'<div class="photo" style="background-image:url({uri})"></div>'
        body = f'<div class="note">{html.escape(spec.get("headline", ""))}' + (f'<div style="font-size:.6em;margin-top:.6em">{sub}</div>' if sub else "") + f'</div>{cta_html}'
    elif kind == "letter":
        v.update(bg="#e9e4da", ink="#1f1b16", justify="center")
        paras = "".join(f"<p style='margin:.5em 0'>{x}</p>" for x in items) or (f"<p>{sub}</p>" if sub else "")
        sig = html.escape(spec.get("name") or "Bruce, AuburnSEO")
        body = f'<div class="letter"><div class="t">{head}</div>{paras}<div class="sig">{sig}</div></div>{cta_html}'
    else:
        raise SystemExit(f"unknown template {kind!r}; choose one of {', '.join(TEMPLATES)}")
    return pl.fill("static", {"theme": pl.theme(w, h, 1.0, cfg), "body": body, **v})


def build_template(spec: dict, ratio: str, out: Path, focus=(0.5, 0.5)) -> Path:
    w, h = RESOLUTIONS[ratio][0]
    out.parent.mkdir(parents=True, exist_ok=True)
    if spec["template"] == "lofi":
        # the raw phone photo, no overlay at all: the words live in the primary text above the ad
        from PIL import Image

        if not spec.get("image"):
            raise SystemExit("--template lofi needs --image (a real, unedited phone photo)")
        cover_crop(Image.open(spec["image"]).convert("RGB"), w, h, focus).save(out, "PNG", optimize=True)
        return out
    import plates as pl  # noqa: WPS433

    r = pl.Renderer(w, h)
    try:
        r.render_still(template_html(spec, w, h, load_config()), 0.0, out)
    finally:
        r.close()
    from PIL import Image

    Image.open(out).convert("RGB").save(out, "PNG", optimize=True)   # statics are opaque
    return out


def frame_from(video: Path, at: float, tmp: Path) -> Path:
    png = tmp / "frame.png"
    subprocess.run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", str(png)],
                   check=True)
    return png


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", choices=TEMPLATES, help="a static template (see the docstring); omit for the photo + gradient layout")
    ap.add_argument("--items", nargs="*", help="list rows for listicle / howitworks / letter paragraphs")
    ap.add_argument("--left", help='versus: "label|row|row"')
    ap.add_argument("--right", help='versus: "label|row|row" (the winning column)')
    ap.add_argument("--name", help="quote: who said it (first name, trade, city); letter: the signature")
    ap.add_argument("--qualifier", help="small line above the hook, e.g. 'For Huntsville roofers'")
    src = ap.add_mutually_exclusive_group(required=False)
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
    if args.template:
        with tempfile.TemporaryDirectory() as td:
            image = Path(args.image) if args.image else (frame_from(Path(args.frame_from), args.at, Path(td)) if args.frame_from else None)
            spec = {"template": args.template, "headline": args.headline, "sub": args.sub, "cta": args.cta, "image": str(image) if image else None,
                    "items": args.items, "left": args.left, "right": args.right, "name": args.name, "qualifier": args.qualifier}
            out = build_template(spec, args.ratio, Path(args.out), focus)
        print(f"Wrote {out}")
        return 0
    if not (args.image or args.frame_from):
        raise SystemExit("--image or --frame-from is required for the default layout")
    with tempfile.TemporaryDirectory() as td:
        image = Path(args.image) if args.image else frame_from(Path(args.frame_from), args.at, Path(td))
        out = build(image, args.ratio, args.headline, args.sub, args.cta, Path(args.out), focus, not args.no_logo)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
