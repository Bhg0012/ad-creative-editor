# The Hormozi "vibe editing" ad, the 2026 agentic editing stack, and the plan for this engine

Date: 2026-11-05. Research by two agents (about 75 searches, 55 page reads, 4 live Meta Ad Library queries through the Meta Ads MCP). Items marked "unverified" could not be opened from the research session (facebook.com, acquisition.com, remotion.dev and several vendors are blocked there); open them from the Mac.

## 1. What Bruce saw

**High confidence:** Alex Hormozi's own paid Meta campaign, link title **"Get the Free Vibe Editing System"**, run from his verified page (Ad Library page id 116482854782233).

- First wave 2026-10-07 (about 20 ads), then 2026-10-28, 2026-10-29 and 2026-11-03 (about 50-60 ads total, most still delivering). Example snapshot: https://www.facebook.com/ads/library/?id=4260324617461655
- Copy (from an ad-intelligence listing, quoted in search results): "One of our editors built the whole thing, and we packaged it so you can run it yourself", "talk to it in plain English, and it turns your long videos into finished, on-brand clips", "download it free, paste in our setup code", "absolutely free". Landing page: https://lp.acquisition.com/vibe-editing
- It is a lead magnet for the Acquisition.com funnel, not a product and not open source. No Hormozi post, video, or podcast about it was found, and no endorsement of any editing SaaS (OpusClip, Submagic, Captions, Descript and the rest brand "Hormozi style" presets on their own).
- **What is inside is unverified.** "Paste in our setup code" is the exact distribution pattern of Claude Code video skills (the browser-use/video-use README tells you to paste a setup prompt into Claude Code or Codex and it installs itself). Timing fits too: the "edit video with Claude Code" wave peaked in Sept to Oct 2026 (video-use at 30k+ GitHub stars; an Anthropic engineer editing a launch video entirely in Claude Code with Whisper word timestamps, a JSON edit list, ffmpeg, and Remotion). Hormozi's first ad wave followed on Oct 7.

Two look-alikes in the same ad feed, in case it was one of these: "Mr. Paid Social" (Caleb Kruse) running "Try my Claude Code editing setup" and "Raw take in, finished ad out" since Nov 4 (open source: github.com/mrpaidsocial/mrpaidsocial-video-editor-agent), and "EditFlow AI" ("Turn Claude Into Your Video Editor", Nov 5).

**What Hormozi actually teaches about ads has not changed** (GOATed Ads playbook, quoted): "First, I would make fifty hooks." Three to five bodies per weekly recording session, "only test a few CTAs", "50 hooks x 3-5 meat x 1-3 CTAs = 150 to 750 ads", prep split "80% Hooks, 20% Meat, ~0% CTAs", steal hooks from your own long content and saved ads, test CTAs in isolation, "double down on what works". The AI editor is there to make that volume cheap. That is the lesson for AuburnSEO, not the specific tool.

## 2. How these tools work (and what we copied)

Every serious open-source Claude Code editor converges on one recipe:

1. Transcribe every take to word-level JSON. The model reads text; it never "watches" pixels.
2. The model proposes the cut in plain English; a human approves before anything renders.
3. A JSON or YAML edit decision list (EDL) drives per-segment ffmpeg extraction and concat. Never cut inside a word; pad cut edges 30-200 ms for timestamp drift; silences of 400 ms or more are the cleanest cut points.
4. Captions are rendered last, from word timestamps, 2-4 words per page, active word highlighted.
5. Graphics come from code: Remotion (React) or HyperFrames (HTML), or plain ffmpeg drawtext.
6. Self-QA: ffprobe the output, meter loudness, re-transcribe the cut, screenshot cut boundaries.

Reference implementations: browser-use/video-use (MIT, 30k stars), remotion-dev/skills (official Remotion agent skills), AgriciDaniel/claude-shorts, kurbaitaev/ghost-editor, mrpaidsocial/mrpaidsocial-video-editor-agent (the most ad-oriented: hook splitter, hook variations, native hook overlay, branded ad edit), heygen-com/hyperframes (Apache 2.0 HTML-to-video renderer).

