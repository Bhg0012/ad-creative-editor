"""Build burned-in caption subtitles (.ass) from a word-level transcript.

Captions come from the transcript of the FINAL cut (transcribe the rendered edit),
so timing matches the timeline exactly. Never retype captions by hand.

Style: bold sans, 2-5 words per chunk, max 2 lines, white with black outline, one
keyword per chunk in the accent color, positioned inside the safe zone.

Usage:
    .venv/bin/python tools/captions.py work/transcripts/cut.words.json \
        --size 1080x1920 --out work/cut.ass
    ffmpeg -i cut.mp4 -vf "ass=work/cut.ass:fontsdir=brand/fonts" -c:a copy captioned.mp4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config, ratio_of, safe_box  # noqa: E402

STOPWORDS = set("""a an the and or but if of to in on at by for with from up out as is are was were be been
it its this that these those you your we our i me my he she they them their his her him so do does did
not no just than then there here what when where who how can will would could should get got have has
had im i'm you're it's that's dont don't""".split())

PAUSE_BREAK = 0.35   # seconds of silence that forces a new chunk
MAX_LINE_CHARS = 16  # per line, before wrapping to a second line
HOLD_GAP = 0.25      # gaps shorter than this are bridged so captions do not flicker


def hex_to_bgr(color: str) -> str:
    """'#E55B13' -> '135BE5' (ASS stores colors as blue-green-red)."""
    c = color.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        raise SystemExit(f"Bad color {color!r}; use #RRGGBB.")
    return (c[4:6] + c[2:4] + c[0:2]).upper()


def apply_fixes(words: list[dict], fixes: dict) -> list[dict]:
    """Case-insensitive phrase replacement across consecutive words (e.g. 'auburn seo' -> 'AuburnSEO')."""
    if not fixes:
        return words
    out, i = [], 0
    rules = sorted(((k.lower().split(), v) for k, v in fixes.items()), key=lambda r: -len(r[0]))
    while i < len(words):
        for src, dst in rules:
            span = words[i:i + len(src)]
            if len(span) == len(src) and all(
                re.sub(r"[^\w']", "", w["word"].lower()) == s for w, s in zip(span, src)
            ):
                trail = re.findall(r"[^\w']+$", span[-1]["word"])
                out.append({**span[0], "word": dst + (trail[0] if trail else ""), "end": span[-1]["end"]})
                i += len(src)
                break
        else:
            out.append(words[i])
            i += 1
    return out


def chunk(words: list[dict], max_words: int) -> list[list[dict]]:
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        chars = len(" ".join(x["word"] for x in cur))
        ends_sentence = w["word"][-1] in ".?!,;:"
        pause = nxt is not None and nxt["start"] - w["end"] >= PAUSE_BREAK
        too_long = nxt is not None and chars + 1 + len(nxt["word"]) > MAX_LINE_CHARS * 2
        if len(cur) >= max_words or ends_sentence or pause or too_long or nxt is None:
            chunks.append(cur)
            cur = []
    return chunks


def pick_keyword(chunk_words: list[dict], keywords: set[str]) -> int | None:
    clean = [re.sub(r"[^\w$%']", "", w["word"]).lower() for w in chunk_words]
    for i, c in enumerate(clean):
        if c in keywords:
            return i
    for i, w in enumerate(chunk_words):  # numbers and money are the strongest emphasis
        if re.search(r"\d|\$", w["word"]):
            return i
    candidates = [(len(c), i) for i, c in enumerate(clean) if c and c not in STOPWORDS]
    if not candidates:
        return None
    return max(candidates)[1]


def wrap(tokens: list[str]) -> str:
    """Join tokens on one line, or split into two balanced lines if too long."""
    plain = [re.sub(r"\{[^}]*\}", "", t) for t in tokens]
    if len(" ".join(plain)) <= MAX_LINE_CHARS or len(tokens) < 2:
        return " ".join(tokens)
    best, best_diff = 1, 10**9
    for k in range(1, len(tokens)):
        diff = abs(len(" ".join(plain[:k])) - len(" ".join(plain[k:])))
        if diff < best_diff:
            best, best_diff = k, diff
    return " ".join(tokens[:best]) + r"\N" + " ".join(tokens[best:])


def ass_time(t: float) -> str:
    cs = int(round(max(t, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def build_ass(words: list[dict], width: int, height: int, font: str, accent: str,
              max_words: int = 4, uppercase: bool = False, keywords: set[str] | None = None) -> str:
    ratio = ratio_of(width, height)
    if ratio is None:
        raise SystemExit(f"Unsupported size {width}x{height}; use 9:16, 4:5 or 1:1.")
    box = safe_box(width, height, ratio)
    pad = round(height * 0.02)
    font_size = round(height * (0.042 if ratio == "9:16" else 0.05))
    outline = max(3, round(font_size * 0.09))
    # A heavy font file is already bold; asking libass for bold on top would smear it.
    bold = 0 if re.search(r"bold|black|heavy", font, re.I) else -1
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,{bold},0,0,0,100,100,0,0,1,{outline},2,2,{box['side'] + pad},{box['side'] + pad},{box['bottom'] + pad},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    acc = hex_to_bgr(accent)
    chunks = chunk(words, max_words)
    lines = []
    for n, c in enumerate(chunks):
        start = c[0]["start"]
        end = c[-1]["end"]
        if n + 1 < len(chunks):
            nxt = chunks[n + 1][0]["start"]
            end = nxt if nxt - end < HOLD_GAP else end
        else:
            end += 0.3
        k = pick_keyword(c, keywords or set())
        tokens = []
        for i, w in enumerate(c):
            t = escape(w["word"].upper() if uppercase else w["word"])
            if i == k:
                core, trail = re.match(r"^(.*?)([^\w$%]*)$", t).groups()
                t = f"{{\\c&H{acc}&}}{core}{{\\r}}{trail}"
            tokens.append(t)
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{wrap(tokens)}")
    return header + "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("words_json")
    ap.add_argument("--size", required=True, help="e.g. 1080x1920")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cfg = load_config()
    cap = cfg.get("captions", {}) or {}
    biz = cfg.get("business", {}) or {}
    width, height = (int(x) for x in args.size.lower().split("x"))
    words = apply_fixes(json.loads(Path(args.words_json).read_text()), cap.get("fixes") or {})
    ass = build_ass(
        words, width, height,
        font=biz.get("caption_font_name") or "Montserrat ExtraBold",
        accent=(biz.get("brand_colors") or {}).get("accent", "#E55B13"),
        max_words=max(2, min(5, int(cap.get("words_per_chunk_max") or 4))),
        uppercase=bool(cap.get("uppercase")),
        keywords={k.lower() for k in cap.get("keywords") or []},
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(ass)
    print(f"Wrote {args.out} ({ass.count('Dialogue:')} caption chunks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
