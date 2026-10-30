"""Creative performance metrics from a Meta Ads export (Ads Manager CSV or Windsor.ai pull).

Definitions (sources disagree, so these are fixed for this engine):
    hook_rate      = 3-second video plays / impressions        (is the opening working?)
    hold_rate      = ThruPlays / 3-second video plays          (is the body working?)
    thruplay_rate  = ThruPlays / impressions                   (whole-video pull)
    ctr_link       = link clicks / impressions                 (is the offer/CTA working?)
    cpl            = spend / leads                             (is it making money?)
A ThruPlay is 15 s watched, or the full video if shorter, so hold_rate is only
comparable between ads of similar length.

Usage:
    .venv/bin/python tools/metrics.py data/export.csv --target-cpl 60 --out data/analysis
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ALIASES = {
    "ad_name": ["adname", "ad", "name"],
    "spend": ["amountspentusd", "amountspent", "spend", "cost"],
    "impressions": ["impressions"],
    "plays_3s": ["3secondvideoplays", "3secondvideoviews", "videoplays3s", "actionsvideoview", "videoview"],
    "thruplays": ["thruplays", "thruplay", "videothruplaywatchedactionsvideoview", "videothruplaywatchedactions"],
    "link_clicks": ["linkclicks", "inlinelinkclicks", "actionslinkclick"],
    "leads": ["leads", "onfacebookleads", "actionslead", "leadsform", "results"],
    "avg_watch_s": ["videoaverageplaytime", "videoavgtimewatchedactionsvideoview", "averagewatchtime"],
    "frequency": ["frequency"],
}
MIN_IMPRESSIONS = 1000  # below this, rates are too noisy to read
NAME_RE = re.compile(r"^(?P<market>[^_]+)_(?P<offer>[^_]+)_(?P<angle>[^_]+)_(?P<hooktype>[^_]+)_"
                     r"(?P<length>\d+)s_(?P<ratio>[^_]+)_v(?P<version>\d+)")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    by_norm = {norm(c): c for c in df.columns}
    rename = {}
    for target, alias_list in ALIASES.items():
        for alias in [target.replace("_", "")] + alias_list:
            if alias in by_norm and by_norm[alias] not in rename:
                rename[by_norm[alias]] = target
                break
    df = df.rename(columns=rename)
    print("Column mapping: " + ", ".join(f"{src!r} -> {dst}" for src, dst in rename.items()))
    missing = [c for c in ("ad_name", "spend", "impressions") if c not in df.columns]
    if missing:
        raise SystemExit(f"Export is missing required columns {missing}. Columns seen: {list(df.columns)}")
    return df


def compute(df: pd.DataFrame) -> pd.DataFrame:
    df = map_columns(df)
    num = [c for c in ALIASES if c != "ad_name" and c in df.columns]
    for c in num:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[,$]", "", regex=True), errors="coerce").fillna(0)
    sums = [c for c in num if c not in ("avg_watch_s", "frequency")]
    g = df.groupby("ad_name", as_index=False)[sums].sum()  # exports split by day collapse to one row per ad

    def ratio(a, b):
        if a not in g or b not in g:
            return pd.Series([float("nan")] * len(g))
        return g[a] / g[b].where(g[b] > 0)

    g["hook_rate"] = ratio("plays_3s", "impressions")
    g["hold_rate"] = ratio("thruplays", "plays_3s")
    g["thruplay_rate"] = ratio("thruplays", "impressions")
    g["ctr_link"] = ratio("link_clicks", "impressions")
    g["cpl"] = ratio("spend", "leads")
    g["cpm"] = ratio("spend", "impressions") * 1000
    g["low_sample"] = g["impressions"] < MIN_IMPRESSIONS
    return g


def diagnose(g: pd.DataFrame, target_cpl: float | None) -> pd.DataFrame:
    ok = g[~g["low_sample"]]
    med = {m: ok[m].median() for m in ("hook_rate", "hold_rate", "ctr_link")} if len(ok) else {}
    notes, verdicts = [], []
    for _, r in g.iterrows():
        n = []
        if r["low_sample"]:
            n.append(f"low sample (<{MIN_IMPRESSIONS} impressions)")
        else:
            if pd.notna(r["hook_rate"]) and r["hook_rate"] < 0.8 * med["hook_rate"]:
                n.append("weak opening -> new visual + spoken hook")
            elif pd.notna(r["hold_rate"]) and r["hold_rate"] < 0.8 * med["hold_rate"]:
                n.append("hook ok, body loses them -> pacing/re-hooks/proof earlier")
            elif pd.notna(r["ctr_link"]) and r["ctr_link"] < 0.8 * med["ctr_link"]:
                n.append("watched but not clicked -> offer/CTA clarity")
        verdict = ""
        if target_cpl:
            leads = r.get("leads", 0)
            if r["spend"] < target_cpl:
                verdict = "too early"
            elif leads == 0 and r["spend"] >= 2 * target_cpl:
                verdict = "kill candidate"
            elif leads > 0 and r["cpl"] > 1.5 * target_cpl and r["spend"] >= 3 * target_cpl:
                verdict = "kill candidate"
            elif leads >= 3 and r["cpl"] <= target_cpl:
                verdict = "winner candidate"
            else:
                verdict = "keep running"
            if verdict != "too early" and leads > 0 and r["cpl"] > target_cpl and not n:
                n.append("engagement fine, leads expensive -> form/landing page, lead quality, audience")
        notes.append("; ".join(n))
        verdicts.append(verdict)
    g = g.copy()
    g["diagnosis"] = notes
    g["verdict"] = verdicts
    return g


def by_convention(g: pd.DataFrame) -> dict[str, pd.DataFrame]:
    parts = g["ad_name"].str.extract(NAME_RE)
    if parts.isna().all().all():
        return {}
    d = pd.concat([g, parts], axis=1).dropna(subset=["angle"])
    out = {}
    cols = [c for c in ("spend", "impressions", "plays_3s", "thruplays", "link_clicks", "leads") if c in d]
    for dim in ("angle", "hooktype", "length", "ratio"):
        s = d.groupby(dim)[cols].sum()
        s["ads"] = d.groupby(dim).size()
        if "plays_3s" in s:
            s["hook_rate"] = s["plays_3s"] / s["impressions"]
        if "thruplays" in s and "plays_3s" in s:
            s["hold_rate"] = s["thruplays"] / s["plays_3s"].where(s["plays_3s"] > 0)
        if "link_clicks" in s:
            s["ctr_link"] = s["link_clicks"] / s["impressions"]
        if "leads" in s:
            s["cpl"] = s["spend"] / s["leads"].where(s["leads"] > 0)
        out[dim] = s.reset_index()
    return out


def fmt(df: pd.DataFrame) -> str:
    d = df.copy()
    for c in ("hook_rate", "hold_rate", "thruplay_rate", "ctr_link"):
        if c in d:
            d[c] = d[c].map(lambda x: "" if pd.isna(x) else f"{x:.1%}")
    for c in ("spend", "cpl", "cpm"):
        if c in d:
            d[c] = d[c].map(lambda x: "" if pd.isna(x) else f"${x:,.2f}")
    return d.to_markdown(index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--target-cpl", type=float)
    ap.add_argument("--out", required=True, help="output folder")
    args = ap.parse_args()
    g = diagnose(compute(pd.read_csv(args.csv)), args.target_cpl)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    g.to_csv(out / "ad_metrics.csv", index=False)
    cols = [c for c in ("ad_name", "spend", "impressions", "hook_rate", "hold_rate", "ctr_link", "leads", "cpl",
                        "diagnosis", "verdict") if c in g]
    md = ["# Ad metrics", "", f"Rates from {len(g)} ads. Medians use only ads with {MIN_IMPRESSIONS}+ impressions.",
          "Verdicts are heuristics from target CPL (see skill ad-results); confirm before pausing anything.", "",
          fmt(g.sort_values("spend", ascending=False)[cols]), ""]
    total_leads = g["leads"].sum() if "leads" in g else 0
    if total_leads < 30:
        md.append(f"> Caution: only {int(total_leads)} total leads. Pattern conclusions below are directional, not proven.\n")
    for dim, table in by_convention(g).items():
        md += [f"## By {dim}", "", fmt(table), ""]
    (out / "ad_metrics.md").write_text("\n".join(md))
    print(f"Wrote {out / 'ad_metrics.md'} and ad_metrics.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