Our engine already had steps 1, 4 and 6 and the gates for step 2. It had no step 3 or 5: the skill said "write a cut list", but nothing turned a cut list into a video, so every edit would have been hand-written ffmpeg. That was the biggest gap, and it is now closed.

## 3. What was built today (all free, all local, all tested)

| Tool | What it does | Status |
|---|---|---|
| `tools/render.py` | EDL yaml to finished ad: reframe to 9:16 or 4:5 around the speaker's face (OpenCV YuNet), static punch-ins and slow pushes, pause tightening (gaps, never words), B-roll overlays with labels, headline hook text from frame 1, lower third, end card in brand colors, voice chain (high-pass, compressor, de-esser), music ducked under the voice (sidechain), SFX, two-pass loudness to -14 LUFS, captions burned last. `--proxy` for 540 px rough cuts with timecode. One EDL renders every ratio. Writes a `.render.json` timeline sidecar. | done, tested end to end |
| `tools/captions.py` | Five caption styles: `chunk` (clean default), `highlight`, `karaoke`, `reveal`, `hormozi` (1-3 words, caps, accent on the spoken word). Config `captions.style`. | done, tested |
| `tools/transcribe.py` | Picks mlx-whisper (Mac GPU), WhisperX (tightest word timing), faster-whisper, or openai-whisper, whichever is installed. Same JSON output for all. | done (backends need a model download on the Mac) |
| `tools/selects.py` | Matches every script line to the best take in the transcripts (top 3 with scores), flags lines never filmed, writes a draft EDL. | done, tested |
| `tools/statics.py` | Static ads (4:5, 9:16) from a photo or a frame: cover crop, gradient, headline, sub line, CTA pill, logo, all inside the safe zone. | done, tested |
| `tools/doctor.py` | Now checks for a transcription backend, the brand font, and the face model. | done |
| Skills | Stage 1b uses the Meta Ads MCP Ad Library search (no browser scraping); 1c and `/ad-results` pull ad metrics from the Meta Ads MCP; stages 5, 6, 8 use selects, EDL, render, statics. | done |
| Playbook | Six new sourced facts (Hormozi campaign, the agentic recipe, captions evidence, hit rate, creatives per ad set, fatigue signals). | done |

Test suite: 26 tests, including a full synthetic render (landscape plus portrait footage, a still, green B-roll, music, SFX, end card, captions, then QA).

## 4. Codebase audit: what else to improve, in priority order

1. **Brand font missing.** `brand/fonts/` is empty, so captions and headlines fall back to a system font. Put the licensed Montserrat ExtraBold file there (doctor flags it).
2. **No transcription backend on this machine.** On the Mac `tools/setup_mac.sh` installs mlx-whisper. For word-by-word caption styles also run `.venv/bin/pip install whisperx` (slower, CPU, but forced alignment makes the timing tight).
3. **Caption safe-zone check is positional, not pixel based.** Captions are placed by margins; QA does not yet rasterize a frame and prove nothing sits in the 14/35/6 bands. Add a check that samples caption-time frames from the `.render.json` and tests the bands (cheap, ffmpeg only).
4. **Hook text vs captions overlap when the first caption page is long.** Headline sits at the top band, captions at the bottom band, so they cannot collide, but a `hormozi` page at 5.8% font height on a 4:5 frame gets close to a lower third. QA by eye for now; make the lower third auto-hide while a two-line page shows.
5. **B-roll index.** Stage 5 still tags footage by eye from contact sheets. Add `tools/inventory.py --sheets` to write per-clip contact sheets and, later, SigLIP2 embeddings so Claude can ask "which clip shows a phone receiving a text".
6. **Remotion for richer graphics.** Animated counters, review cards and phone mockups are still unbuilt. Remotion is free at AuburnSEO's size (individuals and companies up to 3 people) and has official Claude Code skills (`npx skills add remotion-dev/skills`). Add it only when a batch needs a graphic that drawtext cannot do.
7. **Metrics.** `tools/metrics.py` cannot see day-by-day fatigue yet. When the Meta Ads MCP pull includes `time_increment: "1"`, add frequency and CTR trend per ad against the `creative_fatigue` thresholds.
8. **Hook variants from one take.** Hormozi's volume math needs cheap hook swaps. The EDL already supports this (swap the first clip and `hook_text`); add a `--variants hooks.yaml` option to render N openings against one body in one command.
9. **Proxies are not previewable in the app.** Add a one-page HTML review sheet per batch (video, timeline, caption text) so Bruce can review on his phone.
10. **Setup on Linux/CI.** `setup_mac.sh` is Mac only. Add a Linux variant for cloud sessions (ffmpeg with libass, faster-whisper).

