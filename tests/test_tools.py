"""Tests for the engine's tools, using synthetic media generated with ffmpeg."""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import captions  # noqa: E402
import common  # noqa: E402
import doctor  # noqa: E402
import inventory  # noqa: E402
import metrics  # noqa: E402
import new_batch  # noqa: E402
import qa  # noqa: E402
import transcribe  # noqa: E402

FF = common.ffmpeg()
EM_DASH = chr(0x2014)  # built at runtime so this file passes its own check


def ff(*args: str) -> None:
    subprocess.run([FF, "-nostdin", "-y", "-v", "error", *args], check=True)


def make_ad(path: Path, size="1080x1920", seconds=6, extra_v=(), extra_a=("-ac", "2")) -> Path:
    """Synthetic ad with speech-like audio normalized to -14 LUFS via the two-pass recipe."""
    raw = path.with_suffix(".raw.mp4")
    ff("-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={seconds}",
       "-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=48000:duration={seconds}",
       "-af", "volume=0.3,apulsator=hz=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(raw))
    err = subprocess.run([FF, "-nostdin", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    af = ("loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:"
          "measured_thresh={input_thresh}:offset={target_offset}:linear=true").format(**m)
    ff("-i", str(raw), "-af", af, "-ar", "48000", *extra_a, "-c:v", "libx264", "-pix_fmt", "yuv420p", *extra_v,
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(path))
    raw.unlink()
    return path


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    good = make_ad(d / "HSV_reviews_test_question_6s_9x16_v1.mp4")
    twin = make_ad(d / "HSV_reviews_test2_story_6s_9x16_v1.mp4")
    bad = make_ad(d / "bad.mp4", size="1000x1000", extra_a=("-ac", "1"))
    return {"dir": d, "good": good, "twin": twin, "bad": bad}


# ---------- qa ----------

def statuses(report):
    return {c["check"]: c["status"] for c in report["results"]}


def test_qa_passes_good_ad(media, tmp_path):
    r = qa.qa_one(media["good"], tmp_path, -14, -1.0)
    s = statuses(r)
    fails = {k: v for k, v in s.items() if v == "FAIL"}
    assert not fails, r["results"]
    assert s["integrated loudness"] == "PASS" and s["true peak"] == "PASS"
    assert s["length vs name"] == "PASS"
    out = tmp_path / media["good"].stem
    for name in ("first_frame.png", "first_frame_360.png", "contact_sheet.png",
                 "safezone_00_start.png", "mobile360_50pct.png", "report.json"):
        assert (out / name).stat().st_size > 0, name


def test_qa_flags_bad_ad(media, tmp_path):
    s = statuses(qa.qa_one(media["bad"], tmp_path, -14, -1.0))
    assert s.get("aspect ratio") == "FAIL" or s.get("resolution") == "FAIL"
    assert s["audio channels"] == "FAIL"
    assert s["naming convention"] == "WARN"


def test_qa_loudness_fails_when_quiet(media, tmp_path):
    quiet = tmp_path / "quiet_6s_.mp4"
    ff("-i", str(media["good"]), "-af", "volume=-12dB", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(quiet))
    s = statuses(qa.qa_one(quiet, tmp_path, -14, -1.0))
    assert s["integrated loudness"] == "FAIL"


def test_similarity_flags_identical_openings(media):
    assert qa.similarity_checks([media["good"], media["twin"]])  # same testsrc frame -> flagged


def test_safe_box_rounds_up():
    assert common.safe_box(1080, 1920, "9:16") == {"top": 269, "bottom": 672, "side": 65}
    assert common.safe_box(1440, 2560, "9:16") == {"top": 359, "bottom": 896, "side": 87}


# ---------- captions ----------

WORDS = [
    {"word": "Huntsville", "start": 0.00, "end": 0.40}, {"word": "roofers,", "start": 0.42, "end": 0.80},
    {"word": "your", "start": 0.85, "end": 1.00}, {"word": "competitor", "start": 1.02, "end": 1.50},
    {"word": "has", "start": 1.52, "end": 1.70}, {"word": "140", "start": 1.72, "end": 2.10},
    {"word": "reviews.", "start": 2.12, "end": 2.60}, {"word": "auburn", "start": 3.20, "end": 3.50},
    {"word": "seo", "start": 3.52, "end": 3.80}, {"word": "fixes", "start": 3.82, "end": 4.10},
    {"word": "that.", "start": 4.12, "end": 4.50},
]


def test_caption_chunks_and_highlight():
    words = captions.apply_fixes(WORDS, {"auburn seo": "AuburnSEO"})
    assert [w["word"] for w in words][7] == "AuburnSEO"
    chunks = captions.chunk(words, 4)
    assert all(1 <= len(c) <= 4 for c in chunks)
    assert [w["word"] for w in chunks[0]] == ["Huntsville", "roofers,"]  # comma ends a chunk
    assert sum(len(c) for c in chunks) == len(words)
    k = captions.pick_keyword(chunks[1], set())
    assert chunks[1][k]["word"] == "140"  # numbers win emphasis


def test_caption_ass_inside_safe_zone_and_burns(tmp_path, media):
    ass = captions.build_ass(WORDS, 1080, 1920, font="DejaVu Sans", accent="#E55B13", keywords={"reviews."})
    style = next(line for line in ass.splitlines() if line.startswith("Style: Cap"))
    fields = style.split(",")
    margin_l, margin_r, margin_v = int(fields[19]), int(fields[20]), int(fields[21])
    assert margin_v >= 672 and margin_l >= 65 and margin_r >= 65
    assert "&H135BE5&" in ass  # #E55B13 in BGR
    assert EM_DASH not in ass
    f = tmp_path / "c.ass"
    f.write_text(ass)
    ff("-i", str(media["good"]), "-vf", f"ass={f}", "-t", "1", "-c:a", "copy", str(tmp_path / "burn.mp4"))
    assert (tmp_path / "burn.mp4").stat().st_size > 0


def test_ass_time_format():
    assert captions.ass_time(3725.456) == "1:02:05.46"


# ---------- transcribe helpers ----------

def test_transcribe_normalize_and_srt():
    result = {"text": " Hi there.", "segments": [
        {"start": 0.0, "end": 1.2, "text": " Hi there.",
         "words": [{"word": " Hi", "start": 0.0, "end": 0.4, "probability": 0.9},
                   {"word": " there.", "start": 0.5, "end": 1.2, "probability": 0.4}]}]}
    words = transcribe.normalize(result)
    assert words == [{"word": "Hi", "start": 0.0, "end": 0.4, "prob": 0.9},
                     {"word": "there.", "start": 0.5, "end": 1.2, "prob": 0.4}]
    assert "00:00:00,000 --> 00:00:01,200" in transcribe.to_srt(result)


def test_load_audio_decodes(media):
    pytest.importorskip("numpy")
    audio = transcribe.load_audio(str(media["good"]))
    assert abs(len(audio) / transcribe.SAMPLE_RATE - 6) < 0.1


# ---------- inventory ----------

def test_inventory_handles_rotation(media, tmp_path):
    landscape = tmp_path / "land.mp4"
    ff("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(landscape))
    rot = tmp_path / "rot.mp4"
    ff("-display_rotation", "90", "-i", str(landscape), "-c", "copy", str(rot))
    row = inventory.describe(rot)
    assert (row["width"], row["height"], row["orientation"]) == (1080, 1920, "vertical")
    assert row["has_audio"] == "no" and row["kind"] == "video"


# ---------- metrics ----------

def test_metrics_rates_and_verdicts():
    df = pd.DataFrame({
        "Ad name": ["HSV_reviews_lostjobs_question_30s_9x16_v1"] * 2 + ["HSV_reviews_founder_story_15s_9x16_v1",
                                                                         "HSV_reviews_demo_demo_30s_4x5_v1"],
        "Amount spent (USD)": ["$60.00", "$60.00", "200", "30"],
        "Impressions": ["5,000", "5,000", "8000", "3000"],
        "3-second video plays": [1500, 1500, 800, 900],
        "ThruPlays": [300, 300, 100, 200],
        "Link clicks": [60, 60, 40, 30],
        "Leads": [2, 2, 0, 1],
    })
    g = metrics.diagnose(metrics.compute(df), target_cpl=50)
    r = g.set_index("ad_name")
    a = r.loc["HSV_reviews_lostjobs_question_30s_9x16_v1"]
    assert a["impressions"] == 10000 and a["leads"] == 4
    assert a["hook_rate"] == pytest.approx(0.30) and a["hold_rate"] == pytest.approx(0.20)
    assert a["cpl"] == pytest.approx(30) and a["verdict"] == "winner candidate"
    assert r.loc["HSV_reviews_founder_story_15s_9x16_v1", "verdict"] == "kill candidate"
    assert r.loc["HSV_reviews_demo_demo_30s_4x5_v1", "verdict"] == "too early"
    groups = metrics.by_convention(g)
    assert set(groups) == {"angle", "hooktype", "length", "ratio"}


def test_metrics_requires_core_columns():
    with pytest.raises(SystemExit):
        metrics.compute(pd.DataFrame({"Ad name": ["x"], "Leads": [1]}))


# ---------- doctor / playbook / config ----------

def test_tbd_paths():
    cfg = {"a": "TBD", "b": {"c": "x", "d": ["TBD"]}, "e": [{"f": "tbd"}]}
    assert doctor.tbd_paths(cfg) == ["a", "b.d", "e[0].f"]


def test_playbook_schema_and_staleness():
    facts = common.load_yaml(ROOT / "playbook" / "facts.yaml")["facts"]
    ids = [f["id"] for f in facts]
    assert len(ids) == len(set(ids)), "duplicate fact ids"
    for f in facts:
        for key in ("id", "topic", "claim", "sources", "verified_on", "shelf_life_days", "confidence", "applies_as"):
            assert key in f, (f.get("id"), key)
        assert isinstance(f["verified_on"], dt.date), f["id"]
        assert f["confidence"] in {"high", "medium", "low"}, f["id"]
        assert f["applies_as"] in {"rule", "default", "heuristic", "context"}, f["id"]
        assert all(s["url"].startswith("https://") for s in f["sources"]), f["id"]
    far_future = dt.date(2100, 1, 1)
    assert len(doctor.stale_facts(facts, far_future)) == len(facts)
    newest = max(f["verified_on"] for f in facts)
    assert doctor.stale_facts(facts, newest) == []


def test_config_parses_and_has_expected_keys():
    cfg = common.load_config()
    for key in ("business", "offer", "icp", "proof_assets", "captions", "audio", "data", "batch_defaults"):
        assert key in cfg
    assert re.fullmatch(r"#[0-9A-Fa-f]{6}", cfg["business"]["brand_colors"]["accent"])


def test_new_batch_scaffold(tmp_path, monkeypatch):
    monkeypatch.setattr(new_batch, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["new_batch.py", "--market", "HSV", "--offer", "reviews"])
    assert new_batch.main() == 0
    batch = next((tmp_path / "batches").iterdir())
    assert (batch / "BATCH.md").exists() and (batch / "brief" / "swipe").is_dir()
    monkeypatch.setattr(sys, "argv", ["new_batch.py", "--market", "HSV", "--offer", "bad_slug"])
    with pytest.raises(SystemExit):
        new_batch.main()


# ---------- house style ----------

def test_no_em_dashes_anywhere():
    offenders = []
    for p in ROOT.rglob("*"):
        if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts and p.suffix in {
                ".md", ".py", ".yaml", ".yml", ".sh", ".txt", ""}:
            try:
                if EM_DASH in p.read_text():
                    offenders.append(str(p.relative_to(ROOT)))
            except UnicodeDecodeError:
                pass
    assert not offenders, offenders


# ---------- render / selects / statics ----------

import render  # noqa: E402
import selects  # noqa: E402
import statics  # noqa: E402


@pytest.fixture(scope="session")
def footage(tmp_path_factory):
    """A fake batch folder: landscape A-roll, portrait A-roll with a silence gap, a still, green B-roll, music, SFX."""
    b = tmp_path_factory.mktemp("batch")
    (b / "BATCH.md").write_text("# test batch\n")
    for d in ("raw", "audio", "work/edl", "work/transcripts"):
        (b / d).mkdir(parents=True)
    ff("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=8",
       "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=44100:duration=8",
       "-af", "volume=0.3,apulsator=hz=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
       str(b / "raw" / "landscape.mp4"))
    # portrait: tone 0-1s, silence 1-2s, tone 2-4s (a gap to tighten)
    ff("-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=4",
       "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
       "-af", "volume=0.3,volume=enable='between(t,1,2)':volume=0", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-shortest", str(b / "raw" / "portrait.mp4"))
    ff("-f", "lavfi", "-i", "color=c=green:s=1280x720:rate=24:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-an", str(b / "raw" / "broll.mp4"))
    ff("-f", "lavfi", "-i", "color=c=orange:s=800x600:d=1", "-frames:v", "1", str(b / "raw" / "still.png"))
    import pillow_heif
    from PIL import Image
    pillow_heif.register_heif_opener()
    Image.new("RGB", (600, 400), (200, 40, 40)).save(b / "raw" / "photo.heic", quality=80)
    # rotated phone clip: stored landscape with a 90 degree display rotation (what iPhones write)
    ff("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(b / "raw" / "flat.mp4"))
    ff("-display_rotation", "90", "-i", str(b / "raw" / "flat.mp4"), "-c", "copy", str(b / "raw" / "rotated.mp4"))
    # HDR-tagged clip (HLG transfer) to exercise the tonemap chain
    ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", "-an", str(b / "raw" / "hdr.mp4"))
    ff("-f", "lavfi", "-i", "sine=frequency=110:sample_rate=48000:duration=3", "-af", "volume=0.5",
       "-c:a", "libmp3lame", str(b / "audio" / "music.mp3"))
    ff("-f", "lavfi", "-i", "sine=frequency=2000:sample_rate=48000:duration=0.2", str(b / "audio" / "whoosh.wav"))
    (b / "work" / "transcripts" / "landscape.words.json").write_text(json.dumps(WORDS))
    (b / "work" / "edl" / "TEST_offer_angle_question_10s_9x16_v1.yaml").write_text("""
name: TEST_offer_angle_question_10s_9x16_v1
ratio: "9:16"
hook_text: "Huntsville roofers: only 9 reviews?"
hook_text_seconds: 2
clips:
  - {src: raw/landscape.mp4, in: 1.0, out: 3.0, focus: auto}
  - {src: raw/portrait.mp4, in: 0.0, out: 4.0, zoom: 1.1, tighten: 0.5}
  - {src: raw/landscape.mp4, in: 5.0, out: 6.0, push: 1.08}
  - {src: raw/still.png, duration: 1.0, push: 1.1}
broll:
  - {src: raw/broll.mp4, at: 0.25, duration: 0.5, src_in: 1.0, pip: {w: 0.5, x: 0.5, y: 0.40}}
  - {src: raw/broll.mp4, at: 1.0, duration: 1.0, label: "A text goes out", speaker_inset: {w: 0.40, x: 0.76, y: 0.70}}
  - {src: raw/photo.heic, at: 5.6, duration: 0.8, pip: {w: 0.6, x: 0.5, y: 0.4}}
callouts:
  - {text: "$4,800 job (example)", at: 3.0, duration: 1.0, accent: true}
plates:
  - {type: compare, title: "Same work.", left: {label: You, value: 9}, right: {label: Them, value: 140}, note: "(example)", at: 4.2, duration: 1.2}
  - {type: stat, value: 140, suffix: " reviews", label: "(example)", at: 6.5, duration: 0.9}
look: {contrast: 1.03, saturation: 1.05, sharpen: true}
lower_third: {text: "Bruce, Auburn AL", at: 0.5, duration: 1.5}
music: {src: audio/music.mp3, gain_db: -16, duck: true}
sfx:
  - {src: audio/whoosh.wav, at: 1.0, gain_db: -8}
end_card: {text: "Tap Learn More", subtext: "Huntsville contractors", seconds: 1.5}
""")
    return b


def mean_rgb(video: Path, t: float, crop: str = "crop=iw*0.6:ih*0.3:iw*0.2:ih*0.4") -> tuple[float, float, float]:
    raw = subprocess.run([FF, "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                          "-vf", f"{crop},scale=8:8", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    px = [raw[i:i + 3] for i in range(0, len(raw), 3)]
    return tuple(sum(p[c] for p in px) / len(px) for c in range(3))


def test_crop_box_and_resolution():
    assert render.crop_box(1920, 1080, "9:16", (0.5, 0.5), 1.0) == (606, 1080, 656, 0)
    w, h, x, y = render.crop_box(1920, 1080, "9:16", (0.9, 0.5), 1.0)
    assert x + w <= 1920 and x >= 1300  # focus near the right edge is clamped inside the frame
    w, h, *_ = render.crop_box(1080, 1920, "4:5", (0.5, 0.5), 1.1)
    assert abs(w / h - 0.8) < 0.01 and w < 1080
    assert render.pick_resolution("9:16", 1440) == (1440, 2560)
    assert render.pick_resolution("9:16", 1080) == (1080, 1920)


def test_tighten_ranges_keeps_edges_and_shortens_gaps():
    gaps = [(0.0, 0.3), (2.0, 3.0), (4.8, 5.0)]
    assert render.tighten_ranges(0.0, 5.0, gaps, keep=0.12) == [(0.0, 2.12), (2.88, 5.0)]
    assert render.tighten_ranges(0.0, 5.0, [], keep=0.12) == [(0.0, 5.0)]


def test_silence_detection_finds_the_gap(footage):
    gaps = render.silences(footage / "raw" / "portrait.mp4", 0.0, 4.0, 0.5)
    assert len(gaps) == 1 and abs(gaps[0][0] - 1.0) < 0.15 and abs(gaps[0][1] - 2.0) < 0.15


def test_render_proxy_and_final(footage):
    edl = footage / "work" / "edl" / "TEST_offer_angle_question_10s_9x16_v1.yaml"
    proxy = render.render(edl, None, None, proxy=True, keep_tmp=False, out_dir=None)
    assert proxy.exists() and proxy.parent.name == "proxies"
    info = common.probe(proxy)
    assert int(common.video_stream(info)["width"]) == 540

    master = render.render(edl, None, None, proxy=False, keep_tmp=False, out_dir=None)
    assert master.name.endswith("_master.mp4")
    final = render.render(edl, None, str(footage / "work" / "transcripts" / "landscape.words.json"),
                          proxy=False, keep_tmp=False, out_dir=None)
    assert final.parent.name == "exports"
    info = common.probe(final)
    v, a = common.video_stream(info), common.audio_stream(info)
    assert (int(v["width"]), int(v["height"])) == (1080, 1920)
    assert v["r_frame_rate"] == "30/1" and a["codec_name"] == "aac" and a.get("channels") == 2
    dur = float(info["format"]["duration"])
    # 2.0 + (4.0 tightened to ~3.24) + 1.0 + 1.0 + end card 1.5 = about 8.7 s
    assert 8.2 < dur < 9.2, dur
    r, g, b = mean_rgb(final, 1.5, "crop=iw*0.4:ih*0.3:iw*0.05:ih*0.4")   # left half of the green B-roll window (0x008000)
    assert g > 90 and g > 2 * r and g > 2 * b, (r, g, b)
    r, g, b = mean_rgb(final, 1.5, "crop=iw*0.3:ih*0.12:iw*0.62:ih*0.60")   # the speaker inset is A-roll, not green
    assert not (g > 90 and g > 2 * r and g > 2 * b), (r, g, b)
    r, g, b = mean_rgb(final, 2.6)       # back on A-roll (testsrc2 is not green)
    assert not (g > 90 and g > 2 * r and g > 2 * b), (r, g, b)
    sidecar = json.loads((final.parent / (final.stem + ".render.json")).read_text())
    assert [c["src"] for c in sidecar["clips"]][-1] == "end_card"
    assert sidecar["broll"][1]["at"] == 1.0 and sidecar["graphics"][0]["type"] in ("hook_text", "hook")
    assert sidecar["broll"][1].get("speaker_inset") is True and sidecar["broll"][0]["pip"] is True
    assert len(sidecar["clips"]) == 6  # the tightened clip became two segments
    assert [g["type"] for g in sidecar["graphics"]] == ["hook", "lower_third", "label", "compare", "pip", "stat"]
    assert all(g["engine"] == "html" for g in sidecar["graphics"])
    assert sidecar["captions"]["engine"] == "html" and sidecar["captions"]["style"] == "pill"
    assert sidecar["broll"][2]["pip"] is True
    r, g, b = mean_rgb(final, 5.9, "crop=iw*0.3:ih*0.1:iw*0.35:ih*0.37")   # inside the pip plate of the red HEIC photo
    assert r > 120 and r > 2 * g and r > 2 * b, (r, g, b)
    s = statuses(qa.qa_one(final, footage / "qa", -14, -1.0))
    assert s["flash frames (10 fps scan)"] == "PASS" and s["captions inside safe zone"] == "PASS"
    s = statuses(qa.qa_one(final, footage / "qa", -14, -1.0))
    assert not [k for k, v in s.items() if v == "FAIL"], s
    feed = render.render(edl, "4:5", None, proxy=True, keep_tmp=False, out_dir=None)
    assert "_4x5_" in feed.name


def test_captions_styles_are_well_formed():
    for style in captions.STYLES:
        ass = captions.build_ass(WORDS, 1080, 1920, font="DejaVu Sans", accent="#E55B13", style=style)
        n = ass.count("Dialogue:")
        assert n >= 3, style
        assert EM_DASH not in ass
        if style in ("highlight", "reveal", "hormozi"):
            assert n == len(WORDS)  # one event per spoken word
        if style == "karaoke":
            assert "\\kf" in ass
        if style == "hormozi":
            assert "HUNTSVILLE" in ass
    with pytest.raises(SystemExit):
        captions.build_ass(WORDS, 1080, 1920, font="x", accent="#E55B13", style="nope")


def test_selects_matches_lines(footage, tmp_path):
    script = tmp_path / "script.md"
    script.write_text("| [0-3s] | Huntsville roofers, your competitor has 140 reviews. | text | A-roll |\n"
                      "Something that was never said on camera at all\n")
    out, edl = tmp_path / "selects.md", tmp_path / "draft.yaml"
    sys_argv = ["selects.py", "--script", str(script), "--transcripts", str(footage / "work" / "transcripts"),
                "--out", str(out), "--edl", str(edl), "--name", "T_a_b_c_15s_9x16_v1", "--raw", str(footage / "raw")]
    import unittest.mock as um
    with um.patch.object(sys, "argv", sys_argv):
        assert selects.main() == 0
    md = out.read_text()
    assert "| 1 | landscape | 0.00 |" in md and "NOT FOUND" in md
    y = common.load_yaml(edl)
    assert len(y["clips"]) == 1 and y["clips"][0]["src"].endswith("landscape.mp4")


def test_statics_builds_png(footage, tmp_path):
    out = statics.build(footage / "raw" / "still.png", "4:5", "Huntsville roofers: only 9 reviews?",
                        "Your competitor has 140.", "Tap Learn More", tmp_path / "s.png")
    from PIL import Image
    assert Image.open(out).size == (1440, 1800)


def test_find_font_prefers_brand_folder(tmp_path):
    (tmp_path / "Montserrat-ExtraBold.ttf").write_bytes(b"x")
    path, exact = common.find_font("Montserrat ExtraBold", tmp_path)
    assert exact and path.endswith("Montserrat-ExtraBold.ttf")
    path, exact = common.find_font("Montserrat ExtraBold", tmp_path / "nope")
    assert not exact


def test_requirements_parse():
    """A bad environment marker makes pip reject the whole file, which leaves the venv empty."""
    from packaging.requirements import Requirement
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            Requirement(line)


import variants  # noqa: E402
import review  # noqa: E402


def test_render_handles_rotated_and_hdr_sources(footage):
    edl = footage / "work" / "edl" / "T_offer_angle_hook_5s_9x16_v1.yaml"
    edl.write_text("""
name: T_offer_angle_hook_5s_9x16_v1
clips:
  - {src: raw/rotated.mp4, in: 0.0, out: 1.0}
  - {src: raw/hdr.mp4, in: 0.0, out: 0.5, zoom: 1.1}
""")
    out = render.render(edl, None, None, proxy=True, keep_tmp=False, out_dir=None)
    v = common.video_stream(common.probe(out))
    assert (int(v["width"]), int(v["height"])) == (540, 960)
    # the rotated source is displayed portrait, so the crop keeps (almost) its full width
    tl = render.timeline_of(edl)
    assert [c["src"] for c in tl] == ["raw/rotated.mp4", "raw/hdr.mp4"]
    assert render.crop_box(1080, 1920, "9:16", (0.5, 0.5), 1.0)[0] == 1080


def test_variants_matrix(footage):
    base = footage / "work" / "edl" / "HSV_reviews_lostjobs_question_10s_9x16_v1.yaml"
    base.write_text("""
name: HSV_reviews_lostjobs_question_10s_9x16_v1
hook_text: "Huntsville roofers?"
clips:
  - {src: raw/landscape.mp4, in: 1.0, out: 2.0, slot: hook}
  - {src: raw/portrait.mp4, in: 0.0, out: 1.0, slot: offer}
lower_third: {text: "Bruce", at: 0.2, duration: 1.0}
end_card: {text: "Tap Learn More", subtext: "Huntsville", seconds: 1.0}
""")
    spec = footage / "work" / "edl" / "HSV_reviews_lostjobs_question_10s_9x16_v1.variants.yaml"
    spec.write_text("""
base: HSV_reviews_lostjobs_question_10s_9x16_v1.yaml
ratios: ["9:16"]
dimensions:
  market:
    HSV: {hook_text: "Huntsville roofers?", end_card: {subtext: "Huntsville"}}
    AUB: {hook_text: "Auburn roofers?", slots: {hook: {src: raw/landscape.mp4, in: 3.0, out: 4.0}}, end_card: {subtext: "Auburn"}}
  price:
    p497: {slots: {offer: {in: 1.0, out: 2.0}}, callouts: [{text: "$497 (example)", at: 0.2, duration: 0.5}]}
    free: {remove: [lower_third]}
skip:
  - {market: AUB, price: free}
""")
    rows = variants.materialize(spec)
    names = [r["name"] for r in rows]
    assert names == ["HSV_reviews_lostjobs-p497_question_10s_9x16_v1", "HSV_reviews_lostjobs-free_question_10s_9x16_v1",
                     "AUB_reviews_lostjobs-p497_question_10s_9x16_v1"]
    aub = common.load_yaml(rows[2]["path"])
    assert aub["hook_text"] == "Auburn roofers?" and aub["clips"][0]["in"] == 3.0 and aub["end_card"]["subtext"] == "Auburn"
    assert aub["clips"][1]["in"] == 1.0 and aub["callouts"][0]["text"].startswith("$497")
    free = common.load_yaml(rows[1]["path"])
    assert "lower_third" not in free and "callouts" not in free
    assert (spec.parent / "variants" / "MATRIX.md").read_text().count("| HSV_") == 2
    out = render.render(rows[2]["path"], "9:16", None, proxy=True, keep_tmp=False, out_dir=None)
    assert out.name.startswith("AUB_reviews_lostjobs-p497")
    with pytest.raises(SystemExit):
        variants.deep_merge({"clips": [{"slot": "hook"}]}, {"slots": {"nope": {}}})


def test_qa_sidecar_checks_and_review_page(footage):
    final = next((footage / "exports").glob("TEST_offer_angle_question_10s_9x16_v1.mp4"))
    script = footage / "script.txt"
    script.write_text("Huntsville roofers, your competitor has 140 reviews.\nA line that is not in the ad.\n")
    r = qa.qa_one(final, footage / "qa", -14, -1.0, script)
    s = statuses(r)
    assert s["headline on frame 1"] == "PASS" and s["end card with CTA"] == "PASS"
    assert s["captions inside safe zone"] == "PASS" and s["caption pages readable"] == "PASS"
    assert s["captions match script"] == "WARN"          # one of two lines is not in the captions
    assert s["face in hook (first 1.5s)"] == "WARN"      # synthetic footage has no face
    page = review.build(footage)
    html_text = page.read_text()
    assert "TEST_offer_angle_question_10s_9x16_v1.mp4" in html_text and "Timeline" in html_text and "QA:" in html_text


def test_inventory_sheets(footage, tmp_path):
    import unittest.mock as um
    with um.patch.object(sys, "argv", ["inventory.py", "--raw", str(footage / "raw"), "--out", str(tmp_path / "inv.csv"),
                                       "--sheets", str(tmp_path / "sheets")]):
        assert inventory.main() == 0
    assert (tmp_path / "sheets" / "landscape.png").stat().st_size > 0
    rows = (tmp_path / "inv.csv").read_text()
    assert "photo.heic" in rows and "rotated.mp4" in rows


import lint_copy  # noqa: E402


def test_lint_copy_catches_house_rule_breaks(tmp_path):
    cfg = {"offer": {"urgency_or_scarcity": "none", "price": "$497"}, "proof_assets": {"client_results": []}}
    f = lint_copy.lint_text("Struggling to pay bills? Our SEO funnel is guaranteed. Only 2 spots left. 140 reviews in 30 days.",
                            "t", cfg)
    whys = " | ".join(x["why"] for x in f)
    levels = {x["level"] for x in f}
    assert "personal attribute" in whys and "jargon 'seo'" in whys and "claim 'guaranteed'" in whys
    assert "urgency 'only 2 spots'" in whys and "not labeled (example)" in whys and "FAIL" in levels
    assert not lint_copy.lint_text("Huntsville roofers: 9 reviews vs 140? (example)", "t", cfg)
    assert not lint_copy.lint_text("Set up for $497. Tap learn more.", "t", cfg)   # price from config is allowed
    assert any("em dash" in x["why"] for x in lint_copy.lint_text("a " + EM_DASH + " b", "t", cfg))
    batch = tmp_path / "b"
    (batch / "exports").mkdir(parents=True)
    (batch / "exports" / "x_copy.md").write_text("# Primary text\n\nWe help contractors. We do SEO. We are the best.\n\n"
                                                 "# Headlines\n\n- More 5-star reviews on autopilot for your business (49)\n")
    (batch / "work" / "edl").mkdir(parents=True)
    (batch / "work" / "edl" / "a.yaml").write_text("name: x\nhook_text: 'Guaranteed #1 on Google'\nclips: []\n")
    findings = lint_copy.lint_batch(batch, cfg)
    whys = " | ".join(x["why"] for x in findings)
    assert "more 'we/I' than 'you'" in whys and "headline is 50 characters" in whys and "claim 'guaranteed'" in whys


def test_metrics_reads_mcp_json_and_flags_fatigue(tmp_path):
    rows = []
    for day in range(14):
        ctr = 0.02 if day < 7 else 0.012   # CTR drops 40% in the last week
        rows.append({"name": "HSV_reviews_lostjobs_question_30s_9x16_v1", "date_start": f"2026-10-{day + 1:02d}",
                     "spend": "20", "impressions": 2000, "inline_link_clicks": int(2000 * ctr), "frequency": 3.1,
                     "actions": [{"action_type": "lead", "value": 1}, {"action_type": "video_view", "value": 500}],
                     "video_thruplay_watched_actions": [{"action_type": "video_view", "value": 100}]})
    j = tmp_path / "pull.json"
    j.write_text(json.dumps({"ad_entities": rows}))
    df = metrics.load_rows(j)
    assert "actions_lead" in df.columns and "date_start" in df.columns
    g = metrics.diagnose(metrics.compute(df), target_cpl=50)
    assert g.iloc[0]["leads"] == 14 and g.iloc[0]["impressions"] == 28000
    fat = g.attrs["fatigue"]
    assert fat is not None and fat.iloc[0]["fatigue"] == "fatigue: refresh creative"


def test_render_all_ratios_reuses_words(footage, monkeypatch):
    edl = footage / "work" / "edl" / "TEST_offer_angle_question_10s_9x16_v1.yaml"
    words = footage / "work" / "transcripts" / "landscape.words.json"
    monkeypatch.setattr(sys, "argv", ["render.py", str(edl), "--all-ratios", "--captions", str(words)])
    assert render.main() == 0
    feed = footage / "exports" / "TEST_offer_angle_question_10s_4x5_v1.mp4"
    assert feed.exists()
    v = common.video_stream(common.probe(feed))
    assert (int(v["width"]), int(v["height"])) == (1080, 1350)
    sc = json.loads((footage / "exports" / "TEST_offer_angle_question_10s_4x5_v1.render.json").read_text())
    assert sc["ratio"] == "4:5" and sc["captions"]["style"] == "pill"


import plates  # noqa: E402


def test_plates_render_alpha_and_storyboard(footage):
    cfg = common.load_config()
    r = plates.Renderer(540, 960)
    try:
        for spec in plates.demo_specs():
            spec = {**spec, "duration": 0.5}
            mov = footage / "work" / f"plate_{spec['type']}.mov"
            r.render_mov(plates.build_html(spec, 540, 960, cfg), 0.5, 10, mov)
            v = common.video_stream(common.probe(mov))
            assert v["codec_name"] == "prores" and v["pix_fmt"].startswith("yuva"), spec["type"]
    finally:
        r.close()
    edl = footage / "work" / "edl" / "TEST_offer_angle_question_10s_9x16_v1.yaml"
    sheet = render.storyboard(edl, None)
    from PIL import Image
    assert sheet.exists() and Image.open(sheet).size[0] > 1000


def test_editor_defaults_alternate_tighten_settle():
    cfg = {"edit": {"auto_tighten": 0.4, "auto_alternate_zoom": True, "alternate_zoom": 1.08, "settle_cuts": 1.04}}
    edl = {"clips": [{"src": "a", "still": False}, {"src": "a", "still": False}, {"src": "img", "still": True},
                     {"src": "a", "still": False, "zoom": 1.2, "tighten": 0, "settle": 0}, {"src": "a", "still": False}]}
    render.apply_editor_defaults(edl, cfg)
    c = edl["clips"]
    assert [x.get("zoom") for x in c] == [1.0, 1.08, None, 1.2, 1.0]
    assert c[0]["tighten"] == 0.4 and c[3]["tighten"] == 0 and "tighten" not in c[2]
    assert "_settle" not in c[0] and c[1]["_settle"] == 1.04 and c[3]["_settle"] is None and c[4]["_settle"] == 1.04
    vf = render.video_filters(1920, 1080, False, "9:16", 1080, 1920, 30, (0.5, 0.5), 1.0, None, 2.0, None, 1.04)
    assert "eval=frame" in vf and "pow(" in vf


def test_qa_flags_overlapping_graphics():
    sc = {"graphics": [{"type": "label", "at": 2.0, "duration": 2.0, "region": "center"},
                       {"type": "stat", "at": 3.0, "duration": 2.0, "region": "center"},
                       {"type": "hook", "at": 0.0, "duration": 3.0, "region": "top"}], "clips": [{"src": "end_card"}]}
    s = {c["check"]: c["status"] for c in qa.sidecar_checks(sc, 20.0)}
    assert s["one graphic per region at a time"] == "FAIL"
    sc["graphics"][1]["at"] = 4.5
    s = {c["check"]: c["status"] for c in qa.sidecar_checks(sc, 20.0)}
    assert s["one graphic per region at a time"] == "PASS"


def test_caption_box_style_builds(footage):
    cfg = common.load_config()
    spec = {"type": "captions", "words": WORDS, "style": "box", "keywords": ["reviews."], "max_words": 3, "duration": 5}
    h = plates.build_html(spec, 540, 960, cfg)
    assert "style-box" in h and h.count('class="w on key"') >= 3


def test_grid_plate_from_clip_and_new_types(footage):
    cfg = common.load_config()
    edl = footage / "work" / "edl" / "G_offer_angle_hook_5s_9x16_v1.yaml"
    edl.write_text("""
name: G_offer_angle_hook_5s_9x16_v1
hook_text: "EDITORS SHOULD BE WORRIED"
hook_variant: light
hook_uppercase: true
clips:
  - {src: raw/landscape.mp4, in: 0.0, out: 2.0}
plates:
  - {type: grid, src: raw/landscape.mp4, count: 6, text: "cuts found", at: 0.3, duration: 1.2}
  - {type: step, number: "01", text: "Film it", at: 0.2, duration: 1.0}
""")
    loaded = render.load_edl(edl, None)
    specs = render.plate_specs(loaded, cfg)
    grid = next(sp for sp in specs if sp["type"] == "grid")
    assert len(grid["images"]) == 6 and all(Path(p).exists() for p in grid["images"])
    hook = next(sp for sp in specs if sp["type"] == "hook")
    assert hook["uppercase"] is True and hook["variant"] == "light"
    r = plates.Renderer(540, 960)
    try:
        for sp in specs:
            r.render_still(plates.build_html(sp, 540, 960, cfg), 0.8, footage / "work" / f"still_{sp['type']}.png")
    finally:
        r.close()
    from PIL import Image
    assert Image.open(footage / "work" / "still_grid.png").size == (540, 960)


def test_split_layout_stage_progress_punches_and_source_captions(footage):
    """Reference 3 grammar: speaker in a bottom band over the brand backdrop, graphics on the stage above,
    a progress bar for the whole ad, zoom punches on key words, and captions mapped from the SOURCE transcript."""
    edl = footage / "work" / "edl" / "S_offer_angle_hook_5s_9x16_v1.yaml"
    edl.write_text("""
name: S_offer_angle_hook_5s_9x16_v1
progress_bar: true
punches: [0.6, {at: 1.4}]
clips:
  - {src: raw/landscape.mp4, in: 1.0, out: 3.0, layout: split, tighten: 0}
  - {src: raw/landscape.mp4, in: 5.0, out: 6.0, tighten: 0}
plates:
  - {type: label, text: "On the *stage*", position: stage, at: 0.3, duration: 1.2}
  - {type: takeover, text: "*Nine*\\nreviews.", sub: "example", at: 2.2, duration: 0.6}
""")
    loaded = render.load_edl(edl, None)
    specs = render.plate_specs(loaded, common.load_config())
    stage = next(sp for sp in specs if sp["type"] == "label")
    assert 0.25 < float(stage["position"]) < 0.40            # centre of the stage above the speaker band
    assert specs[0]["type"] == "progress" and specs[0]["at"] == 0.0
    final = render.render(edl, None, "source", proxy=False, keep_tmp=False, out_dir=None)
    info = common.probe(final)
    assert 2.8 < float(info["format"]["duration"]) < 3.3
    # the stage (top of frame) is the dark navy backdrop while the first clip plays; the band at the bottom is A-roll
    r, g, b = mean_rgb(final, 1.8, "crop=iw*0.6:ih*0.08:iw*0.2:ih*0.04")
    assert r < 60 and g < 60 and b < 90 and b >= r, (r, g, b)
    r2, g2, b2 = mean_rgb(final, 1.8, "crop=iw*0.6:ih*0.2:iw*0.2:ih*0.75")
    assert (r2 + g2 + b2) > (r + g + b) + 60, (r2, g2, b2)
    # second clip is full frame again
    r3, g3, b3 = mean_rgb(final, 2.9, "crop=iw*0.6:ih*0.08:iw*0.2:ih*0.04")   # after the takeover has left
    assert (r3 + g3 + b3) > (r + g + b) + 60, (r3, g3, b3)
    sidecar = json.loads((final.parent / (final.stem + ".render.json")).read_text())
    assert sidecar["clips"][0]["layout"] == "split" and sidecar["clips"][1]["layout"] == "full"
    assert sidecar["punches"] == [0.6, 1.4]
    assert [g["type"] for g in sidecar["graphics"]] == ["progress", "label", "takeover"]
    words = json.loads(Path(sidecar["captions"]["words_json"]).read_text())
    # source words 1.02-2.60 s ("competitor has 140 reviews.") land at 0.02-1.60 s on the master; "your" (0.85-1.00) is cut
    assert [w["word"] for w in words] == ["competitor", "has", "140", "reviews."]
    assert abs(words[0]["start"] - 0.02) < 0.02 and abs(words[-1]["end"] - 1.60) < 0.02
    s = statuses(qa.qa_one(final, footage / "qa", -14, -1.0))
    assert s["no clicks at cuts"] in ("PASS", "WARN") and s["no repeated words across cuts"] == "PASS"
    assert "no breathy lulls over 0.5s" in s
    assert not [k for k, v in s.items() if v == "FAIL"], s


def test_words_from_sources_drops_removed_pauses():
    timeline = {"clips": [{"src": "raw/landscape.mp4", "src_in": 0.0, "src_out": 1.0, "at": 0.0, "duration": 1.0},
                          {"src": "raw/landscape.mp4", "src_in": 3.0, "src_out": 4.6, "at": 1.0, "duration": 1.6},
                          {"src": "end_card", "at": 2.6, "duration": 1.0}]}
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tr = Path(d) / "transcripts"
        tr.mkdir()
        (tr / "landscape.words.json").write_text(json.dumps(WORDS))
        out = render.words_from_sources({}, timeline, tr, Path(d) / "m.words.json")
        words = json.loads(out.read_text())
    assert [w["word"] for w in words] == ["Huntsville", "roofers,", "your", "auburn", "seo", "fixes", "that."]
    assert abs(words[3]["start"] - 1.2) < 1e-6 and words[3]["start"] > words[2]["end"]   # the 1.0-3.0 s pause is gone
    assert render.words_from_sources({}, {"clips": [{"src": "raw/none.mp4", "src_in": 0, "src_out": 1, "at": 0, "duration": 1}]},
                                     Path("/nonexistent"), Path("/tmp/x.json")) is None


def test_seam_click_and_repeated_word_checks(tmp_path):
    # a hard step from +0.9 to -0.9 at the 1.0 s cut is a butt-splice click; a continuous signal is not
    ff("-f", "lavfi", "-i", "aevalsrc=0.9:s=48000:d=1", "-f", "lavfi", "-i", "aevalsrc=-0.9:s=48000:d=1",
       "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", "-c:a", "pcm_s16le", str(tmp_path / "click.wav"))
    ff("-f", "lavfi", "-i", "aevalsrc=0.9:s=48000:d=2", "-c:a", "pcm_s16le", str(tmp_path / "smooth.wav"))
    words = [{"word": "Huntsville", "start": 0.2, "end": 0.6}, {"word": "roofers", "start": 0.62, "end": 0.95},
             {"word": "Roofers,", "start": 1.02, "end": 1.3}, {"word": "listen", "start": 1.32, "end": 1.6}]
    wj = tmp_path / "w.json"
    wj.write_text(json.dumps(words))
    sc = {"clips": [{"src": "a", "at": 0.0}, {"src": "a", "at": 1.0}], "captions": {"words_json": str(wj)}}
    s = {c["check"]: c for c in qa.seam_checks(tmp_path / "click.wav", sc)}
    assert s["no clicks at cuts"]["status"] == "WARN" and "1.00s" in s["no clicks at cuts"]["detail"]
    assert s["no repeated words across cuts"]["status"] == "FAIL" and "roofers" in s["no repeated words across cuts"]["detail"]
    s = {c["check"]: c["status"] for c in qa.seam_checks(tmp_path / "smooth.wav", sc)}
    assert s["no clicks at cuts"] == "PASS"
    words[2]["word"] = "listen"
    words[3]["word"] = "up"
    wj.write_text(json.dumps(words))
    s = {c["check"]: c["status"] for c in qa.seam_checks(tmp_path / "smooth.wav", sc)}
    assert s["no repeated words across cuts"] == "PASS"


def test_lull_scan_finds_quiet_stretch(tmp_path):
    # speech-level tone (about -15 dB) with a breathy -41 dB stretch from 1.5 to 2.5 s: too loud for silencedetect, dead air to a viewer
    ff("-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=4",
       "-af", "volume='if(between(t,1.5,2.5),0.2,4)':eval=frame", "-c:a", "pcm_s16le", str(tmp_path / "lull.wav"))
    res = {c["check"]: c for c in qa.lull_scan(tmp_path / "lull.wav")}
    assert res["no breathy lulls over 0.5s"]["status"] == "WARN" and "(1.0s)" in res["no breathy lulls over 0.5s"]["detail"]
    ff("-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=4", "-af", "volume=4", "-c:a", "pcm_s16le", str(tmp_path / "even.wav"))
    res = {c["check"]: c["status"] for c in qa.lull_scan(tmp_path / "even.wav")}
    assert res["no breathy lulls over 0.5s"] == "PASS"


def test_speech_spans_split_takes(footage):
    spans = transcribe.speech_spans(footage / "raw" / "portrait.mp4", min_silence=0.6)
    assert len(spans) == 2, spans
    assert spans[0][0] == 0.0 and abs(spans[0][1] - 1.0) < 0.15 and abs(spans[1][0] - 2.0) < 0.15 and spans[1][1] > 3.8


def test_new_plate_types_render_stills(footage):
    cfg = common.load_config()
    specs = [{"type": "progress", "duration": 4.0}, {"type": "backdrop", "duration": 1.0},
             {"type": "takeover", "text": "*Nine*\nreviews.", "sub": "example", "bg": "dark", "duration": 1.4},
             {"type": "strike", "title": "What everyone tries", "items": ["Asking", "A sign", "Hoping"], "answer": "A text, same day", "duration": 4},
             {"type": "pip", "src": str(footage / "raw" / "still.png"), "device": "phone", "stamp": "Live", "highlight": {"x": 0.1, "y": 0.2, "w": 0.6, "h": 0.1}, "duration": 2}]
    assert all(plates.region_of(sp) == "full" for sp in specs[:3])
    r = plates.Renderer(540, 960)
    try:
        for sp in specs:
            r.render_still(plates.build_html(sp, 540, 960, cfg), 0.9, footage / "work" / f"still2_{sp['type']}.png")
    finally:
        r.close()
    from PIL import Image
    bd = Image.open(footage / "work" / "still2_backdrop.png").convert("RGBA")
    assert bd.getpixel((270, 100))[3] == 255 and bd.getpixel((270, 100))[2] > bd.getpixel((270, 100))[0]   # opaque, navy
    pr = Image.open(footage / "work" / "still2_progress.png").convert("RGBA")
    assert pr.getpixel((270, 480))[3] == 0                        # progress plate is transparent below the bar
    tk = Image.open(footage / "work" / "still2_takeover.png").convert("RGBA")
    assert tk.getpixel((270, 480))[3] == 255                      # takeover covers the frame
    h = plates.build_html(specs[4], 540, 960, cfg)
    assert "Live" in h and 'class="hl"' in h


def test_caption_sentiment_classes(footage):
    cfg = common.load_config()
    spec = {"type": "captions", "words": WORDS, "style": "pill", "keywords_neg": ["competitor"], "keywords_pos": ["fixes"], "max_words": 3, "duration": 5}
    h = plates.build_html(spec, 540, 960, cfg)
    assert "neg" in h and "pos" in h and h.index("competitor") < h.index("fixes")


def test_reference_analysis_writes_report(footage):
    import reference
    out = reference.analyze(footage / "raw" / "landscape.mp4", 3, footage / "work" / "ref_analysis")
    text = out.read_text()
    assert out.suffix == ".md" and "hard cuts" in text and (footage / "work" / "ref_analysis" / "sheet.png").exists()
    assert len(list((footage / "work" / "ref_analysis").glob("frame_*.png"))) == 3
