"""Creative performance metrics from a Meta Ads export (Ads Manager CSV or Windsor.ai pull).

Definitions (sources disagree, so these are fixed for this engine):
    hook_rate      = 3-second video plays / impressions        (is the opening working?)
    hold_rate      = ThruPlays / 3-second video plays          (is the body working?)
    thruplay_rate  = ThruPlays / impressions                   (whole-video pull)
    ctr_link       = link clicks / impressions                 (is the offer/CTA working?)
    cpl            = spend / leads                             (is it making money?)
A ThruPlay is 15 s watched, or the full video if shorter, so hold_rate is only
comparable between ads of similar length.

Input: an Ads Manager CSV export, a Windsor.ai pull, or a JSON file saved from the Meta Ads MCP
(`ads_get_ad_entities` at ad level; a list of ad objects, nested metric dicts are flattened).
If rows carry a date column (daily breakdown), each ad also gets a fatigue read: CTR in the
last 7 days vs the 7 before, plus latest frequency (playbook `creative_fatigue`).

Also: video plays at 25/50/75/95/100% give a retention table, and with --render-dir exports the biggest drop
is mapped to what was on screen; a "qualified leads" column adds cost per qualified lead; --impression-cap N
ranks ads that reached N impressions on upstream signals (small-budget fair test).

Usage:
    .venv/bin/python tools/metrics.py data/export.csv --target-cpl 60 --out data/analysis
    .venv/bin/python tools/metrics.py data/export.csv --target-cpl 60 --out data/analysis --render-dir batches/<id>/exports --impression-cap 2000
    .venv/bin/python tools/metrics.py data/mcp_pull.json --target-cpl 60 --out data/analysis
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
    "p25": ["videoplaysat25", "videoplaysat25percent", "videop25watchedactions", "videop25watchedactionsvideoview"],
    "p50": ["videoplaysat50", "videoplaysat50percent", "videop50watchedactions", "videop50watchedactionsvideoview"],
    "p75": ["videoplaysat75", "videoplaysat75percent", "videop75watchedactions", "videop75watchedactionsvideoview"],
    "p95": ["videoplaysat95", "videoplaysat95percent", "videop95watchedactions", "videop95watchedactionsvideoview"],
    "p100": ["videoplaysat100", "videoplaysat100percent", "videop100watchedactions", "videop100watchedactionsvideoview"],
    "qualified_leads": ["qualifiedleads", "conversionleads", "submitapplication", "qualified"],
    "date": ["date", "day", "datestart", "reportingstarts", "daystart"],
}
QUARTILES = [("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p95", 0.95)]
MIN_IMPRESSIONS = 1000  # below this, rates are too noisy to read
NAME_RE = re.compile(r"^(?P<market>[A-Za-z0-9-]+)_(?P<offer>[A-Za-z0-9-]+)_(?:(?P<price>[A-Za-z0-9-]+)_)?(?P<angle>[A-Za-z0-9-]+)_"
                     r"(?P<hooktype>[A-Za-z0-9-]+)_(?P<length>\d+)s_(?P<ratio>\d+x\d+)_v(?P<version>\d+)")


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


def flatten(obj: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in obj.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "_"))
        elif isinstance(v, list) and v and all(isinstance(x, dict) and "action_type" in x for x in v):
            for x in v:  # Meta "actions" style lists: [{action_type: lead, value: 3}, ...]
                out[f"{key}_{x['action_type']}"] = x.get("value")
        else:
            out[key] = v
    return out


def load_rows(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".json":
        import json

        data = json.loads(path.read_text())
        if isinstance(data, dict):
            for k in ("ad_entities", "data", "ads", "rows"):
                if isinstance(data.get(k), list):
                    data = data[k]
                    break
        if not isinstance(data, list):
            raise SystemExit("JSON must be a list of ad objects (or a dict with ad_entities / data / ads / rows)")
        return pd.DataFrame([flatten(x) for x in data])
    return pd.read_csv(path)


def fatigue(df: pd.DataFrame) -> pd.DataFrame | None:
    """Per ad: link CTR over the last 7 days vs the 7 days before, and the latest frequency."""
    if "date" not in df.columns or "link_clicks" not in df.columns:
        return None
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date"])
    if d.empty:
        return None
    rows = []
    for name, g in d.groupby("ad_name"):
        last = g["date"].max()
        recent = g[g["date"] > last - pd.Timedelta(days=7)]
        before = g[(g["date"] <= last - pd.Timedelta(days=7)) & (g["date"] > last - pd.Timedelta(days=14))]
        if recent["impressions"].sum() < MIN_IMPRESSIONS or before["impressions"].sum() < MIN_IMPRESSIONS:
            continue
        ctr_r = recent["link_clicks"].sum() / recent["impressions"].sum()
        ctr_b = before["link_clicks"].sum() / before["impressions"].sum()
        drop = (ctr_b - ctr_r) / ctr_b if ctr_b else float("nan")
        freq = float(recent["frequency"].mean()) if "frequency" in g else float("nan")
        flag = ""
        if drop >= 0.15 and (pd.isna(freq) or freq >= 2.5):
            flag = "fatigue: refresh creative"
        elif drop >= 0.10:
            flag = "early warning"
        rows.append({"ad_name": name, "ctr_last7": ctr_r, "ctr_prev7": ctr_b, "ctr_drop": drop, "frequency": freq, "fatigue": flag})
    return pd.DataFrame(rows) if rows else None


def compute(df: pd.DataFrame) -> pd.DataFrame:
    df = map_columns(df)
    num = [c for c in ALIASES if c not in ("ad_name", "date") and c in df.columns]
    for c in num:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[,$]", "", regex=True), errors="coerce").fillna(0)
    sums = [c for c in num if c not in ("avg_watch_s", "frequency")]
    df.attrs["fatigue"] = fatigue(df)
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
    if "qualified_leads" in g:
        g["cost_per_qualified"] = ratio("spend", "qualified_leads")
    g["low_sample"] = g["impressions"] < MIN_IMPRESSIONS
    g.attrs["fatigue"] = df.attrs.get("fatigue")
    return g


def on_screen_at(sidecar: dict, t: float) -> str:
    """What the viewer was looking at, t seconds in: the graphic, B-roll or A-roll clip under that moment."""
    for g in sidecar.get("graphics", []):
        if g.get("type") not in ("progress", "backdrop") and float(g["at"]) <= t < float(g["at"]) + float(g["duration"]):
            return f"{g['type']} graphic" + (f" \"{str(g.get('text'))[:30]}\"" if g.get("text") else "")
    for b in sidecar.get("broll", []):
        if float(b["at"]) <= t < float(b["at"]) + float(b["duration"]):
            return f"B-roll {Path(str(b['src'])).stem}"
    for c in sidecar.get("clips", []):
        if float(c["at"]) <= t < float(c["at"]) + float(c["duration"]):
            return "end card" if c.get("src") == "end_card" else f"A-roll {Path(str(c['src'])).stem} ({c.get('layout', 'full')})"
    return "end of ad"


def retention(g: pd.DataFrame, render_dir: Path | None) -> pd.DataFrame | None:
    """Share of 3-second viewers still watching at 25/50/75/95%, the biggest drop, and (with the render sidecars)
    what was on screen when people left (Matt Wolfe, V20: read the retention curve, not just the totals)."""
    have = [q for q, _ in QUARTILES if q in g]
    if not have or "plays_3s" not in g:
        return None
    import json

    rows = []
    for _, r in g.iterrows():
        base = r["plays_3s"]
        if not base or base <= 0:
            continue
        curve = [(0.0, 1.0)] + [(f, r[q] / base) for q, f in QUARTILES if q in g]
        drops = [(a[0], b[0], a[1] - b[1]) for a, b in zip(curve, curve[1:])]
        worst = max(drops, key=lambda d: d[2])
        row = {"ad_name": r["ad_name"], **{q: (r[q] / base) for q, _ in QUARTILES if q in g},
               "biggest_drop": f"{worst[2]:.0%} between {worst[0]:.0%} and {worst[1]:.0%}"}
        sc = (render_dir / f"{r['ad_name']}.render.json") if render_dir else None
        if sc is not None and sc.exists():
            side = json.loads(sc.read_text())
            dur = float(side.get("duration") or 0)
            if dur:
                t = (worst[0] + worst[1]) / 2 * dur
                row["lost_around"] = f"{worst[0] * dur:.1f}-{worst[1] * dur:.1f}s, during {on_screen_at(side, t)}"
        rows.append(row)
    return pd.DataFrame(rows) if rows else None


def impression_cap(g: pd.DataFrame, cap: int) -> pd.DataFrame:
    """Small-budget fair test (Sergio C, V15): every ad gets about the same exposure, then ads that reached the cap
    are ranked on upstream signals. CPL at 1,000-3,000 impressions is noise; hook, hold, link CTR and CPM are not."""
    d = g.copy()
    d["reached_cap"] = d["impressions"] >= cap
    ok = d[d["reached_cap"]].copy()
    for col in ("hook_rate", "hold_rate", "ctr_link"):
        if col in ok:
            ok[f"{col}_rank"] = ok[col].rank(ascending=False)
    if "cpm" in ok:
        ok["cpm_rank"] = ok["cpm"].rank(ascending=True)
    rank_cols = [c for c in ok.columns if c.endswith("_rank")]
    if rank_cols:
        ok["fair_test_score"] = ok[rank_cols].mean(axis=1)
        ok = ok.sort_values("fair_test_score")
    waiting = d[~d["reached_cap"]][["ad_name", "impressions"]]
    ok.attrs["waiting"] = waiting
    return ok


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
    fat = g.attrs.get("fatigue")
    g = g.copy()
    g["diagnosis"] = notes
    g["verdict"] = verdicts
    g.attrs["fatigue"] = fat
    return g


def by_convention(g: pd.DataFrame) -> dict[str, pd.DataFrame]:
    parts = g["ad_name"].str.extract(NAME_RE)
    if parts.isna().all().all():
        return {}
    d = pd.concat([g, parts], axis=1).dropna(subset=["angle"])
    d["price"] = d["price"].fillna("noprice")
    out = {}
    cols = [c for c in ("spend", "impressions", "plays_3s", "thruplays", "link_clicks", "leads") if c in d]
    for dim in ("price", "angle", "hooktype", "length", "ratio"):
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
    ap.add_argument("csv", help="CSV export or JSON saved from the Meta Ads MCP")
    ap.add_argument("--target-cpl", type=float)
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--render-dir", help="exports folder with <ad>.render.json sidecars, to say what was on screen at each drop-off")
    ap.add_argument("--impression-cap", type=int, help="small-budget fair test: rank ads that reached this many impressions on upstream signals")
    args = ap.parse_args()
    g = diagnose(compute(load_rows(Path(args.csv))), args.target_cpl)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    g.to_csv(out / "ad_metrics.csv", index=False)
    cols = [c for c in ("ad_name", "spend", "impressions", "hook_rate", "hold_rate", "ctr_link", "leads", "cpl",
                        "qualified_leads", "cost_per_qualified", "diagnosis", "verdict") if c in g]
    md = ["# Ad metrics", "", f"Rates from {len(g)} ads. Medians use only ads with {MIN_IMPRESSIONS}+ impressions.",
          "Verdicts are heuristics from target CPL (see skill ad-results); confirm before pausing anything.", "",
          fmt(g.sort_values("spend", ascending=False)[cols]), ""]
    total_leads = g["leads"].sum() if "leads" in g else 0
    if total_leads < 30:
        md.append(f"> Caution: only {int(total_leads)} total leads. Pattern conclusions below are directional, not proven.\n")
    for dim, table in by_convention(g).items():
        md += [f"## By {dim}", "", fmt(table), ""]
    fat = g.attrs.get("fatigue")
    if fat is not None and len(fat):
        f = fat.copy()
        for c in ("ctr_last7", "ctr_prev7", "ctr_drop"):
            f[c] = f[c].map(lambda x: "" if pd.isna(x) else f"{x:.1%}")
        f["frequency"] = f["frequency"].map(lambda x: "" if pd.isna(x) else f"{x:.2f}")
        md += ["## Fatigue (last 7 days vs the 7 before)", "", f.to_markdown(index=False), ""]
    ret = retention(g, Path(args.render_dir) if args.render_dir else None)
    if ret is not None:
        r2 = ret.copy()
        for q, _ in QUARTILES:
            if q in r2:
                r2[q] = r2[q].map(lambda x: "" if pd.isna(x) else f"{x:.0%}")
        md += ["## Retention (share of 3-second viewers still watching)", "", r2.to_markdown(index=False), ""]
    if args.impression_cap:
        cap = impression_cap(g, args.impression_cap)
        cols = [c for c in ("ad_name", "impressions", "hook_rate", "hold_rate", "ctr_link", "cpm", "fair_test_score") if c in cap]
        md += [f"## Fair test at {args.impression_cap:,} impressions", "",
               "Ads that reached the cap, best first on hook rate, hold, link CTR and CPM together. Pausing an ad at the cap needs Bruce's yes.", "",
               fmt(cap[cols]) if len(cap) else "(no ad has reached the cap yet)", ""]
        waiting = cap.attrs.get("waiting")
        if waiting is not None and len(waiting):
            md += ["Still below the cap: " + ", ".join(f"{a} ({int(i):,})" for a, i in zip(waiting["ad_name"], waiting["impressions"])), ""]
    (out / "ad_metrics.md").write_text("\n".join(md))
    print(f"Wrote {out / 'ad_metrics.md'} and ad_metrics.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
