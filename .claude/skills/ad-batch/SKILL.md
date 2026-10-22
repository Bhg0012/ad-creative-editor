---
name: ad-batch
description: Start or resume a batch of Meta (Facebook + Instagram) video and static ads for AuburnSEO, from live research through angles, scripts, editing, captions, sound, QA, copy, and launch plan, with an approval gate after each stage. Use when Bruce wants new ads, a new batch, to edit footage into ads, or to continue a batch in progress.
---

# Ad batch pipeline

Work one stage at a time. At every **GATE**: stop, show the output, update `BATCH.md`, and wait for Bruce's "yes". Apply every note he gives and log it in `LEARNINGS.md` immediately.

Reference files (read when the stage needs them):
- `reference/angles-and-hooks.md`: angle families, hook types, hook scoring rubric
- `reference/scripts-and-editing.md`: beat timing, script format, cadence, captions, graphics, sound, ffmpeg recipes
- `reference/compliance.md`: hard rules and the per-ad compliance checklist
- `reference/copy-package.md`: primary text, headlines, CTA, Instant Form
- `reference/launch.md`: campaign structure, pre-publish audit, kill/keep rules

## Stage 0: start or resume

1. Run `.venv/bin/python tools/doctor.py`. Expired playbook facts -> run `/refresh-playbook` first. Missing tools -> give the install command and wait.
2. Read `LEARNINGS.md`, `DECISIONS.md`, `config.yaml`.
3. Resuming? Find the batch in `batches/`, read its `BATCH.md`, continue at the first unfinished gate.
4. New batch? Confirm market (one per batch, never blend Auburn-Opelika and Huntsville) and offer, then run `.venv/bin/python tools/new_batch.py --market <HSV|AUB> --offer <slug>`.
5. Ask every `TBD` needed for Stages 1-3 in ONE batched list. Never guess offer terms, price, guarantees, results, or scarcity.

All batch paths below are relative to `batches/<id>/`.

## Stage 1: live research (no editing)

Goal: know the market today, not as of training data.

**1a. Best practices.** Start from `playbook/facts.yaml` (already verified and dated). Then search the web for anything from the last 3 months that changes or adds to it, focused on: creative diversity and delivery, Reels/Feed specs and safe zones, hook/pacing/caption trends in local-service and B2B-to-small-business ads (DTC ecommerce only if clearly transferable), lead-gen form and lead-quality changes, and policy changes. Write `brief/01_research.md` with a source and date on every claim; flag anything older than 12 months as possibly stale. Any new durable fact also goes into `playbook/facts.yaml` with the same fields as the others.

**1b. Competitor and swipe research.** Use Claude in Chrome (start Claude Code with `claude --chrome`, or run `/chrome` in the session; needs the Claude in Chrome extension in Google Chrome) to open the Meta Ad Library (facebook.com/ads/library, country United States, ad category All ads). If the browser is not connected, ask Bruce to connect it or to drop Ad Library screenshots into `brief/swipe/`; do not invent ads. Search:
- agencies selling the same offer type to contractors ("review management for contractors", "contractor websites", "home service marketing", "GoHighLevel agency", "more Google reviews")
- local competitors in the batch's market
- big national players in the space

Longevity is the signal: an ad still active 30+ days after its "Started running on" date is likely profitable (caveat: big brands sometimes leave ads on regardless). For the top 10-15 long runners, log in `brief/02_swipe.md`:

| advertiser | days running | format | length | hook (first line + first visual) | angle | offer | CTA | proof used | why it likely works |

Then list **gaps**: angles nobody in this market uses, and claims everybody makes (now invisible).

**1c. Bruce's own data.** If the Windsor.ai MCP is connected, pull all past Meta ads (discover field names with its field-listing tool; you need ad name, spend, impressions, 3-second video plays, ThruPlays, average watch time, link clicks, leads, frequency) and save as CSV in `data/`. Otherwise read CSV exports in `data/`. Run `.venv/bin/python tools/metrics.py <csv> --target-cpl <config target_cpl> --out data/analysis_<date>` and go deeper in `data/analysis.ipynb` (pandas, seaborn) if useful. Identify best and worst ads by CPL (flag low samples), whether hook or hold is the bottleneck, and which angles, hooks, and lengths correlate with better results. State sample-size caveats; do not over-fit a handful of ads. Summarize in `brief/03_my_data.md`. No data yet? Say so and move on.

