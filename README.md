# Ad Video Engine

Claude Code project that turns raw footage into upload-ready, QA'd Meta (Facebook + Instagram) video and static ads for AuburnSEO, and keeps its Meta ads knowledge current.

No pasting a giant prompt: `CLAUDE.md` loads automatically, and the workflow lives in skills you call by name.

## One-time setup (MacBook Pro)

```bash
git clone <this repo> && cd ad-creative-editor
tools/setup_mac.sh          # installs ffmpeg-full, Python venv, mlx-whisper, then runs the doctor
```

Everything in the pipeline is free and runs on the Mac: ffmpeg, Whisper (mlx-whisper or WhisperX), OpenCV for face-centered reframing, Pillow for statics, and Claude Code as the editor's brain. No render API, no subscription, no upload of footage anywhere.

Then:
1. Fill in every `TBD` you can in `config.yaml` (offer, market, target CPL, etc.).
2. Put fonts (commercially licensed) in `brand/fonts/`, logo in `brand/`, real proof screenshots in `brand/proof/`.
3. Put footage in `raw/`, ad-licensed music in `audio/music/` (keep each license file next to its track), SFX in `audio/sfx/`.
4. Optional: install the Claude in Chrome extension (for Meta Ad Library research) and connect the Windsor.ai MCP (for pulling your ad results). Without them, the engine asks for screenshots and CSV exports instead.

## Use

Open Claude Code in this folder (`claude`, or `claude --chrome` for Ad Library research), then:

| Command | What it does |
|---|---|
| `/ad-batch` | Start or resume a batch: research -> ICP and angles -> offer -> hooks and scripts -> rough cut -> full edit -> copy -> QA -> launch plan, with an approval gate after each stage |
| `/ad-results` | Analyze live results, diagnose each ad, update `LEARNINGS.md`, plan the next batch |
| `/refresh-playbook` | Re-verify everything the engine "knows" about Meta ads against live sources |

Batches live in `batches/<date>_<market>_<offer>/`, each with a `BATCH.md` tracker, so any session can pick up where the last one stopped.

## How it stays current

- `playbook/facts.yaml` holds every spec, policy, algorithm, benchmark, and trend fact with its source, the date it was verified, a shelf life, and a confidence level.
- `tools/doctor.py` runs at the start of every session and flags expired facts; the engine must run `/refresh-playbook` before giving strategy on expired facts.
- Every batch's Stage 1 also researches the last 3 months live and adds what is new.
- `playbook/CHANGELOG.md` records what changed and when.
- Optional: a monthly scheduled refresh that runs `/refresh-playbook` unattended.

## Tools

| Script | Purpose |
|---|---|
| `tools/doctor.py` | Tools installed, config gaps, playbook freshness |
| `tools/new_batch.py` | Scaffold a batch folder |
| `tools/inventory.py` | ffprobe every file in `raw/` (rotation, VFR, HDR, resolution flags) and per-clip contact sheets |
| `tools/transcribe.py` | Word-level transcripts (mlx-whisper, WhisperX, or faster-whisper, whichever is installed) |
| `tools/selects.py` | Best take per script line from the transcripts, plus a draft EDL |
| `tools/render.py` | EDL (yaml) to finished ad: reframe to 9:16 or 4:5 around the face, punch-ins, pause tightening, B-roll, hook text, lower third, ducked music, SFX, end card, two-pass loudness, captions. `--proxy` for rough cuts |
| `tools/captions.py` | Caption file (.ass) from a transcript: chunk, highlight, karaoke, reveal, or hormozi style, inside the safe zone |
| `tools/statics.py` | Static image ads (4:5, 9:16) from a photo or a frame, headline + CTA inside the safe zone |
| `tools/variants.py` | Single-variable versions of a hero ad (market, offer, hook, CTA) from one variants file; writes every EDL and a MATRIX.md |
| `tools/review.py` | One-page local review site per batch (players, timelines, captions, QA, notes box) |
| `tools/qa.py` | Spec, loudness, black-frame, silent-open, opening-similarity, caption geometry, headline, face, duration and script-match checks plus evidence images |
| `tools/metrics.py` | Hook rate, hold rate, CTR, CPL, verdicts, and grouping by angle / hook / length / ratio |

Run the tests with `.venv/bin/python -m pytest -q`.

## What is not in git

Footage, audio, fonts, proof screenshots, rendered ads, and ad data are ignored by `.gitignore`. Back them up separately (iCloud Drive, external SSD).

## Versions of one ad

Set `batch_defaults.variants.enabled: yes` in `config.yaml` and turn on the dimensions you want (market, offer, hook, cta). The shot list then asks for the extra takes, the hero EDL marks the swap-able clips with `slot:`, and `tools/variants.py` renders every combination in every ratio with its own name and a `MATRIX.md` that says what changed.
