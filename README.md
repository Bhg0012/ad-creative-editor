# Ad Video Engine

Claude Code project that turns raw footage into upload-ready, QA'd Meta (Facebook + Instagram) video and static ads for AuburnSEO, and keeps its Meta ads knowledge current.

No pasting a giant prompt: `CLAUDE.md` loads automatically, and the workflow lives in skills you call by name.

## One-time setup (MacBook Pro)

```bash
git clone <this repo> && cd ad-creative-editor
tools/setup_mac.sh          # installs ffmpeg-full, Python venv, mlx-whisper, then runs the doctor
```

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
| `tools/inventory.py` | ffprobe every file in `raw/` (rotation, VFR, HDR, resolution flags) |
| `tools/transcribe.py` | Word-level transcripts with mlx-whisper |
| `tools/captions.py` | Burned-in caption file (.ass) from a transcript, inside the safe zone, keyword highlight |
| `tools/qa.py` | Spec, loudness, black-frame, silent-open, and opening-similarity checks plus evidence images |
| `tools/metrics.py` | Hook rate, hold rate, CTR, CPL, verdicts, and grouping by angle / hook / length / ratio |

Run the tests with `.venv/bin/python -m pytest -q`.

## What is not in git

Footage, audio, fonts, proof screenshots, rendered ads, and ad data are ignored by `.gitignore`. Back them up separately (iCloud Drive, external SSD).
