"""One-page local review site for a batch: every export with its player, timeline, captions,
QA status and copy, plus a notes box whose contents you copy back into the chat.

Usage:
    .venv/bin/python tools/review.py batches/<id>            # writes batches/<id>/review/index.html
    cd batches/<id> && python3 -m http.server 8000           # then open http://<mac-ip>:8000/review/ on your phone
No dependencies, no network: the page links to the local files next to it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

CSS = """
body{font-family:-apple-system,Helvetica,Arial,sans-serif;margin:0;background:#0f1115;color:#e8eaf0}
header{padding:16px 20px;border-bottom:1px solid #2a2f3a}h1{font-size:18px;margin:0}
.ad{display:grid;grid-template-columns:minmax(220px,320px) 1fr;gap:20px;padding:20px;border-bottom:1px solid #2a2f3a}
video{width:100%;max-height:70vh;background:#000;border-radius:10px}
h2{font-size:16px;margin:0 0 8px}table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
td,th{border-bottom:1px solid #2a2f3a;padding:4px 6px;text-align:left;vertical-align:top}
.PASS{color:#4ade80}.FAIL{color:#f87171;font-weight:bold}.WARN{color:#fbbf24}.MANUAL{color:#93c5fd}
textarea{width:100%;min-height:90px;background:#161a22;color:#e8eaf0;border:1px solid #2a2f3a;border-radius:8px;padding:8px}
button{background:#3B96F6;color:#fff;border:0;border-radius:8px;padding:8px 12px;margin-top:6px}
details{margin:6px 0}summary{cursor:pointer;color:#93c5fd}pre{white-space:pre-wrap;font-size:12px;background:#161a22;padding:8px;border-radius:8px}
.chip{display:inline-block;background:#1f2532;border-radius:999px;padding:2px 10px;font-size:12px;margin:2px}
@media(max-width:700px){.ad{grid-template-columns:1fr}}
"""
JS = """
function copyNotes(){const out=[];document.querySelectorAll('textarea').forEach(t=>{if(t.value.trim())out.push('## '+t.dataset.ad+'\\n'+t.value.trim())});
const txt=out.join('\\n\\n')||'(no notes)';navigator.clipboard.writeText(txt).then(()=>alert('Notes copied. Paste them into the chat.'));}
function stamp(btn){const sec=btn.closest('section');const v=sec.querySelector('video');const t=sec.querySelector('textarea');
const s=v.currentTime;const m=Math.floor(s/60),ss=(s%60).toFixed(1).padStart(4,'0');t.value=(t.value?t.value.replace(/\\s*$/,'')+'\\n':'')+m+':'+ss+'  ';t.focus();}
"""


def ass_text(path: Path) -> list[str]:
    lines = []
    for line in path.read_text().splitlines():
        if line.startswith("Dialogue:"):
            text = line.split(",", 9)[-1]
            text = re.sub(r"\{[^}]*\}", "", text).replace(r"\N", " ")
            if not lines or lines[-1] != text:
                lines.append(text)
    return lines


def qa_rows(batch: Path, stem: str) -> list[dict]:
    rep = batch / "qa" / stem / "report.json"
    return json.loads(rep.read_text())["results"] if rep.exists() else []


def build(batch: Path) -> Path:
    exports = sorted((batch / "exports").glob("*.mp4")) if (batch / "exports").exists() else []
    proxies = sorted((batch / "work" / "proxies").glob("*.mp4")) if (batch / "work" / "proxies").exists() else []
    statics = sorted((batch / "statics").glob("*.png")) if (batch / "statics").exists() else []
    out_dir = batch / "review"
    out_dir.mkdir(exist_ok=True)
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Review {html.escape(batch.name)}</title><style>{CSS}</style></head><body>",
             f"<header><h1>{html.escape(batch.name)}</h1><div>{len(exports)} finals, {len(proxies)} proxies, {len(statics)} statics. "
             f"Generated {dt.datetime.now():%Y-%m-%d %H:%M}. Write notes under each ad, then tap Copy all notes.</div>"
             f"<button onclick='copyNotes()'>Copy all notes</button></header>"]
    for group, files in (("Finals", exports), ("Proxies (rough cuts)", proxies)):
        if not files:
            continue
        parts.append(f"<h2 style='padding:16px 20px 0'>{group}</h2>")
        for f in files:
            rel = f.relative_to(batch).as_posix()
            stem = f.stem.replace("_proxy", "")
            sidecar = batch / "exports" / f"{stem}.render.json"
            tl = json.loads(sidecar.read_text()) if sidecar.exists() else None
            parts.append(f"<section class='ad'><div><video controls playsinline preload='metadata' src='../{rel}'></video></div><div>")
            parts.append(f"<h2>{html.escape(f.name)}</h2>")
            if tl:
                parts.append(f"<span class='chip'>{tl['size'][0]}x{tl['size'][1]}</span><span class='chip'>{tl['duration']:.1f}s</span>"
                             f"<span class='chip'>{tl['fps']} fps</span><span class='chip'>captions: {html.escape(str((tl.get('captions') or {}).get('style', 'none')))}</span>")
                parts.append("<details open><summary>Timeline</summary><table><tr><th>at</th><th>len</th><th>what</th></tr>")
                for c in tl["clips"]:
                    what = c["src"] if c["src"] == "end_card" else f"{c['src']} [{c.get('src_in')}-{c.get('src_out')}] zoom {c.get('zoom', '')} {('push ' + str(c['push'])) if c.get('push') else ''}"
                    parts.append(f"<tr><td>{c['at']:.2f}</td><td>{c['duration']:.2f}</td><td>{html.escape(what)}</td></tr>")
                for b in tl.get("broll", []):
                    parts.append(f"<tr><td>{b['at']:.2f}</td><td>{b['duration']:.2f}</td><td>B-roll {html.escape(b['src'])}{' (pip)' if b.get('pip') else ''} {html.escape(b.get('label') or '')}</td></tr>")
                for g in tl.get("graphics", []):
                    parts.append(f"<tr><td>{g['at']:.2f}</td><td>{g['duration']:.2f}</td><td>{g['type']}: {html.escape(str(g.get('text', '')))}</td></tr>")
                parts.append("</table></details>")
                caps = tl.get("captions") or {}
                if caps.get("ass") and Path(caps["ass"]).is_file():
                    parts.append("<details><summary>Captions</summary><pre>" + html.escape("\n".join(ass_text(Path(caps["ass"])))) + "</pre></details>")
                elif caps.get("pages") and Path(caps["pages"]).is_file():
                    pages = json.loads(Path(caps["pages"]).read_text())
                    parts.append("<details><summary>Captions</summary><pre>" + html.escape("\n".join(f"{p['start']:6.2f}  {p['text']}" for p in pages)) + "</pre></details>")
            rows = qa_rows(batch, f.stem)
            if rows:
                fails = sum(r["status"] == "FAIL" for r in rows)
                parts.append(f"<details {'open' if fails else ''}><summary>QA: {fails} FAIL, {sum(r['status'] == 'WARN' for r in rows)} WARN</summary><table>")
                for r in rows:
                    parts.append(f"<tr><td>{html.escape(r['check'])}</td><td class='{r['status']}'>{r['status']}</td><td>{html.escape(r['detail'])}</td></tr>")
                parts.append("</table></details>")
            copy_md = batch / "exports" / f"{stem}_copy.md"
            if copy_md.exists():
                parts.append("<details><summary>Copy package</summary><pre>" + html.escape(copy_md.read_text()) + "</pre></details>")
            parts.append(f"<textarea data-ad='{html.escape(f.name)}' placeholder='Notes for this ad. Pause the video and tap Stamp time to insert the timecode.'></textarea>"
                         f"<button onclick='stamp(this)'>Stamp time</button></div></section>")
    if statics:
        parts.append("<h2 style='padding:16px 20px 0'>Statics</h2><div style='display:flex;flex-wrap:wrap;gap:12px;padding:20px'>")
        for s in statics:
            parts.append(f"<figure style='margin:0;max-width:300px'><img src='../{s.relative_to(batch).as_posix()}' style='width:100%;border-radius:8px'><figcaption style='font-size:12px'>{html.escape(s.name)}</figcaption></figure>")
        parts.append("</div>")
    parts.append(f"<script>{JS}</script></body></html>")
    out = out_dir / "index.html"
    out.write_text("\n".join(parts))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    args = ap.parse_args()
    out = build(Path(args.batch))
    print(f"Wrote {out}\nServe: cd {Path(args.batch)} && python3 -m http.server 8000  (then open /review/ on your phone)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
