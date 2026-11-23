---
name: ad-results
description: Analyze live Meta ad results for AuburnSEO, diagnose each ad (opening, body, offer, or form), compute the batch hit rate, write winning and losing patterns to LEARNINGS.md, and propose the next batch. Use when Bruce comes back with ad data, asks how his ads are doing, which ads to kill or scale, or what to make next.
---

# Ad results and learning loop

## Steps

1. **Get the data.** If the Meta Ads MCP is connected (`ads_get_ad_accounts`, then `ads_get_ad_entities` at `level: ad`, `reporting_purpose: ["creative"]`, with a `time_range`; verify field names with `ads_get_field_context`), pull ad-level rows and save them as `data/<batch id>_<date>.csv`. Else if the Windsor.ai MCP is connected, pull Meta Ads data at ad level for the batch's date range (ad name, spend, impressions, 3-second video plays, ThruPlays, average watch time, link clicks, leads, frequency; list available fields first to get exact names) and save it as `data/<batch id>_<date>.csv`. Otherwise ask Bruce for an Ads Manager CSV export at ad level with those columns. Read-only: never change anything in Ads Manager without Bruce approving the specific change.
2. **Lead quality.** Ask Bruce (or pull from the CRM if connected) how many leads per ad qualified, booked, and closed. CPL without lead quality is misleading. When CRM stages exist, rank ads by cost per qualified lead and cost per booked call, not CPL (Ben Heath, V12; Sabri Suby, V13 budgets on closed revenue).
3. **Compute.** Run `.venv/bin/python tools/metrics.py <csv> --target-cpl <target> --out data/analysis_<batch id>_<date>`. Read `ad_metrics.md`. Go deeper in a notebook in `data/` if needed (pandas, seaborn), e.g. trends by day or frequency.
4. **Diagnose each ad** against the account's own medians first and playbook benchmarks second (playbook `hook_hold_benchmarks`):
   - low hook rate -> new opening
   - good hook, low hold -> body and pacing
   - good hold, low CTR -> offer and CTA
   - good CTR, bad CPL or lead quality -> form, landing page, follow-up speed, audience
   Respect the verdicts' spend thresholds; call out anything judged on a low sample. Judge on 7-day rolling numbers and at least 7 days of data (playbook `evaluation_window`). Step 0 before blaming any ad: compare account-wide CPM and CTR with the prior 7 days and look for a season or local event (SEC football Saturdays, the Iron Bowl, storm weeks for roofers; local inference) (Sabri Suby, V13).
   Fatigue check (playbook `creative_fatigue`): frequency is never the signal on its own. Fatigue is frequency climbing together with CTR falling and CPM rising (Sabri Suby, V13; Professor Charley T, V14). When a winner fades, refresh in this order: the visual first (a new opening shot, or a new static on the same copy), then the headline, then the body copy. Make 2-3 new visuals, not Sabri's 15-100 (V13).
   **Retention:** run `tools/metrics.py` with `--render-dir batches/<id>/exports`. It reads the video p25/p50/p75/p95 columns, converts the biggest drop to seconds, and names what was on screen at that moment from the ad's `.render.json` ("lost 38% by 7.5 s, during the compare plate"). Fix that moment, not the whole ad (Matt Wolfe, V20, adapted from Shorts retention curves).
   **Small-budget tests:** with `--impression-cap N`, ads that reached the cap are marked and ranked on hook rate, hold and link CTR at equal exposure; CPL is judged only on the 2-5 survivors (Sergio C, V15; playbook `small_budget_fair_test`).
5. **Hit rate:** winners / ads tested for the batch, and the running hit rate across batches.
6. **Write to `LEARNINGS.md`:** winners' patterns and losers' patterns (angle, hook type, opening shot type, length, format, caption style, music energy), each with the evidence and its sample size. Promote a pattern to "Rules in force" only after it holds across at least two batches or a clearly significant result.
7. **Recommend actions** for live ads (pause, keep, raise budget, duplicate into a new test) and wait for Bruce's approval of each specific change.
8. **Contrast winners and losers.** Run `.venv/bin/python tools/reference.py` on the top 3 and the bottom 3 exports and compare hook pace, first frame, change events per second and music. Write the differences into the plan, with sample-size caveats (Matt Wolfe, V20, adapted from organic Shorts to ads).
9. **Propose the next batch:** 50-70% new concepts in the winning angle families, 30-50% iterations on winners, plus at least one wild-card angle. An iteration changes one variable, but as a big swing (a whole new hook, not a word) (Dara Denney, V7). Porting a winner's big idea to another format counts as an iteration: every winning video idea gets 1-2 statics, and every winning static idea gets a video (Dara Denney, V1; Alessio Cordeddu, V8). Log the plan in `DECISIONS.md` with the evidence. Start it with `/ad-batch` when Bruce says go.

## Optional monthly run

Bruce can schedule this skill monthly, like the playbook refresh, so winners and losers update the rules without waiting to be asked (Matt Wolfe, V20). A scheduled run only reads data and proposes; it never changes Ads Manager.
