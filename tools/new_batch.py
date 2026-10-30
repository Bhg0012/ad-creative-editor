"""Scaffold a new ad batch folder with a gate tracker.

Usage:
    .venv/bin/python tools/new_batch.py --market HSV --offer reviews
Creates batches/<YYYY-MM-DD>_<market>_<offer>/ and prints its path.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402

SUBDIRS = ["brief", "brief/swipe", "work/transcripts", "work/cuts", "work/proxies", "graphics", "exports", "statics", "qa"]

TRACKER = """# Batch {batch_id}

Market: {market} | Offer: {offer} | Started: {date}

Update this file at every gate so any future session can resume exactly here.

| Stage | Output | Gate | Status |
|---|---|---|---|
| 1 Research | brief/01_research.md, 02_swipe.md, 03_my_data.md | GATE 1 | not started |
| 2 ICP + angles | brief/04_icp.md, 05_angles.md | GATE 2 | not started |
| 3 Offer + message | brief/06_offer.md | GATE 3 | not started |
| 4 Hooks + scripts | brief/07_hooks.md, 08_scripts.md, 09_shotlist.md | GATE 4 | not started |
| 5 Ingest + rough cut | work/inventory.csv, work/selects.md, work/cuts/ | GATE 5 | not started |
| 6 Full edit | first hero ad in exports/ | GATE 6 | not started |
| 7 Copy package | exports/*_copy.md | (with gate 8) | not started |
| 8 QA + delivery | qa/REPORT.md | GATE 7 | not started |
| 9 Launch plan | brief/10_launch.md | none | not started |

## Notes from Bruce at each gate

"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", required=True, help="short code, e.g. HSV or AUB")
    ap.add_argument("--offer", required=True, help="short slug, e.g. reviews or websites")
    args = ap.parse_args()
    for v in (args.market, args.offer):
        if not re.fullmatch(r"[A-Za-z0-9-]+", v):
            raise SystemExit(f"{v!r}: use letters, digits and hyphens only (underscores break the naming convention)")
    date = dt.date.today().isoformat()
    batch_id = f"{date}_{args.market}_{args.offer}"
    root = ROOT / "batches" / batch_id
    if root.exists():
        raise SystemExit(f"{root} already exists; resume it instead of recreating it.")
    for d in SUBDIRS:
        (root / d).mkdir(parents=True)
    (root / "BATCH.md").write_text(TRACKER.format(batch_id=batch_id, market=args.market, offer=args.offer, date=date))
    print(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
