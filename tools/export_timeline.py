"""Export a finished cut as a timeline for Premiere Pro, DaVinci Resolve or Final Cut Pro, so
the AI edit opens as real clips on real tracks for a finishing pass, not a flattened MP4.

Reads the render sidecar (exports/<adname>.render.json: every A-roll segment with its source
file and in/out, every B-roll window, every graphic) and writes:
    fcp7   Final Cut Pro 7 XML (xmeml): imports into Premiere Pro and DaVinci Resolve
    fcpx   Final Cut Pro X / 10 XML (fcpxml)
    otio   OpenTimelineIO JSON (any OTIO-aware tool)
Clips reference the ORIGINAL raw files by absolute path. Graphics become markers with the plate
type and text, since they are rendered plates, not NLE titles. Pause tightening is preserved
as separate segments; zoom punches and grades are not carried (do them in the NLE).

Usage:
    .venv/bin/python tools/export_timeline.py exports/<adname>.render.json --format fcp7
    .venv/bin/python tools/export_timeline.py exports/<adname>.render.json --format all --out exports/timelines
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import probe, video_stream  # noqa: E402


def build_timeline(sidecar: dict, base: Path):
    import opentimelineio as otio  # noqa: WPS433

    fps = float(sidecar.get("fps") or 30)
    w, h = sidecar.get("size") or [1080, 1920]
    tl = otio.schema.Timeline(name=sidecar.get("name", "ad"))
    tl.metadata["ad_video_engine"] = {"ratio": sidecar.get("ratio"), "size": [w, h]}
    v1 = otio.schema.Track(name="V1 A-roll", kind=otio.schema.TrackKind.Video)
    v2 = otio.schema.Track(name="V2 B-roll", kind=otio.schema.TrackKind.Video)
    tl.tracks.append(v1)
    tl.tracks.append(v2)

    def rt(sec: float):
        return otio.opentime.RationalTime(round(sec * fps), fps)

    refs: dict[str, otio.schema.ExternalReference] = {}

    def ref_for(src: str):
        if src in refs:
            return refs[src]
        p = Path(src)
        p = p if p.is_absolute() else (base / p)
        dur = None
        try:
            info = probe(p)
            dur = float(info["format"]["duration"])
        except Exception:  # noqa: BLE001
            dur = 3600.0
        refs[src] = otio.schema.ExternalReference(target_url=p.resolve().as_uri(),
                                                  available_range=otio.opentime.TimeRange(rt(0), rt(dur)))
        return refs[src]

    for c in sidecar.get("clips", []):
        if c.get("src") == "end_card":
            v1.append(otio.schema.Gap(name="end card (rendered plate)", source_range=otio.opentime.TimeRange(rt(0), rt(c["duration"]))))
            continue
        clip = otio.schema.Clip(name=Path(c["src"]).stem, media_reference=ref_for(c["src"]),
                                source_range=otio.opentime.TimeRange(rt(c["src_in"]), rt(c["duration"])))
        clip.metadata["ad_video_engine"] = {k: c.get(k) for k in ("zoom", "push", "layout", "focus") if c.get(k) is not None}
        v1.append(clip)

    cursor = 0.0
    for b in sorted(sidecar.get("broll", []), key=lambda x: x["at"]):
        at, dur = float(b["at"]), float(b["duration"])
        if at > cursor + 1 / fps:
            v2.append(otio.schema.Gap(source_range=otio.opentime.TimeRange(rt(0), rt(at - cursor))))
        clip = otio.schema.Clip(name=Path(b["src"]).stem, media_reference=ref_for(b["src"]),
                                source_range=otio.opentime.TimeRange(rt(float(b.get("src_in") or 0.0)), rt(dur)))
        clip.metadata["ad_video_engine"] = {"pip": bool(b.get("pip")), "label": b.get("label")}
        v2.append(clip)
        cursor = at + dur

    for g in sidecar.get("graphics", []):
        m = otio.schema.Marker(name=f"{g['type']}: {g.get('text') or ''}".strip(),
                               marked_range=otio.opentime.TimeRange(rt(g["at"]), rt(g["duration"])),
                               color=otio.schema.MarkerColor.ORANGE)
        v1.markers.append(m)
    cap = sidecar.get("captions") or {}
    if cap.get("pages") and Path(cap["pages"]).exists():
        for pg in json.loads(Path(cap["pages"]).read_text()):
            v1.markers.append(otio.schema.Marker(name=f"caption: {pg['text']}", color=otio.schema.MarkerColor.CYAN,
                                                 marked_range=otio.opentime.TimeRange(rt(pg["start"]), rt(max(0.0, pg["end"] - pg["start"])))))
    return tl


def export(sidecar_path: Path, fmt: str, out_dir: Path | None) -> list[Path]:
    import opentimelineio as otio  # noqa: WPS433

    sidecar = json.loads(sidecar_path.read_text())
    base = sidecar_path.resolve().parent.parent   # exports/ sits in the batch folder
    tl = build_timeline(sidecar, base)
    out_dir = out_dir or sidecar_path.parent / "timelines"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = sidecar.get("name") or sidecar_path.stem.replace(".render", "")
    fmts = ["fcp7", "fcpx", "otio"] if fmt == "all" else [fmt]
    written = []
    for f in fmts:
        if f == "fcp7":
            p = out_dir / f"{name}_premiere_resolve.xml"
            otio.adapters.write_to_file(tl, str(p), adapter_name="fcp_xml")
        elif f == "fcpx":
            p = out_dir / f"{name}_finalcut.fcpxml"
            otio.adapters.write_to_file(tl, str(p), adapter_name="fcpx_xml")
        else:
            p = out_dir / f"{name}.otio"
            otio.adapters.write_to_file(tl, str(p), adapter_name="otio_json")
        written.append(p)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sidecar", help="exports/<adname>.render.json")
    ap.add_argument("--format", default="fcp7", choices=("fcp7", "fcpx", "otio", "all"))
    ap.add_argument("--out", help="folder (default exports/timelines)")
    args = ap.parse_args()
    for p in export(Path(args.sidecar), args.format, Path(args.out) if args.out else None):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