## 5. The ChatGPT tool table: are we using these, what do they cost, do they run locally

| Tool | Using it? | Cost | Where it runs |
|---|---|---|---|
| FFmpeg | Yes, it is the backbone of render, inventory, qa, transcribe. | Free (LGPL/GPL). | Local. On the Mac use `brew install ffmpeg-full` (the plain formula lost libass in Jan 2026); `tools/setup_mac.sh` does it. |
| Whisper | Yes: mlx-whisper on the Mac, WhisperX or faster-whisper elsewhere. | Free (MIT models and code). The large-v3-turbo model download is about 1.6 GB once. | Local. No audio leaves the machine. Cloud alternative only if you want it: Deepgram Nova-3 at about $0.0043 per minute. |
| Remotion | Optional, not yet used. The engine draws hook text, labels, lower thirds and end cards with ffmpeg. | Free for individuals and companies up to 3 people (verify at remotion.dev/license); paid above that. | Local (Node, headless Chrome). Install only when a batch needs animated graphics: `npm i remotion` in `batches/<id>/graphics/` plus `npx skills add remotion-dev/skills`. |
| Vision AI | Yes, two ways: OpenCV YuNet face detection for reframing (free, local, 232 KB model shipped in `tools/models/`), and Claude itself looking at contact sheets and QA frames (that is the Claude Code session you are already paying for). | Free beyond the Claude plan. | Face detection local. Frame review goes through Claude. |
| MCP | Yes, read-only, and only where it pays: the Meta Ads MCP for Ad Library research and your own ad metrics. No video goes through MCP. | Free. | Hosted by Meta; connected in Claude. |

So: the whole editing pipeline is free and local. The only recurring cost is the Claude plan. Install everything with `tools/setup_mac.sh`, then `.venv/bin/python tools/doctor.py` tells you what is still missing.

## 6. The ChatGPT project vision, measured against what exists

**Already implemented (do not rebuild):** footage ingest and inventory; word-level transcription; highlight and take selection from the script (`selects.py`); pause removal (`tighten`); automatic assembly, captions, music, graphics, formatting and export (`render.py`); multiple aspect ratios; QA; the gated workflow; brand settings in `config.yaml`; business context (offer, ICP, proof) in the repo; results analysis and a learning loop.

**Phase 1 (functional MVP):** done as of today, pending the brand font and a transcription backend on the Mac.

**Phase 2 (conversational editing, non-destructive timeline):** the EDL yaml is the persistent timeline. "Make the captions bigger and orange" is a one-line config change plus a re-render; "replace the product footage at 12 seconds" is editing one `broll` entry; "lower the music during dialogue" is `music.gain_db` or `duck`. Because every revision is a diff to a small text file in git, version history and undo come free. What is missing is the habit, which the skill now enforces: never hand-cut an MP4, always change the EDL. Previews: proxies render in seconds; a review page is item 9 above.

