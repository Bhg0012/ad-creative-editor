"""Build a sample ad from stand-in clips so the pipeline can be seen working with no footage.

Creates batches/<date>_SAMPLE_demo/ with synthesized voice (macOS `say` or ffmpeg's flite),
labeled placeholder A-roll (one landscape take, one portrait take), a mock B-roll insert,
a stand-in proof image, a music bed and a whoosh, then runs the real pipeline:
selects-style EDL -> render master -> captions -> final -> QA.

Because no transcription backend is needed here, caption timing comes from the known
speech timings mapped through the render sidecar (exactly what tools/transcribe.py would
produce from the master).

Usage:
    .venv/bin/python tools/make_sample.py            # writes batches/<date>_SAMPLE_demo/exports/*.mp4
    .venv/bin/python tools/make_sample.py --style hormozi
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, ffmpeg, find_font, load_config, probe, run_ffmpeg  # noqa: E402

# Caption pages (2-4 words) per sentence. Numbers are examples; this is a stand-in, not an ad.
SCRIPT = [
    ["Huntsville roofers.", "Your competitor has", "140 Google reviews.", "You have nine."],
    ["Same quality work.", "They get the call.", "You don't."],
    ["AuburnSEO sends", "a review request", "to every customer,", "automatically."],
    ["Tap learn more", "and I'll show you", "how it works."],
]
PAGE_GAP, SENTENCE_GAP, LEAD_IN = 0.12, 0.65, 0.6


def say(text: str, out_wav: Path) -> None:
    """Synthesize one caption page to a 48 kHz mono wav."""
    if shutil.which("say"):
        aiff = out_wav.with_suffix(".aiff")
        subprocess.run(["say", "-o", str(aiff), text], check=True)
        run_ffmpeg(["-i", str(aiff), "-ar", "48000", "-ac", "1", str(out_wav)])
        aiff.unlink()
    else:
        tf = out_wav.with_suffix(".txt")
        tf.write_text(text)
        run_ffmpeg(["-f", "lavfi", "-i", f"flite=textfile={tf}:voice=rms", "-ar", "48000", "-ac", "1", str(out_wav)])
        tf.unlink()


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def build_voice(sentences: list[list[str]], tmp: Path, out_wav: Path) -> list[dict]:
    """Concatenate synthesized pages with gaps. Returns word timings in the take's timeline."""
    parts, words, t = [], [], LEAD_IN
    parts.append(("silence", LEAD_IN))
    for si, pages in enumerate(sentences):
        for pi, page in enumerate(pages):
            wav = tmp / f"p{si}_{pi}.wav"
            say(page, wav)
            d = duration(wav)
            toks = page.split()
            weights = [len(w) + 1 for w in toks]
            cursor = t + 0.04
            for w, wt in zip(toks, weights):
                wd = (d - 0.08) * wt / sum(weights)
                words.append({"word": w, "start": round(cursor, 3), "end": round(cursor + wd, 3), "prob": 1.0})
                cursor += wd
            parts.append(("file", wav))
            t += d
            gap = SENTENCE_GAP if pi == len(pages) - 1 else PAGE_GAP
            parts.append(("silence", gap))
            t += gap
    inputs, fc, n = [], [], 0
    for kind, v in parts:
        if kind == "silence":
            inputs += ["-f", "lavfi", "-t", f"{v:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
        else:
            inputs += ["-i", str(v)]
        fc.append(f"[{n}:a]")
        n += 1
    run_ffmpeg([*inputs, "-filter_complex", f"{''.join(fc)}concat=n={n}:v=0:a=1[a]", "-map", "[a]", str(out_wav)])
    return words


def placeholder_take(voice_wav: Path, out: Path, size: str, label: str, colors: tuple[str, str], font: str) -> None:
    w, h = (int(x) for x in size.split("x"))
    d = duration(voice_wav)
    # Text goes through files: colons and commas inside drawtext text= break newer ffmpeg filter parsers.
    label_f = out.with_suffix(".label.txt")
    label_f.write_text(label)
    sub_f = out.with_suffix(".sub.txt")
    sub_f.write_text("STAND-IN FOOTAGE")
    head = f"drawbox=x=(iw-{w // 4})/2:y=ih*0.22:w={w // 4}:h={h // 2}:color=white@0.18:t=fill"
    txt = (f"drawtext=fontfile='{font}':textfile='{label_f}':fontsize={h // 22}:fontcolor=white@0.9:x=(w-text_w)/2:y=h*0.80,"
           f"drawtext=fontfile='{font}':textfile='{sub_f}':fontsize={h // 30}:fontcolor=white@0.6:x=(w-text_w)/2:y=h*0.80+{h // 16}")
    run_ffmpeg(["-f", "lavfi", "-t", f"{d:.3f}", "-i", f"gradients=s={size}:c0=0x{colors[0]}:c1=0x{colors[1]}:nb_colors=2:speed=0.015:r=30",
                "-i", str(voice_wav), "-vf", f"{head},{txt},format=yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)])
    label_f.unlink()
    sub_f.unlink()


def mock_broll(out: Path, font: str) -> None:
    t1_f, t2_f = out.with_suffix(".t1.txt"), out.with_suffix(".t2.txt")
    t1_f.write_text("Review request sent")
    t2_f.write_text("to Mike T. (example)")
    box = "drawbox=x=90:y=760:w=900:h=300:color=white@0.95:t=fill"
    t1 = f"drawtext=fontfile='{font}':textfile='{t1_f}':fontsize=58:fontcolor=0x1f2a44:x=140:y=820"
    t2 = f"drawtext=fontfile='{font}':textfile='{t2_f}':fontsize=44:fontcolor=0x3B96F6:x=140:y=920"
    run_ffmpeg(["-f", "lavfi", "-t", "3", "-i", "color=c=0x101522:s=1080x1920:r=30", "-vf", f"{box},{t1},{t2},format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an", str(out)])
    t1_f.unlink()
    t2_f.unlink()


def mock_still(out: Path, font: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1440, 1800), "#f3f4f6")
    d = ImageDraw.Draw(img)
    f1, f2 = ImageFont.truetype(font, 90), ImageFont.truetype(font, 56)
    d.rounded_rectangle((120, 420, 1320, 1380), radius=40, fill="white", outline="#d0d4da", width=4)
    d.text((720, 640), "4.9 stars", font=f1, fill="#1f2a44", anchor="mm")
    d.text((720, 780), "140 reviews (example)", font=f2, fill="#3B96F6", anchor="mm")
    d.text((720, 1150), "STAND-IN PROOF IMAGE", font=f2, fill="#9aa1ab", anchor="mm")
    img.save(out)


def music_and_sfx(music: Path, sfx: Path) -> None:
    expr = "0.10*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*1.8*t))+0.07*sin(2*PI*164.8*t)+0.05*sin(2*PI*220*t)*(0.5+0.5*sin(2*PI*0.9*t))"
    run_ffmpeg(["-f", "lavfi", "-t", "40", "-i", f"aevalsrc='{expr}':s=48000", "-c:a", "libmp3lame", "-q:a", "3", str(music)])
    run_ffmpeg(["-f", "lavfi", "-t", "0.4", "-i", "anoisesrc=c=pink:r=48000:a=0.5", "-af", "afade=t=in:d=0.1,afade=t=out:st=0.15:d=0.25,highpass=f=800",
                str(sfx)])


def remap_words(sidecar: dict, source_words: dict[str, list[dict]]) -> list[dict]:
    """Source-time words -> master-timeline words using the render sidecar's clip map."""
    out = []
    for seg in sidecar["clips"]:
        if seg["src"] not in source_words:
            continue
        for w in source_words[seg["src"]]:
            mid = (w["start"] + w["end"]) / 2
            if seg["src_in"] <= mid <= seg["src_out"]:
                off = seg["at"] - seg["src_in"]
                start = max(w["start"], seg["src_in"]) + off
                end = min(w["end"], seg["src_out"]) + off
                out.append({**w, "start": round(start, 3), "end": round(max(end, start + 0.05), 3)})
    return sorted(out, key=lambda w: w["start"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default=None, help="caption style override (chunk, highlight, karaoke, reveal, hormozi)")
    ap.add_argument("--batch", default=None, help="batch folder (default batches/<date>_SAMPLE_demo)")
    args = ap.parse_args()
    import render  # noqa: WPS433

    cfg = load_config()
    font, _ = find_font((cfg.get("business") or {}).get("caption_font_name") or "Montserrat ExtraBold")
    batch = Path(args.batch) if args.batch else ROOT / "batches" / f"{dt.date.today().isoformat()}_SAMPLE_demo"
    for d in ("raw", "audio", "work/edl", "work/transcripts", "work/cuts", "work/proxies", "exports", "qa"):
        (batch / d).mkdir(parents=True, exist_ok=True)
    (batch / "BATCH.md").write_text("# SAMPLE batch\n\nStand-in clips made by tools/make_sample.py. Not for upload.\n")
    tmp = batch / "work" / "tmp_sample"
    tmp.mkdir(exist_ok=True)

    print("1/5 synthesizing voice")
    take1_words = build_voice(SCRIPT, tmp, tmp / "take1.wav")
    take2_words = build_voice(SCRIPT[:1], tmp, tmp / "take2.wav")
    print("2/5 building stand-in clips")
    placeholder_take(tmp / "take1.wav", batch / "raw" / "take1_landscape.mp4", "1920x1080", "Take 1, landscape 16:9", ("1f2a44", "3B96F6"), font)
    placeholder_take(tmp / "take2.wav", batch / "raw" / "take2_portrait.mp4", "1080x1920", "Take 2, portrait 9:16", ("2b1d3a", "E55B13"), font)
    mock_broll(batch / "raw" / "broll_review_request.mp4", font)
    mock_still(batch / "raw" / "proof_stand_in.png", font)
    music_and_sfx(batch / "audio" / "music_bed.mp3", batch / "audio" / "whoosh.wav")
    for name, words in (("take1_landscape", take1_words), ("take2_portrait", take2_words)):
        (batch / "work" / "transcripts" / f"{name}.words.json").write_text(json.dumps(words, indent=1))

    # Sentence boundaries in take1, from the word timings
    s_bounds = []
    i = 0
    for pages in SCRIPT:
        n = sum(len(p.split()) for p in pages)
        s_bounds.append((take1_words[i]["start"], take1_words[i + n - 1]["end"]))
        i += n
    s2_start, s3_end = s_bounds[1][0], s_bounds[2][1]
    s4_start, s4_end = s_bounds[3]
    hook_end = take2_words[-1]["end"]
    broll_at = None  # filled after the master renders (needs the timeline)
    name = "SAMPLE_demo_lostjobs_callout_15s_9x16_v1"
    edl = f"""# Sample EDL written by tools/make_sample.py. Edit and re-render with tools/render.py.
name: {name}
ratio: "9:16"
hook_text: "9 reviews vs 140? (example)"
hook_text_seconds: 2.5
clips:
  - {{src: raw/take2_portrait.mp4, in: {LEAD_IN - 0.25:.2f}, out: {hook_end + 0.25:.2f}, zoom: 1.0}}
  - {{src: raw/take1_landscape.mp4, in: {s2_start - 0.2:.2f}, out: {s3_end + 0.2:.2f}, zoom: 1.08, focus: [0.5, 0.45], tighten: 0.45}}
  - {{src: raw/proof_stand_in.png, duration: 1.6, push: 1.10}}
  - {{src: raw/take1_landscape.mp4, in: {s4_start - 0.2:.2f}, out: {s4_end + 0.3:.2f}, zoom: 1.0, focus: [0.5, 0.45]}}
broll:
  - {{src: raw/broll_review_request.mp4, at: BROLL_AT, duration: 2.2, label: "A review request goes out"}}
lower_third: {{text: "Bruce, Auburn AL", at: 0.6, duration: 2.5}}
music: {{src: audio/music_bed.mp3, gain_db: -20, duck: true, fade_out: 1.0}}
sfx:
  - {{src: audio/whoosh.wav, at: BROLL_AT, gain_db: -14}}
end_card: {{text: "Tap Learn More", subtext: "Sample edit, stand-in footage", seconds: 2.5, logo: true}}
"""
    # First pass with a provisional B-roll time to get the timeline, then place B-roll on "AuburnSEO sends"
    edl_path = batch / "work" / "edl" / f"{name}.yaml"
    edl_path.write_text(edl.replace("BROLL_AT", "6.0"))
    print("3/5 rendering master")
    master = render.render(edl_path, None, None, proxy=False, keep_tmp=False, out_dir=None)
    total = float(render.probe(master)["format"]["duration"])
    new_name = name.replace("_15s_", f"_{int(round(total))}s_")   # name carries the real length
    edl = edl.replace(name, new_name)
    edl_path.unlink()
    name = new_name
    edl_path = batch / "work" / "edl" / f"{name}.yaml"
    edl_path.write_text(edl.replace("BROLL_AT", "6.0"))
    src_words = {"raw/take1_landscape.mp4": take1_words, "raw/take2_portrait.mp4": take2_words}
    tl = render.timeline_of(edl_path)
    master_words = remap_words({"clips": tl}, src_words)
    s3_word = next(w for w in master_words if w["word"].startswith("AuburnSEO"))
    broll_at = round(s3_word["start"] + 0.15, 2)
    edl_path.write_text(edl.replace("BROLL_AT", f"{broll_at:.2f}"))
    words_json = batch / "work" / "transcripts" / f"{name}_master.words.json"
    words_json.write_text(json.dumps(master_words, indent=1))
    if args.style:
        cfg_captions = cfg.setdefault("captions", {})
        cfg_captions["style"] = args.style
        render.load_config = lambda: cfg  # style override for this run only
    print("4/5 rendering final with captions")
    final = render.render(edl_path, None, str(words_json), proxy=False, keep_tmp=False, out_dir=None)
    print("5/5 QA")
    import qa  # noqa: WPS433

    report = qa.qa_one(final, batch / "qa", float(cfg["audio"]["target_lufs"]), float(cfg["audio"]["true_peak_max_dbtp"]))
    fails = [c for c in report["results"] if c["status"] == "FAIL"]
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nSample ad: {final}\nEDL: {edl_path}\nQA: {len(fails)} automated FAIL(s); evidence in {batch / 'qa' / final.stem}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
