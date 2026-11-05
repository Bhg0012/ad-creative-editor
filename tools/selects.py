"""Find the best take for every script line in the transcribed footage.

Reads script lines (plain text, one per line, or the `[tc] | VO | ...` table rows from
brief/08_scripts.md) and every `*.words.json` in the transcripts folder, then aligns each
line to the closest spoken span (token similarity). Writes a selects table and a draft
EDL that `tools/render.py` can render as a rough cut.

Usage:
    .venv/bin/python tools/selects.py --script brief/08_scripts.md --transcripts work/transcripts \
        --out work/selects.md --edl work/edl/<adname>.yaml --name <adname> [--raw raw]

The draft EDL is a starting point: check the proxy, then fix in/out points by hand.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402

PAD_IN, PAD_OUT = 0.15, 0.25     # seconds added around the matched words (timestamp drift margin)
MIN_SCORE = 0.55                 # below this the line is reported as "not found in footage"
MEDIA_EXT = (".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts", ".wav", ".m4a", ".mp3")


def norm(tok: str) -> str:
    return re.sub(r"[^\w$%']", "", tok.lower())


def script_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\|?\s*\[?[\d:.\-s ]+\]?\s*\|\s*(.+?)\s*\|", line)   # `[0-3s] | VO text | ...`
        if m:
            line = m.group(1)
        elif line.startswith("|") or re.match(r"^\|?\s*-{2,}", line):
            continue  # table header or divider
        line = re.sub(r"\*\*|__|`", "", line)
        if len(norm(line)) >= 3:
            lines.append(line)
    return lines


def load_transcripts(folder: Path) -> dict[str, list[dict]]:
    out = {}
    for f in sorted(folder.glob("*.words.json")):
        words = json.loads(f.read_text())
        if words:
            out[f.name.replace(".words.json", "")] = words
    return out


def best_spans(line: str, words: list[dict], top: int = 3) -> list[dict]:
    toks = [norm(t) for t in line.split() if norm(t)]
    n = len(toks)
    if not n:
        return []
    wt = [norm(w["word"]) for w in words]
    tokset = set(toks)
    sizes = sorted({max(1, round(n * f)) for f in (0.7, 0.85, 1.0, 1.15, 1.3)})
    cands = []
    for L in sizes:
        for i in range(0, max(1, len(wt) - L + 1)):
            window = wt[i:i + L]
            if len(tokset & set(window)) < 0.4 * n:
                continue
            score = SequenceMatcher(None, toks, window, autojunk=False).ratio()
            cands.append((score, i, i + L))
    cands.sort(key=lambda c: -c[0])
    picked: list[dict] = []
    for score, a, b in cands:
        if any(abs(p["_a"] - a) < max(2, n // 2) for p in picked):
            continue  # same place, slightly different window
        span = words[a:b]
        picked.append({"_a": a, "score": round(score, 3), "start": round(max(0.0, span[0]["start"] - PAD_IN), 3),
                       "end": round(span[-1]["end"] + PAD_OUT, 3),
                       "text": " ".join(w["word"] for w in span),
                       "low_conf": sum(1 for w in span if w.get("prob", 1.0) < 0.5)})
        if len(picked) == top:
            break
    return picked


def find_source(stem: str, raw: Path) -> str:
    for p in sorted(raw.rglob(f"{stem}.*")):
        if p.suffix.lower() in MEDIA_EXT:
            try:
                return str(p.relative_to(ROOT))
            except ValueError:
                return str(p)
    return f"{stem}  # TODO: path to the source file"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--transcripts", required=True)
    ap.add_argument("--out", required=True, help="selects markdown")
    ap.add_argument("--edl", help="write a draft EDL yaml here")
    ap.add_argument("--name", default="DRAFT_offer_angle_hook_30s_9x16_v1", help="ad name for the draft EDL")
    ap.add_argument("--raw", default=str(ROOT / "raw"))
    args = ap.parse_args()
    lines = script_lines(Path(args.script))
    transcripts = load_transcripts(Path(args.transcripts))
    if not lines or not transcripts:
        raise SystemExit("Need at least one script line and one *.words.json transcript.")
    md = ["# Selects", "", f"{len(lines)} script lines matched against {len(transcripts)} transcript(s). "
          f"Score is token similarity (1.0 = exact). Lines under {MIN_SCORE} were not found: film them or rewrite.", ""]
    clips, missing = [], []
    for i, line in enumerate(lines, 1):
        found = []
        for stem, words in transcripts.items():
            for c in best_spans(line, words):
                found.append({**c, "file": stem})
        found.sort(key=lambda c: -c["score"])
        md += [f"## {i}. {line}", ""]
        if not found or found[0]["score"] < MIN_SCORE:
            md += ["- NOT FOUND in footage (best " + (f"{found[0]['score']:.2f}" if found else "none") + ")", ""]
            missing.append(line)
            continue
        md += ["| take | file | in | out | score | low-conf words | heard |", "|---|---|---|---|---|---|---|"]
        for k, c in enumerate(found[:3], 1):
            md.append(f"| {k} | {c['file']} | {c['start']:.2f} | {c['end']:.2f} | {c['score']:.2f} | {c['low_conf']} | {c['text']} |")
        md.append("")
        best = found[0]
        clips.append({"src": find_source(best["file"], Path(args.raw)), "in": best["start"], "out": best["end"],
                      "line": line, "score": best["score"]})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(md))
    print(f"Wrote {args.out}: {len(clips)} lines matched, {len(missing)} missing")
    if args.edl:
        y = [f"# Draft EDL from tools/selects.py. Check the proxy, then fix in/out by hand.",
             f"name: {args.name}", 'ratio: "9:16"', f"hook_text: \"{lines[0][:60]}\"" if lines else "", "clips:"]
        for n, c in enumerate(clips):
            zoom = 1.0 if n % 2 == 0 else 1.08   # alternate framing so jump cuts read as intentional
            y.append(f"  - {{src: {c['src']}, in: {c['in']:.2f}, out: {c['out']:.2f}, zoom: {zoom}, tighten: 0.45}}"
                     f"   # {c['line'][:60]} (score {c['score']:.2f})")
        y += ["end_card: {text: \"Tap Learn More\", seconds: 2.5}", ""]
        Path(args.edl).parent.mkdir(parents=True, exist_ok=True)
        Path(args.edl).write_text("\n".join(y))
        print(f"Draft EDL: {args.edl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