**Phase 3 (scene analysis, B-roll selection, variations):** partly there (face-centered reframing, hook text, variants by EDL). Items 5 and 8 above cover the rest.

**Phase 4 (business integration, multiple clients):** the engine already separates business context (`config.yaml`, `playbook/`, `LEARNINGS.md`) from tools (`tools/`, skills). Recommendation: keep one repo for now. A second repo and a CLI or MCP server between them is real cost (two checkouts, a brief format, a job runner) with no benefit until there is a second client. When that day comes, the clean split is: this repo becomes the editor (tools, skills, playbook), and each business gets a folder or repo with `config.yaml`, `brand/`, `raw/`, `batches/` that the skill is pointed at with a `--business <path>` flag. The campaign brief format already exists: it is `brief/01..10` in each batch. No MCP server is needed to make Claude in one folder use tools in another; a path is enough.

**Trade-offs worth stating before any architecture change:**
- ffmpeg EDL vs Remotion-first: ffmpeg renders in seconds, needs no Node, and is deterministic; Remotion is better for animated graphics and worse for cutting footage. Keep ffmpeg as the backbone and add Remotion compositions only for graphics.
- Local Whisper vs cloud transcription: local is free and private; cloud is faster for a 30-minute dump when the Mac is busy. Local by default.
- Vision models for footage understanding: Claude reading contact sheets is enough at this volume. A local embedding index (SigLIP2) is a later optimization, not a requirement.
- MCP: use what is already connected (Meta Ads). Do not build one.

## 7. What Bruce should do next

1. Open the Hormozi landing page and one ad snapshot (links in section 1) and drop the "setup code" text, if it is visible, into `brief/swipe/` of the next batch; if it turns out to be a Claude skill, the research agent's read was right and there is nothing in it this engine does not already do.
2. Put the licensed Montserrat ExtraBold file in `brand/fonts/` and the logo at `brand/logo.png`.
3. Run `tools/setup_mac.sh` once, then `.venv/bin/python tools/doctor.py`.
4. Fill the `TBD` offer and market fields in `config.yaml` (doctor lists them).
5. Film the first batch and run `/ad-batch`. The first real footage will surface the remaining rough edges in `render.py` faster than any more research.

## 8. Update 2026-11-06: overnight build

Added, tested, and merged:

