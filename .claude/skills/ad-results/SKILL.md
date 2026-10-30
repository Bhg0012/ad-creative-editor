---
name: ad-results
description: Analyze live Meta ad results for AuburnSEO, diagnose each ad (opening, body, offer, or form), compute the batch hit rate, write winning and losing patterns to LEARNINGS.md, and propose the next batch. Use when Bruce comes back with ad data, asks how his ads are doing, which ads to kill or scale, or what to make next.
---

# Ad results and learning loop

## Steps

1. **Get the data.** If the Windsor.ai MCP is connected, pull Meta Ads data at ad level for the batch's date range (ad name, spend, impressions, 3-second video plays, ThruPlays, average watch time, link clicks, leads, frequency; list available fields first to get exact names) and save it as `data/<batch id>_<date>.csv`. Otherwise ask Bruce for an Ads Manager CSV export at ad level with those columns. Read-only: never change anything in Ads Manager without Bruce approving the specific change.
2. **Lead quality.** Ask Bruce (or pull from the CRM if connected) how many leads per ad qualified, booked, and closed. CPL without lead quality is misleading.
3. **Compute.** Run `.venv/bin/python tools/metrics.py <csv> --target-cpl <target> --out data/analysis_<batch id>_<date>`. Read `ad_metrics.md`. Go deeper in a notebook in `data/` if needed (pandas, seaborn), e.g. trends by day or frequency.
4. **Diagnose each ad** against the account's own medians first and playbook benchmarks second (playbook `hook_hold_benchmarks`):
   - low hook rate -> new opening
   - good hook, low hold -> body and pacing
   - good hold, low CTR -> offer and CTA
   - good CTR, bad CPL or lead quality -> form, landing page, follow-up speed, audience
   Respect the verdicts' spend thresholds; call out anything judged on a low sample.
5. **Hit rate:** winners / ads tested for the batch, and the running hit rate across batches.
6. **Write to `LEARNINGS.md`:** winners' patterns and losers' patterns (angle, hook type, opening shot type, length, format, caption style, music energy), each with the evidence and its sample size. Promote a pattern to "Rules in force" only after it holds across at least two batches or a clearly significant result.
7. **Recommend actions** for live ads (pause, keep, raise budget, duplicate into a new test) and wait for Bruce's approval of each specific change.
8. **Propose the next batch:** 50-70% new concepts in the winning angle families, 30-50% iterations on winners (one variable at a time), plus at least one wild-card angle. Log the plan in `DECISIONS.md` with the evidence. Start it with `/ad-batch` when Bruce says go.
