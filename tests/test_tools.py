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
