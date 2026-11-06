"""Lint ad copy, captions, and on-screen text against the house rules and Meta policy.

Checks every `exports/*_copy.md`, every EDL's hook text, callouts and end card, and every
burned caption file in a batch for:
    - em dashes (house rule)
    - agency jargon the ICP does not use (SEO, funnel, CRM, conversion, leverage, optimize...)
    - personal-attribute wording Meta rejects ("struggling", "broke", "can't afford", "your debt"...)
    - claims that need proof or are banned (guarantee, #1, best, "results in X days", "double your")
    - fake urgency ("only 2 spots", "today only") unless config has real scarcity
    - numbers or prices that are not labeled "(example)" and are not in config proof assets
    - headline length (27 characters recommended) and first-line length (about 44 shown on Reels)
    - "we"/"I" outnumbering "you"/"your"

Usage:
    .venv/bin/python tools/lint_copy.py batches/<id>            # whole batch
    .venv/bin/python tools/lint_copy.py batches/<id> --strict   # exit 1 on any FAIL
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config, load_yaml  # noqa: E402

EM_DASH = chr(0x2014)
JARGON = ["seo", "funnel", "crm", "conversion", "conversions", "leverage", "optimize", "optimization", "roi",
          "kpi", "synergy", "scalable", "omnichannel", "lead gen", "lead generation", "ctr", "cpl"]
PERSONAL = ["struggling", "struggle to", "broke", "can't afford", "cannot afford", "in debt", "your debt", "desperate",
            "failing business", "losing your business", "behind on", "bankrupt", "your age", "overweight", "depressed",
            "your health", "your race", "your religion"]
CLAIMS = ["guarantee", "guaranteed", "#1", "number one", "the best", "best in", "double your", "triple your",
          "10x", "instantly", "overnight", "never fails", "risk-free", "risk free", "no risk", "proven"]
URGENCY = ["only 2 spots", "only two spots", "spots left", "today only", "ends tonight", "last chance",
           "limited time", "act now", "before it's gone"]
NUMBER_RE = re.compile(r"(\$\s?\d[\d,]*(\.\d+)?|\b\d{2,}\b|\b\d+%|\b\d+\s?(stars?|reviews?|jobs?|calls?|leads?|days?|weeks?|hours?|x)\b)", re.I)
TIME_RE = re.compile(r"^\d+(\.\d+)?s$|^\d+:\d+")   # not a claim: "30s", "0:12"


def finding(level: str, where: str, text: str, why: str) -> dict:
    return {"level": level, "where": where, "text": text.strip()[:90], "why": why}


def has_real_scarcity(cfg: dict) -> bool:
    v = str((cfg.get("offer") or {}).get("urgency_or_scarcity") or "").strip().lower()
    return v not in {"", "tbd", "none", "no"}


def known_numbers(cfg: dict) -> set[str]:
    """Numbers that appear in config proof assets or the offer price are allowed without an example label."""
    nums = set()
    blob = str(cfg.get("proof_assets") or "") + " " + str((cfg.get("offer") or {}).get("price") or "")
    for m in NUMBER_RE.finditer(blob):
        nums.add(re.sub(r"[^\d.]", "", m.group(0)))
    return {n for n in nums if n}


def lint_text(text: str, where: str, cfg: dict, kind: str = "text") -> list[dict]:
    out = []
    low = text.lower()
    if EM_DASH in text:
        out.append(finding("FAIL", where, text, "em dash; use a hyphen or rewrite"))
    for w in JARGON:
        if re.search(rf"\b{re.escape(w)}\b", low) and not ("auburnseo" in low and w == "seo" and low.count("seo") == low.count("auburnseo")):
            out.append(finding("WARN", where, text, f"jargon '{w}': say the outcome (phone ringing, jobs booked, showing up first on Google)"))
    for w in PERSONAL:
        if w in low:
            out.append(finding("FAIL", where, text, f"'{w}' implies a personal attribute (Meta policy); call out by trade and place instead"))
    for w in CLAIMS:
        if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", low):
            out.append(finding("WARN", where, text, f"claim '{w}': only if Bruce offers it in writing or has proof on hand"))
    if not has_real_scarcity(cfg):
        for w in URGENCY:
            if w in low:
                out.append(finding("FAIL", where, text, f"urgency '{w}' but config offer.urgency_or_scarcity is not a real constraint"))
    if "example" not in low:
        ok = known_numbers(cfg)
        scan = re.sub(r"\(\d+\)", "", text)   # "(27)" character counts after headlines are not claims
        for m in NUMBER_RE.finditer(scan):
            tok = m.group(0)
            if TIME_RE.match(tok) or re.sub(r"[^\d.]", "", tok) in ok:
                continue
            out.append(finding("WARN", where, text, f"number '{tok}' is not labeled (example) and is not in config proof_assets or offer.price"))
            break
    return out


def lint_copy_file(path: Path, cfg: dict) -> list[dict]:
    out = []
    text = path.read_text()
    out += lint_text(text, path.name, cfg)
    you = len(re.findall(r"\b(you|your|you're|yours)\b", text, re.I))
    we = len(re.findall(r"\b(we|our|i|i'm|my|us)\b", text, re.I))
    if we > you:
        out.append(finding("WARN", path.name, f"you={you} we/I={we}", "more 'we/I' than 'you'; make it about the contractor"))
    in_headlines = False
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^#+\s*headline", s, re.I):
            in_headlines = True
            continue
        if s.startswith("#"):
            in_headlines = False
        if in_headlines and s and not s.startswith("#"):
            h = re.sub(r"^[-*\d.)\s]+", "", s)
            h = re.sub(r"\s*\(\d+\)\s*$", "", h)
            if h and len(h) > 27 and not re.search(r"\d+ ?chars?|characters", s, re.I):
                out.append(finding("WARN", path.name, h, f"headline is {len(h)} characters; Meta recommends 27"))
    m = re.search(r"^#+\s*primary text.*?\n(.*?)(?=^#)", text, re.I | re.S | re.M)
    if m:
        first = next((ln.strip() for ln in m.group(1).splitlines() if ln.strip() and not ln.strip().startswith(("-", "*", "#"))), "")
        if len(first) > 44:
            out.append(finding("WARN", path.name, first, f"first line of primary text is {len(first)} characters; Reels shows about 44"))
    return out


def lint_edl(path: Path, cfg: dict) -> list[dict]:
    out = []
    edl = load_yaml(path)
    if edl.get("hook_text"):
        out += lint_text(str(edl["hook_text"]), f"{path.name} hook_text", cfg)
        if len(str(edl["hook_text"]).split()) > 8:
            out.append(finding("WARN", f"{path.name} hook_text", str(edl["hook_text"]), "more than 8 words; a text hook should read in one glance"))
    for co in edl.get("callouts") or []:
        out += lint_text(str(co.get("text", "")), f"{path.name} callout", cfg)
    card = edl.get("end_card") or {}
    for k in ("headline", "text", "subtext"):
        if card.get(k):
            out += lint_text(str(card[k]), f"{path.name} end_card.{k}", cfg)
    for b in edl.get("broll") or []:
        if b.get("label"):
            out += lint_text(str(b["label"]), f"{path.name} broll label", cfg)
    return out


def lint_ass(path: Path, cfg: dict) -> list[dict]:
    text = " ".join(re.sub(r"\{[^}]*\}", "", ln.split(",", 9)[-1]).replace(r"\N", " ")
                    for ln in path.read_text().splitlines() if ln.startswith("Dialogue:"))
    seen, out = set(), []
    for f in lint_text(text, f"{path.name} captions", cfg):
        key = (f["level"], f["why"][:30])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def lint_batch(batch: Path, cfg: dict) -> list[dict]:
    out = []
    for p in sorted((batch / "exports").glob("*_copy.md")) if (batch / "exports").exists() else []:
        out += lint_copy_file(p, cfg)
    for p in sorted((batch / "work" / "edl").rglob("*.yaml")) if (batch / "work" / "edl").exists() else []:
        if not p.name.endswith(".variants.yaml"):
            out += lint_edl(p, cfg)
    for p in sorted((batch / "work" / "cuts").glob("*.ass")) if (batch / "work" / "cuts").exists() else []:
        out += lint_ass(p, cfg)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    findings = lint_batch(Path(args.batch), cfg)
    fails = [f for f in findings if f["level"] == "FAIL"]
    md = ["# Copy and caption lint", "", f"{len(fails)} FAIL, {len(findings) - len(fails)} WARN", "",
          "| level | where | text | why |", "|---|---|---|---|"]
    md += [f"| {f['level']} | {f['where']} | {f['text']} | {f['why']} |" for f in findings]
    out = Path(args.batch) / "qa" / "LINT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md) + "\n")
    print(f"{len(fails)} FAIL, {len(findings) - len(fails)} WARN -> {out}")
    return 1 if (args.strict and fails) else 0


if __name__ == "__main__":
    sys.exit(main())