**GATE 1:** one page: top 5 current findings, top 5 competitor patterns, the gaps, what Bruce's data says.

## Stage 2: ICP, awareness, angle map

**2a. ICP deep profile (`brief/04_icp.md`)** from config, sales-call notes, and research:
- Firmographics: trade, size, years in business, revenue band if inferable, market.
- A day in their life: when they are on Facebook/Instagram (early morning, lunch, evening after jobs), device, mental state.
- Pains in their own words: quote real phrasing from competitor reviews, Reddit (r/sweatystartup, r/HVAC, r/Plumbing, r/Construction, r/Roofing), contractor Facebook groups, and Bruce's notes. Quote, don't paraphrase; note the source of each quote.
- Desires: more booked jobs, higher-ticket jobs, less dependence on word of mouth, beating the competitor down the road, looking legit.
- Objections and skepticism ("agencies are scammers", "too busy", "word of mouth is enough", "tried it before", "not techy", "how much?"): for each, the strongest honest rebuttal and which real proof answers it.
- Status and identity triggers: pride in craft, most trusted in town, seen as the pro.
- Language to avoid: SEO, funnel, CRM, conversion, leverage, optimize. Translate to outcomes: phone ringing, jobs booked, 5-star reputation, showing up first on Google.

**2b. Awareness and sophistication.** Classify awareness (unaware, problem-aware, solution-aware, product-aware, most aware) and market sophistication (how many similar claims they have already seen). Low awareness opens on the problem or a story. High sophistication needs a new mechanism or proof, not bigger claims.

**2c. Angle map (`brief/05_angles.md`).** Generate at least 8 genuinely different angles using `reference/angles-and-hooks.md`, then recommend the best 5-6 for this batch, diverse across families. For each: target awareness level, core promise, key proof (real only), primary objection handled, emotional driver (fear of loss, pride, envy, relief, greed, control), and the planned format (talking head, screen-recording-led, text on B-roll, static).

Size the batch to the budget: each live ad needs enough spend to be judged (see `reference/launch.md`). If budget is small, fewer, more different concepts beat many thin ones.

**GATE 2:** ICP summary and angle shortlist with reasoning.

## Stage 3: offer and message engineering

**3a. Offer review (`brief/06_offer.md`).** Score the offer on the value equation: (dream outcome x perceived likelihood) / (time delay x effort). For each lever, propose concrete, honest improvements Bruce could actually deliver (faster setup, done-for-you, guarantee, bonus, no contract). These are suggestions only; nothing goes in an ad until Bruce approves it. Write the one-sentence offer a contractor understands in 3 seconds.

**3b. Message hierarchy per angle:** (1) the one thing the viewer must remember, (2) 1-2 proof items max, (3) one CTA (one ask per ad, matching the real destination).

**3c. Wording rules:**
- Grade 5-6 reading level. Short words, short sentences.
- Talk like a local, not an agency. Southern-friendly is fine; fake is not.
- Specific beats general: "$4,800 roof job" beats "more revenue". Numbers are real or labeled as an example on screen.
- "You" and "your business" far more than "we" and "I".
- Every line answers "so what?" for a busy contractor.
- Call out by trade and place, never by hardship (personal attributes policy).

**GATE 3:** offer statement, message hierarchy per angle, recommended offer improvements.

## Stage 4: hooks and scripts

