"""Search every transcript in a batch for a topic or a phrase, and pull the matching moments
into a draft EDL (the "find everything about X across three interviews" move).

Scores each sentence-sized window of every words.json against the query (word overlap plus
fuzzy match), prints the best moments with file and timecode, and with --edl writes them in
order as a draft EDL you can cut from. Works on raw takes, customer interviews, podcasts:
anything with speech.

Usage:
    .venv/bin/python tools/find.py "slow season" --transcripts work/transcripts
    .venv/bin/python tools/find.py "when the phone stopped ringing" --transcripts work/transcripts --top 8
    .venv/bin/python tools/find.py "reviews" --transcripts work/transcripts --edl work/edl/HSV_reviews_noprice_pull_story_30s_9x16_v1.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402
from selects import MEDIA_EXT, PAD_IN, PAD_OUT, load_transcripts, norm  # noqa: E402

STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "it", "is", "i", "you", "we", "that", "this", "for", "with", "was", "be", "so"}


def windows(words: list[dict], size: int, step: int):
    for i in range(0, max(1, len(words) - size + 1), step):
        yield i, words[i:i + size]


def search(query: str, transcripts: dict[str, list[dict]], top: int = 10) -> list[dict]:
    q = [norm(t) for t in query.split() if norm(t)]
    qset = {t for t in q if t not in STOP} or set(q)
    hits = []
    for stem, words in transcripts.items():
        wt = [norm(w["word"]) for w in words]
        for size in (max(6, len(q) * 2), 14):
            for i, win in windows(words, size, max(1, size // 3)):
                toks = wt[i:i + size]
                overlap = len(qset & set(toks)) / max(1, len(qset))
                if overlap == 0:
                    continue
                fuzzy = SequenceMatcher(None, q, toks, autojunk=False).ratio()
                score = 0.7 * overlap + 0.3 * fuzzy
                hits.append({"stem": stem, "start": round(max(0.0, win[0]["start"] - PAD_IN), 3), "end": round(win[-1]["end"] + PAD_OUT, 3),
                             "score": round(score, 3), "text": " ".join(w["word"] for w in win)})
    hits.sort(key=lambda h: -h["score"])
    picked = []
    for h in hits:
        if any(p["stem"] == h["stem"] and not (h["end"] < p["start"] or h["start"] > p["end"]) for p in picked):
            continue
        picked.append(h)
        if len(picked) == top:
            break
    return picked


def write_edl(hits: list[dict], out: Path, raw: Path, name: str) -> None:
    import yaml  # noqa: WPS433

    def src_of(stem: str) -> str:
        for p in sorted(raw.rglob(f"{stem}.*")):
            if p.suffix.lower() in MEDIA_EXT:
                try:
                    return str(p.relative_to(raw.parent))
                except ValueError:
                    return str(p)
        return f"raw/{stem}.mov"

    clips = [{"src": src_of(h["stem"]), "in": h["start"], "out": h["end"], "note": h["text"][:80]} for h in sorted(hits, key=lambda h: (h["stem"], h["start"]))]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump({"name": name, "clips": clips}, sort_keys=False, allow_unicode=True))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--transcripts", required=True)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--edl", help="write the moments, in source order, as a draft EDL at this path")
    ap.add_argument("--raw", default=None, help="raw folder for resolving sources (default: <batch>/raw next to work/)")
    args = ap.parse_args()
    tr = Path(args.transcripts)
    hits = search(args.query, load_transcripts(tr), args.top)
    for h in hits:
        m, s_ = divmod(int(h["start"]), 60)
        print(f"{h['score']:.2f}  {h['stem']}  {m:02d}:{s_:02d}  {h['text'][:110]}")
    print(f"{len(hits)} moments for {args.query!r}")
    if args.edl and hits:
        raw = Path(args.raw) if args.raw else (tr.parent.parent / "raw")
        write_edl(hits, Path(args.edl), raw, Path(args.edl).stem)
        print(f"draft EDL: {args.edl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
