"""Render many versions of one ad from a base EDL: different market, offer, hook, price, CTA.

A variants file sits next to the base EDL and describes dimensions. Every combination of
dimension values becomes its own EDL (and its own ad name) by patching the base:

    # work/edl/HSV_reviews_lostjobs_question_30s_9x16_v1.variants.yaml
    base: HSV_reviews_lostjobs_question_30s_9x16_v1.yaml
    ratios: ["9:16", "4:5"]
    dimensions:
      market:                      # a naming-convention part: replaces that part of the name
        HSV:
          hook_text: "Huntsville roofers: 9 reviews?"
          slots: {hook: {src: raw/hook_hsv.mov, in: 2.1, out: 5.4}}
          end_card: {subtext: "Huntsville contractors"}
        AUB:
          hook_text: "Auburn roofers: 9 reviews?"
          slots: {hook: {src: raw/hook_aub.mov, in: 1.0, out: 4.2}}
          end_card: {subtext: "Auburn-Opelika contractors"}
      offer:
        reviews497:
          slots: {offer: {src: raw/offer_497.mov, in: 10.2, out: 15.0}}
          callouts: [{text: "$497 setup (example)", at: 12.0, duration: 2.0, accent: true}]
        freesetup:
          slots: {offer: {src: raw/offer_free.mov, in: 3.3, out: 8.1}}
          remove: [callouts]
    only:                          # optional: render just these combinations
      - {market: HSV, offer: reviews497}
    skip:                          # optional: never render these
      - {market: AUB, offer: freesetup}

Patch rules: `slots` replaces fields of the clip(s) whose `slot` matches; `clips` replaces the
whole clip list; `remove` deletes keys; dicts merge, everything else is replaced. Dimension
names that are naming-convention parts (market, offer, angle, hooktype, length) rename that
part; any other dimension is appended to the angle part (e.g. lostjobs-price497) so
tools/metrics.py can still group results.

Usage:
    .venv/bin/python tools/variants.py work/edl/<base>.variants.yaml              # write EDLs + MATRIX.md
    .venv/bin/python tools/variants.py <file> --render --proxy                     # rough cuts of every variant
    .venv/bin/python tools/variants.py <file> --render --captions auto             # finals
"""
from __future__ import annotations

import argparse
import copy
import itertools
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_yaml  # noqa: E402

NAME_RE = re.compile(r"^(?P<market>[^_]+)_(?P<offer>[^_]+)_(?P<angle>[^_]+)_(?P<hooktype>[^_]+)_"
                     r"(?P<length>\d+)s_(?P<ratio>[^_]+)_v(?P<version>\d+)$")
NAME_PARTS = ("market", "offer", "angle", "hooktype", "length")
PART_RE = re.compile(r"^[A-Za-z0-9-]+$")


def deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if k == "slots":
            for slot, fields in (v or {}).items():
                hits = [c for c in out.get("clips", []) if c.get("slot") == slot]
                if not hits:
                    raise SystemExit(f"variant patch names slot {slot!r} but no clip in the base EDL has `slot: {slot}`")
                for c in hits:
                    c.update(copy.deepcopy(fields))
        elif k == "remove":
            for key in v or []:
                out.pop(key, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def variant_name(base_name: str, combo: dict[str, str]) -> str:
    m = NAME_RE.match(base_name)
    if not m:
        raise SystemExit(f"base name {base_name!r} does not follow the naming convention "
                         "{market}_{offer}_{angle}_{hooktype}_{length}s_{ratio}_v{n}")
    parts = m.groupdict()
    for dim, value in combo.items():
        if not PART_RE.match(value):
            raise SystemExit(f"variant value {value!r}: letters, digits and hyphens only")
        if dim in NAME_PARTS:
            parts[dim] = value
        else:
            parts["angle"] = f"{parts['angle']}-{value}"
    return f"{parts['market']}_{parts['offer']}_{parts['angle']}_{parts['hooktype']}_{parts['length']}s_{parts['ratio']}_v{parts['version']}"


def combos(spec: dict) -> list[dict[str, str]]:
    dims = spec.get("dimensions") or {}
    if not dims:
        raise SystemExit("variants file needs at least one entry under `dimensions`")
    keys = list(dims)
    all_combos = [dict(zip(keys, vals)) for vals in itertools.product(*(list(dims[k]) for k in keys))]
    only = spec.get("only")
    if only:
        all_combos = [c for c in all_combos if any(all(c.get(k) == v for k, v in o.items()) for o in only)]
    skip = spec.get("skip") or []
    return [c for c in all_combos if not any(all(c.get(k) == v for k, v in s.items()) for s in skip)]


def describe(patch: dict) -> str:
    bits = []
    for k, v in patch.items():
        if k == "slots":
            bits.append("swap " + ", ".join(f"{s} -> {f.get('src', '?')} {f.get('in', '')}-{f.get('out', '')}" for s, f in v.items()))
        elif k == "remove":
            bits.append("remove " + ", ".join(v))
        elif isinstance(v, str):
            bits.append(f'{k}: "{v[:40]}"')
        else:
            bits.append(f"{k} changed")
    return "; ".join(bits)


def materialize(spec_path: Path) -> list[dict]:
    spec = load_yaml(spec_path)
    base_path = (spec_path.parent / spec["base"]).resolve()
    base = load_yaml(base_path)
    out_dir = spec_path.parent / "variants"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for combo in combos(spec):
        edl = copy.deepcopy(base)
        notes = []
        for dim, value in combo.items():
            patch = spec["dimensions"][dim][value] or {}
            edl = deep_merge(edl, patch)
            notes.append(f"{dim}={value}: {describe(patch)}")
        edl["name"] = variant_name(base["name"], combo)
        edl["variant_of"] = base["name"]
        edl["variant"] = combo
        path = out_dir / f"{edl['name']}.yaml"
        path.write_text("# Generated by tools/variants.py from " + base_path.name + ". Edit the variants file, not this.\n"
                        + yaml.safe_dump(edl, sort_keys=False, allow_unicode=True))
        rows.append({"name": edl["name"], "combo": combo, "path": path, "notes": notes})
    ratios = spec.get("ratios") or [base.get("ratio") or "9:16"]
    md = [f"# Variant matrix for {base['name']}", "",
          f"{len(rows)} variants x {len(ratios)} ratio(s) = {len(rows) * len(ratios)} renders. "
          "All are `iteration` concepts of the base in DECISIONS.md (same angle, one variable changed).", "",
          "| variant | " + " | ".join(spec["dimensions"].keys()) + " | what changes |", "|---|" + "---|" * len(spec["dimensions"]) + "---|"]
    for r in rows:
        md.append(f"| {r['name']} | " + " | ".join(r["combo"][k] for k in spec["dimensions"]) + " | " + "<br>".join(r["notes"]) + " |")
    (out_dir / "MATRIX.md").write_text("\n".join(md) + "\n")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="<base>.variants.yaml")
    ap.add_argument("--render", action="store_true", help="render every variant in every ratio")
    ap.add_argument("--proxy", action="store_true")
    ap.add_argument("--captions", help="'auto' or none; per-variant words.json is not possible, so use auto on the Mac")
    args = ap.parse_args()
    spec_path = Path(args.spec)
    rows = materialize(spec_path)
    print(f"Wrote {len(rows)} variant EDLs and MATRIX.md to {spec_path.parent / 'variants'}")
    if not args.render:
        return 0
    import render  # noqa: WPS433

    ratios = load_yaml(spec_path).get("ratios") or [None]
    outputs = []
    for r in rows:
        for ratio in ratios:
            out = render.render(r["path"], ratio, args.captions, args.proxy, False, None)
            outputs.append(out)
            print(f"  {out.name}")
    print(f"Rendered {len(outputs)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