**4a. Hooks (`brief/07_hooks.md`).** For each angle write 5 hooks, each with three synced layers: visual hook (frame 1 to 1.5s, different from every other ad's opening), text hook (max ~7 words, inside the safe zone, on screen from frame 1), spoken hook (first sentence, under ~2 seconds). Mix hook types and score each with the rubric in `reference/angles-and-hooks.md`. Pick the top 1-2 per angle and justify.

**4b. Scripts (`brief/08_scripts.md`).** Timed scripts per selected angle and length using the beat table and line format in `reference/scripts-and-editing.md`. Any ad over 20s gets 2-3 re-hooks where viewers typically drop. Run the compliance checklist on every line now, not at the end.

**4c. Shot list (`brief/09_shotlist.md`)** for footage Bruce still needs: shot, framing, location, lighting note, line to say, number of takes, alternate hooks to record back-to-back. Prefer phone-native, UGC-style framing for trust. Vary locations, outfits, and backgrounds across angles so concepts are visually distinct.

**GATE 4:** hooks with scores and full scripts. If filming is needed, stop until footage is in `raw/`.

## Stage 5: ingest and rough cut

1. **Inventory:** `.venv/bin/python tools/inventory.py --raw raw --out work/inventory.csv`. Note flags (variable frame rate, HDR, below 1080p) and handle them in the edit (convert VFR to constant, HDR to SDR).
2. **Transcribe:** `.venv/bin/python tools/transcribe.py raw/<files> --out work/transcripts` (word-level JSON + SRT + TXT). Check low-confidence words by ear.
3. **Look at the footage:** contact sheets (1 frame per 2s) into `work/`, then view them. Tag each clip: framing, setting, energy, problems (blur, bad light, wind noise).
4. **Selects (`work/selects.md`):** best take per script line: correct words, best delivery, no stumbles. Energy and clarity over perfection.
5. **Cut list per ad (`work/cuts/<ad>.csv`):** source file, in, out, purpose. Remove dead air, breaths between sentences, ums, restarts. Trim gaps, not words; never speed up speech.
6. **Rough cut proxies:** low-res, no graphics, burned-in timecode, in `work/proxies/`.

**GATE 5:** rough cuts plus cut lists. Apply every note; log each in `LEARNINGS.md`.

## Stage 6: full edit

Follow `reference/scripts-and-editing.md` for cadence, captions, graphics, sound, and render settings. Key points:
- Pattern interrupt every 2-4s in the first 10s; B-roll shows what the VO says; face on screen in hook and CTA.
- Captions are generated from a transcript of the final cut (`tools/transcribe.py` then `tools/captions.py`), never retyped.
- Every text element inside the safe zone for its ratio.
- Mix to the loudness target in `config.yaml`, verified by `tools/qa.py`.
- Must make complete sense with sound off, and with eyes closed.

**Variants:** after the hero is approved, make variants that are meaningfully different: (1) different visual hook (shot, setting, format), not just different text; (2) different length (15s cut-down); (3) different format (talking head vs screen-recording-led vs text on B-roll vs static); (4) aspect ratios (9:16 primary, 4:5 for Feed) reframed to keep face and text in frame, never letterboxed. Label each as `new` or `iteration` in `DECISIONS.md`.

**Statics** (if `also_make_statics`): 2-3 per batch from strong frames or real proof screenshots, 1440x1800 (4:5) and 1440x2560 (9:16), headline inside the safe zone, one message, one CTA.

**GATE 6:** the first full-quality hero ad, before any variants. Apply notes, log them, then produce the rest.

## Stage 7: copy package

For every ad, write `exports/<adname>_copy.md` per `reference/copy-package.md`. Message match with the video is mandatory.

## Stage 8: QA (before Bruce sees anything)

1. Run `.venv/bin/python tools/qa.py exports/*.mp4 --qa-dir qa`. It checks specs, loudness, black frames, silent openings, and opening similarity, and writes evidence images.
2. Open and look at every evidence image: contact sheet, first frame (would it stop a scroll as a still?), safe-zone frames, mobile 360px frames.
3. Diff burned-in captions against the transcript; spell-check and fact-check every on-screen word.
4. Run the compliance checklist from `reference/compliance.md` line by line, per ad.
5. Hook audit: no two concepts share the same opening shot plus opening line.
6. Mark every MANUAL row in `qa/REPORT.md` PASS or FAIL. Fix and re-run until nothing fails. Never deliver a failing ad.

**GATE 7:** deliver the batch: all videos, statics, copy files, and the QA report.

## Stage 9: launch plan

Write `brief/10_launch.md` per `reference/launch.md`: structure, budget sanity check against the learning phase, the pre-publish settings audit (Advantage+ creative enhancements, AI disclosure, placements), naming, and kill/keep rules with numbers derived from `target_cpl`. After launch, results go through `/ad-results`.

## Naming convention

`{market}_{offer}_{angle}_{hooktype}_{length}s_{ratio}_v{n}.mp4`, e.g. `HSV_reviews_lostjobs_question_30s_9x16_v1.mp4`. Each part uses letters, digits, and hyphens only (no underscores inside a part), so `tools/metrics.py` can group results by angle, hook type, length, and ratio. Use the same name for the ad in Ads Manager.
