"""Find the ums, uhs and false starts in a take, and cut them out of the edit.

Lists every filler word in a transcript with its timecode, and with --apply writes `skip`
ranges into the clips of an EDL so tools/render.py drops them from the audio and picture
(a jump cut on a filler is what a human editor does by reflex). Captions already hide
fillers (config captions.drop_fillers); this removes them from the sound.

Usage:
    .venv/bin/python tools/fillers.py work/transcripts/truck.words.json
    .venv/bin/python tools/fillers.py work/transcripts/*.words.json --apply work/edl/<adname>.yaml
    .venv/bin/python tools/fillers.py ... --repeats       # also flag a word said twice in a row ("the the")
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from captions import is_filler  # noqa: E402
from common import load_yaml  # noqa: E402


def find_fillers(words: list[dict], repeats: bool = False) -> list[dict]:
    out = []
    prev = None
    for w in words:
        plain = re.sub(r"[^a-z']", "", w["word"].lower())
        if is_filler(w["word"]):
            out.append({"start": w["start"], "end": w["end"], "word": w["word"], "kind": "filler"})
        elif repeats and prev is not None and plain and plain == prev["plain"] and w["start"] - prev["end"] < 0.6 and len(plain) >= 2:
            out.append({"start": prev["start"], "end": prev["end"], "word": prev["word"], "kind": "repeat"})
        prev = {"plain": plain, "start": w["start"], "end": w["end"], "word": w["word"]}
    return out


def apply_to_edl(edl_path: Path, found: dict[str, list[dict]]) -> int:
    import yaml  # noqa: WPS433

    edl = load_yaml(edl_path)
    n = 0
    for c in edl.get("clips") or []:
        stem = Path(str(c.get("src", ""))).stem
        if stem not in found or "in" not in c:
            continue
        skips = [list(x) for x in (c.get("skip") or [])]
        for f in found[stem]:
            if float(c["in"]) <= f["start"] and f["end"] <= float(c["out"]):
                rng = [round(f["start"], 3), round(f["end"], 3)]
                if rng not in skips:
                    skips.append(rng)
                    n += 1
        if skips:
            c["skip"] = sorted(skips)
    edl_path.write_text(yaml.safe_dump(edl, sort_keys=False, allow_unicode=True))
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", nargs="+", help="<stem>.words.json files")
    ap.add_argument("--apply", help="EDL to add `skip` ranges to")
    ap.add_argument("--repeats", action="store_true")
    args = ap.parse_args()
    found = {}
    for wj in args.words:
        p = Path(wj)
        stem = p.name.replace(".words.json", "")
        hits = find_fillers(json.loads(p.read_text()), args.repeats)
        found[stem] = hits
        for h in hits:
            print(f"{stem}  {h['start']:7.2f}-{h['end']:7.2f}  {h['kind']:7}  {h['word']}")
        print(f"{stem}: {len(hits)} found")
    if args.apply:
        n = apply_to_edl(Path(args.apply), found)
        print(f"added {n} skip ranges to {args.apply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