| Feature | Where | Why it matters for conversion |
|---|---|---|
| Single-variable versions of a hero ad | `tools/variants.py`, `config.yaml` -> `batch_defaults.variants` | Hormozi's volume math: one body, many hooks, markets, offers, CTAs. Each version renders in every ratio with its own name, and `MATRIX.md` says what changed. The config switch makes the shot list ask for the extra takes up front. |
| Callouts | EDL `callouts[]` | A number, a re-hook, or the offer line on screen at the moment it is spoken. Re-hooks at 3 s, 8-10 s and before the proof are where viewers drop. |
| Picture-in-picture B-roll | EDL `broll[].pip` | Review screenshots and phone photos as an inset with a white border instead of a blurry full-frame crop. HEIC photos straight from the iPhone are converted on the fly. |
| End card CTA button | EDL `end_card.text` drawn as an accent pill, optional `headline` | The last 2-3 s state the exact action, and it looks like something a thumb would tap. |
| Light grade | EDL or config `look` | Phone footage gets a consistent, slightly punchier look across every concept without crushing skin tones. |
| 30 ms audio fades at every cut | `tools/render.py` | Jump cuts never click or pop. Professional editors do this by reflex; the engine now does it for every segment. |
| Rotated iPhone clips and HDR footage | `tools/render.py` tests | Portrait video stored as rotated landscape (what iPhones write) and HLG or HDR10 clips render correctly; both are covered by tests. |
| Per-clip contact sheets | `tools/inventory.py --sheets` | Read a whole take at a glance with timecodes, which is how B-roll gets tagged in Stage 5. |
| Stricter QA | `tools/qa.py` | Caption geometry proven inside the safe zone with the real font metrics, caption vs lower third overlap, headline present on frame 1, a face in the hook and in the CTA, duration guidance, and `--script` checks every script line is heard. |
| Review page | `tools/review.py` | One local HTML page per batch with players, timelines, captions, QA tables, copy, and a notes box per ad that copies back into the chat. Serve it with one command and review on the phone. |
| Sample builder | `tools/make_sample.py` | Proves the whole pipeline on a fresh machine in about three minutes with no footage: synthesized voice (your Mac's `say`), placeholder takes in both orientations, mock B-roll, a stand-in proof image, music, SFX, captions, QA. |
| Copy and caption linter | `tools/lint_copy.py` | Catches em dashes, jargon, personal-attribute wording, unproven claims, fake urgency, unlabeled numbers, and length limits in copy files, EDL texts and captions before anything reaches you. |
| One-command ratios | `tools/render.py --all-ratios --captions auto` | Every ratio from one EDL, transcribed once, so Reels and Feed versions can never drift apart. |
| Fatigue reads | `tools/metrics.py` | Reads a Meta Ads MCP JSON pull directly and flags ads whose link CTR fell 15% or more over the last 7 days with frequency above 2.5. |
| Self-review loop in the skill | `.claude/skills/ad-batch/SKILL.md` Stage 6 | Render, look at the QA evidence, fix the EDL, re-render, up to three passes, before Bruce sees anything. |

Test suite: 31 tests, including a full synthetic render with every feature above.

### What one ad costs if Claude runs on the API instead of the Claude Code plan

If you run the engine inside Claude Code on your plan, the plan covers it. The numbers below are for the case where the same work runs through the API (for example an automated pipeline or the Agent SDK). They are estimates from the token shapes of this workflow, not measurements; the first real batch will give exact numbers from the usage fields.

Assumptions for one hero ad from an approved script and footage already on disk (Stages 5 and 6, plus QA): the skill and config in context (about 8K tokens, cached), transcripts and inventory (about 6K), the EDL (1K), 3 to 5 contact sheets and 20 to 30 QA frames viewed across two or three self-review passes (about 40K image tokens), roughly 40 tool calls, and 30 to 40K output tokens including thinking.

| Model | Price (input / output per million tokens; cache reads) | One hero ad | One variant (render plus a check) | Full batch (research through launch plan, 6 concepts plus variants) |
|---|---|---|---|---|
| Claude Fable 5.1 | $10 / $50; $0.25 | about $3 to $5 | about $0.20 to $0.50 | about $20 to $45 |
| Claude Opus 5.5 | $4 / $20; $0.20 | about $1.50 to $2.50 | about $0.10 to $0.25 | about $9 to $20 |
| Claude Sonnet 5.5 | $2 / $10; $0.20 | about $0.75 to $1.25 | about $0.05 to $0.15 | about $5 to $10 |

Prices are Anthropic's first-party API rates as cached in the Claude API skill on 2026-10-06; check the pricing page before budgeting. The biggest lever is images: every QA frame costs roughly (width x height) / 750 tokens, so the engine downsizes evidence frames to 360 px wide before Claude looks at them.

### How long one ad takes

Machine time on an M-series Mac (approximate): proxy 10 to 20 s, master 30 to 60 s, transcription of the master 10 to 30 s with mlx-whisper, captioned final 30 to 60 s, QA 20 s. Under three minutes of rendering per ad end to end.

Claude's working time: the first hero ad from an approved script, including footage review, selects, EDL, two or three self-review passes, and QA, runs 10 to 20 minutes of session time. Each variant is 1 to 3 minutes, mostly render time. A full batch (research, angles, offer, hooks and scripts, six concepts, variants, copy, QA, launch plan) is 2 to 4 hours of session time spread across the gates, because every gate waits for your yes. Filming and your review cycles dominate the calendar, not the editor.
