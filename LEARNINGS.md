# Learnings

Running memory across batches. Re-read before every stage.

Format for each entry:
- **YYYY-MM-DD | batch | source** (Bruce's correction / ad results / QA)
  - What happened:
  - Why it matters:
  - Rule going forward:

## Rules in force

- **Safe zones are law on ads.** About 95% of viewers are on mobile Facebook and Instagram Reels, where the app UI covers the top 14%, bottom 35% and 6% each side of a 9:16 frame. Every graphic, caption and CTA goes inside the clear area; QA fails anything that crosses. Long-form or pre-sale videos after the click can be looser. (Bruce, 2026-11-11 and 2026-11-17)
- **Price is part of the ad name, early.** `{market}_{offer}_{price}_{angle}_{hooktype}_{length}s_{ratio}_v{n}`, with `noprice` when the ad states none. Files, folders and results all sort by it. (Bruce, 2026-11-17)
- **Bruce's take picks win** over the selects tool: "keeper" on camera, a pick at the selects gate, or a note in chat. (Bruce, 2026-11-17)

## Winning patterns (from live results)

(none yet)

## Losing patterns (from live results)

(none yet)

## Log

- **2026-11-23 | engine | self-caught process failure**
  - What happened: after the 20-video training pass, the full test run reported 1 failed, 61 passed, and the merge into main went ahead because only the last line of output (the exit code of `tail`) was checked. The failing test was real: a synthesized click sound produced a -0.6 dBTP peak after AAC encoding, over the -1.0 ceiling.
  - Why it matters: Bruce's standing order is never merge red; a peak over the ceiling can be flagged or squashed by Meta.
  - Rule going forward: before any merge, read the pytest summary line itself ("N passed" with no "failed"), not the exit code of a pipe. Fixed the cause: softer click attack, limiter ceiling 1.0 dB under the true-peak maximum.

- **2026-11-17 | engine | Bruce's correction**
  - What happened: the naming convention had no price part; price variants were being folded into the angle part.
  - Why it matters: Bruce sorts and judges ads by offer price first; a buried price makes the upload folder and the results table hard to read.
  - Rule going forward: price is the third part of every ad name; `tools/variants.py`, `tools/deliver.py`, `tools/metrics.py` and QA all use it.
- **2026-11-17 | engine | Bruce's reminder**
  - What happened: Bruce asked to confirm the Meta safe zones are saved as a rule, mobile first.
  - Why it matters: nearly all his viewers are on mobile Reels where the UI covers part of the frame.
  - Rule going forward: safe zones stay a hard QA check on every ad; written into visual-style.md and the rules above.
