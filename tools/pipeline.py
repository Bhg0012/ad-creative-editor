"""The assembly line: one command takes an EDL from raw footage to a QA'd, reviewable ad.

Each step is one of the existing tools, run in order, with a tick and the time it took, so the
whole edit reads like a checklist (reference 5: "a 10 step assembly line"). Every step is
skippable and re-runnable; nothing here is a new way to edit, it is the same tools in sequence.

    1. Reading footage        tools/inventory.py (skipped when work/inventory.csv exists)
    2. Transcribing the takes tools/transcribe.py on every source the EDL uses (skips files already transcribed)
    3. Storyboarding          tools/render.py --storyboard
    4. Proxy cut              tools/render.py --proxy (only with --proxy)
    5. Rendering the cut      tools/render.py
    6. Captions               --captions source (falls back to auto when a take has no transcript)
    7. Other ratios           every ratio in batch_defaults.aspect_ratios (only with --all-ratios)
    8. Running QA             tools/qa.py with the batch script if present
    9. Checking the copy      tools/lint_copy.py --strict
   10. Delivering             tools/review.py (the review page)

Usage:
    .venv/bin/python tools/pipeline.py batches/<id>/work/edl/<adname>.yaml
    .venv/bin/python tools/pipeline.py <edl> --proxy            # stop after the proxy for a first look
    .venv/bin/python tools/pipeline.py <edl> --all-ratios       # finals in every ratio
    .venv/bin/python tools/pipeline.py <edl> --only 5,6,8       # just these steps
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_config, load_yaml  # noqa: E402

PY = sys.executable
TOOLS = Path(__file__).resolve().parent
STEPS = ["Reading footage", "Transcribing the takes", "Storyboarding", "Proxy cut", "Rendering the cut",
         "Captions", "Other ratios", "Running QA", "Checking the copy", "Delivering"]


def run(cmd: list[str], cwd: Path) -> int:
    print("   $ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def batch_dir_of(path: Path) -> Path:
    import render  # noqa: WPS433

    return render.batch_dir_of(path)


def sources_of(edl_path: Path) -> list[Path]:
    edl = load_yaml(edl_path)
    base = batch_dir_of(edl_path)
    out = []
    for c in edl.get("clips") or []:
        src = Path(str(c.get("src", "")))
        if src.suffix.lower() in (".mp4", ".mov", ".m4v", ".mkv", ".webm"):
            p = (base / src) if not src.is_absolute() else src
            if p.exists() and p not in out:
                out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("--proxy", action="store_true", help="stop after the proxy cut (steps 1-4)")
    ap.add_argument("--all-ratios", action="store_true", help="also render every ratio in batch_defaults.aspect_ratios")
    ap.add_argument("--only", help="comma-separated step numbers to run, e.g. 5,6,8")
    ap.add_argument("--skip", help="comma-separated step numbers to skip")
    ap.add_argument("--fresh", action="store_true", help="redo inventory and transcripts even if they exist")
    args = ap.parse_args()

    edl_path = Path(args.edl).resolve()
    if not edl_path.exists():
        raise SystemExit(f"no EDL at {edl_path}")
    batch = batch_dir_of(edl_path)
    cfg = load_config()
    only = {int(x) for x in args.only.split(",")} if args.only else None
    skip = {int(x) for x in args.skip.split(",")} if args.skip else set()
    if args.proxy:
        only = (only or set(range(1, 11))) & {1, 2, 3, 4}
    if not args.all_ratios:
        skip.add(7)
    if not args.proxy:
        skip.add(4)

    print(f"Assembly line for {edl_path.name} in {batch}")
    results = []
    t_all = time.time()
    for n, name in enumerate(STEPS, 1):
        if (only is not None and n not in only) or n in skip:
            results.append((n, name, "skip", 0.0))
            continue
        t0 = time.time()
        rc = 0
        note = ""
        if n == 1:
            inv = batch / "work" / "inventory.csv"
            raw = batch / "raw"
            if not raw.exists():
                note = "no raw/ folder in the batch"
            elif inv.exists() and not args.fresh:
                note = "inventory exists"
            else:
                rc = run([PY, str(TOOLS / "inventory.py"), "--raw", str(raw), "--out", str(inv), "--sheets", str(batch / "work" / "sheets")], batch)
        elif n == 2:
            tr = batch / "work" / "transcripts"
            todo = [s for s in sources_of(edl_path) if args.fresh or not (tr / f"{s.stem}.words.json").exists()]
            if not todo:
                note = "every take already transcribed"
            else:
                rc = run([PY, str(TOOLS / "transcribe.py"), *map(str, todo), "--out", str(tr)], batch)
                if rc:
                    note = "no transcription backend; captions will fall back to auto"
                    rc = 0
        elif n == 3:
            rc = run([PY, str(TOOLS / "render.py"), str(edl_path), "--storyboard"], batch)
        elif n == 4:
            rc = run([PY, str(TOOLS / "render.py"), str(edl_path), "--proxy"], batch)
        elif n == 5:
            rc = run([PY, str(TOOLS / "render.py"), str(edl_path)], batch)
        elif n == 6:
            tr = batch / "work" / "transcripts"
            have = all((tr / f"{s.stem}.words.json").exists() for s in sources_of(edl_path))
            rc = run([PY, str(TOOLS / "render.py"), str(edl_path), "--captions", "source" if have else "auto"], batch)
            note = "from the source transcripts" if have else "transcribed the master (no source transcripts)"
        elif n == 7:
            ratios = [r for r in ((cfg.get("batch_defaults") or {}).get("aspect_ratios") or []) if r != str(load_yaml(edl_path).get("ratio") or "9:16")]
            for r in ratios:
                rc = rc or run([PY, str(TOOLS / "render.py"), str(edl_path), "--ratio", r, "--captions", "source"], batch)
            note = ", ".join(ratios) if ratios else "no other ratios configured"
        elif n == 8:
            exports = sorted((batch / "exports").glob(f"{edl_path.stem}*.mp4"))
            if not exports:
                note, rc = "nothing in exports/ for this EDL", 1
            else:
                script = batch / "brief" / "08_scripts.md"
                cmd = [PY, str(TOOLS / "qa.py"), *map(str, exports), "--qa-dir", str(batch / "qa")]
                if script.exists():
                    cmd += ["--script", str(script)]
                rc = run(cmd, batch)
        elif n == 9:
            rc = run([PY, str(TOOLS / "lint_copy.py"), str(batch), "--strict"], batch)
            if rc:
                note, rc = "lint found FAIL rows; fix them before the gate", 0
        elif n == 10:
            rc = run([PY, str(TOOLS / "review.py"), str(batch)], batch)
        dt = time.time() - t0
        results.append((n, name, "ok" if rc == 0 else "FAIL", dt, note))
        print(f"{'ok' if rc == 0 else 'FAIL':>4}  {n:>2}. {name} ({dt:.1f}s){'  ' + note if note else ''}")
        if rc != 0:
            print(f"Stopped at step {n}: {name}. Fix the error above and re-run with --only {n},{','.join(str(i) for i in range(n + 1, 11))}")
            return 1
    print(f"\nDone in {time.time() - t_all:.0f}s")
    for r in results:
        mark = {"ok": "[x]", "skip": "[ ]", "FAIL": "[!]"}[r[2]]
        print(f"  {mark} {r[0]:>2}. {r[1]}" + (f"  ({r[4]})" if len(r) > 4 and r[4] else ""))
    print(f"\nReview page: {batch / 'review' / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
