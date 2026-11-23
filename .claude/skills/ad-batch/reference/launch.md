# Launch plan

Write to `brief/10_launch.md`. Check every point against `playbook/facts.yaml` first; Meta changes these settings often.

## Structure

- One campaign per objective (Leads). One broad ad set per market; never blend Auburn-Opelika and Huntsville. Location targeting by the market's real service radius.
- Advantage+ placements unless the data says otherwise.
- All the batch's ads in that one ad set, uploaded at once so they share one learning period (playbook `learning_phase`). 4-8 live ads per ad set at Bruce's budget (playbook `creatives_per_adset`; Professor Charley T's small-account fallback, V14). Produce 5-6 concepts, run 4-8 ads, keep the rest in reserve for the next side test. Volume grows with budget: "You graduate into volume as the account grows" (Sergio C, V15).
- **Meta's spend split is not the verdict.** At $30-100/day delivery puts 80-90% of spend on one or two ads, and the starved ads are sometimes the real winners (Sergio C, V15; Sabri Suby, V13). Use the small-budget fair test below before calling winners.
- **Optional flexible ad (3-2-2):** run one body's 3 hook versions as one flexible ad: 3 videos (same format, same aspect ratio), 2 meaningfully different primary texts, 2 headlines. One data bucket with diversity inside, which suits a small budget. Judge it as one unit; per-combination results are not reported (Professor Charley T, V14; playbook `flexible_ad_322`).
- Ad names in Ads Manager exactly match the export filenames (naming convention) so `tools/metrics.py` can group results.
- Budget clears the minimum Ads Manager enforces at publish for the objective and country (reported Nov 2026, playbook `meta_news_2026_11`); a too-small test campaign is refused, not warned.

## Small-budget creative test (daily budget under about $100)

Sergio C (V15), with Sabri Suby (V13) and Professor Charley T (V14) agreeing that spend share is not a verdict. Playbook `small_budget_fair_test`.

- Pre-screen with an impression cap: 1,000 impressions minimum per ad, 2,000-3,000 preferred. Pause each ad when it reaches the cap, even one that looks great.
- Judge at equal exposure on upstream numbers: hook rate, hold, link CTR, CPM. `tools/metrics.py --impression-cap N` marks the ads that reached the cap and ranks them.
- Judge CPL only on the 2-5 survivors; at this sample each ad has 0-4 leads, which says nothing about CPL. A 1% vs 3% link CTR is clear at 2,000 impressions; 1% vs 1.3% is noise.
- Show Bruce the math first: ads x cap x CPM / 1000 / daily budget = days. Example: 6 ads x 2,000 impressions at a $30 CPM is $360, 12 days at $30/day.
- Every manual pause needs Bruce's yes (read-only rule).

## Batch 2 onward: protect what works

- If the live ad set is at or under target CPL, do not add new ads to it. New ads start with no data and pull delivery from the incumbents while they learn (Professor Charley T, V14; Sergio C, V15; playbook `protect_working_campaign`).
- Test the new batch on the side (a separate test campaign or test ad set) and move an ad in only when it beats the current ones. If the budget cannot fund a side test at the publish minimum (playbook `meta_news_2026_11`), swap the losers out in one batched edit instead.
- When moving a proven ad, reuse its post ID so its comments and reactions carry over (Professor Charley T, V14).
- While a test runs, hands off: no new ads, no edits (V14).

## Optional retargeting ad set

Only if the budget sanity check passes with room to spare: a small ad set for video viewers and form openers, running objection-handling, real proof and close statics (Sabri Suby, V3; Alessio Cordeddu, V5). Never a different offer that Bruce does not actually sell.

## Budget sanity check

- Learning needs roughly 50 optimization events per ad set in 7 days. Compute: weekly budget / expected CPL. If that is far below 50, say so and propose the fix: one ad set only, a longer evaluation window, or temporarily optimizing for a more frequent event. Do not pretend the ad set will exit learning.
- Each ad needs enough spend to be judged: at least 2-3x `target_cpl` per ad over the test. If the budget cannot give every ad that, cut the number of live ads.
- Budget changes: batch edits together, at the campaign level; large jumps can restart learning. Raise only while the 7-day CPL beats target, by no more than about half the margin (Professor Charley T, V14: 10% better than target means raise 5% or less). At $30-100/day that is about $5-10/day per step (Sergio C, V15). Cost per result looks worse for a few days after each raise; that is math, not failure (V14). All heuristics, not Meta rules.

## Lead quality

- Instant Form: "Higher intent" type plus qualifying questions (see `reference/copy-package.md`).
- Connect the CRM (config `offer.crm`) so lead stages (qualified, booked, won) flow back to Meta via the Conversions API for CRM. Once volume allows, test the Conversion Leads performance goal (playbook `conversion_leads`), which optimizes for leads that qualify, not just form fills.
- Speed to lead decides cost per booked call more than the ad does: set up instant text/call follow-up before launch.
- Instant Form conditional logic: one multiple-choice question routes clear non-fits (wrong market, not the owner, a trade not served) to a closing screen so they never count as leads; phone OTP verification on Higher intent forms (Ben Heath, V12; playbook `instant_form_disqualify`; wording in `copy-package.md`). Optimize for and report cost per qualified lead, not cost per raw lead. Do not over-filter: fewer counted leads slows learning.
- Tracking must be right before kill or keep calls: "If you're making decisions based on inaccurate data, you will be making wrong decisions" (Ben Heath, V12).

## Pre-publish audit (every ad, every launch)

- [ ] Advantage+ creative enhancements: open each ad's creative settings and the ad account's creative feature defaults; turn off anything not deliberately tested (text changes, added music, image-to-video, generated backgrounds, overlays). Re-check after any Meta UI change.
- [ ] AI disclosure set if any photorealistic AI-generated or AI-altered content.
- [ ] Placement previews in Ads Manager checked for Reels, Stories, and Feed: nothing cropped or covered.
- [ ] Destination tested on a phone: form submits, booking link works, thank-you screen shows.
- [ ] Copy matches video (message match) and the compliance checklist passed.

## Staging the campaign through the Meta Ads MCP (only on Bruce's yes)

The Meta Ads MCP can build the whole campaign as a draft in Ads Manager. Nothing goes live and nothing spends until it is published. This is a write to Bruce's ad account, so it needs his explicit yes in this session for this batch, after he has seen `brief/10_launch.md`.

What Bruce sets up once, by hand, because the MCP cannot: the Instant Form (it attaches an existing form by ID, it cannot build one), the Lead Ads Terms of Service on the Page, and the Pixel or CRM connection.

Order:
1. Read the account: `ads_get_ad_accounts` (currency, `min_daily_budget_cents`), `ads_get_ad_account_pages` (Page ID, `leadgen_tos_accepted`), `ads_get_ig_accounts` (Instagram ID, required for Reels delivery).
2. Upload each video from `deliver/`: `ads_create_upload_url` (name, size, MIME), upload with curl, `ads_finalize_upload`, then poll `ads_get_ad_videos` until the status is ready. Up to 500 MiB per file. This runs where the files are, so it happens in a session on Bruce's Mac, not in the cloud.
3. `ads_create_campaign`: objective `OUTCOME_LEADS`, the budget Bruce stated (never inferred), campaign-level budget unless he asks otherwise.
4. `ads_create_ad_set`: one per market, broad geo targeting on the real service radius, Advantage+ audience and placements unless the plan says otherwise, the lead goal from the plan.
5. Per video: `ads_create_creative` with the Page and Instagram IDs, the video ID, `primary_texts`, `headlines` and the CTA from `exports/<adname>_copy.md`, the lead form ID or link, URL parameters for tracking, and `self_ai_disclosure` exactly as Bruce decided (never set it for him). Then `ads_create_ad` with the ad name equal to the file name.
6. Read back every object with `ads_get_ad_entities` (draft state) and fix every blocking error. Report which Advantage+ creative enhancements Meta switched on by default, so Bruce can turn off any not under test.
7. Stop. Bruce reviews the draft in Ads Manager and publishes it himself, or says "publish" and the campaign is published with `ads_activate_entity`. Publishing starts spending.

## Kill / keep rules (derive numbers from target_cpl)

Evaluate an ad only after BOTH a spend threshold and at least 7 days of data, judged on 7-day rolling numbers, whichever comes later (Sabri Suby, V13: "no ad gets paused and especially not killed until... you've got at least 7 days worth of data"; Professor Charley T, V14: "Most people kill these tests before the system has a chance to work"; playbook `evaluation_window`). Never crown a winner before 7 days either: early CPL often looks better than it settles (V14).

Step 0, before any verdict: compare account-wide CPM and CTR with the prior 7 days and look for a season or a local event (SEC football Saturdays, the Iron Bowl, storm weeks for roofers; local inference from Sabri Suby, V13). Then check fatigue: frequency together with falling CTR and rising CPM, never frequency alone (V13, V14; playbook `creative_fatigue`).

`tools/metrics.py --target-cpl` applies these defaults:

| Situation | Verdict |
|---|---|
| Spend under 1x target CPL | Too early |
| Spend 2x target CPL, zero leads | Kill candidate |
| Spend 3x target CPL, CPL over 1.5x target | Kill candidate |
| 3+ leads at or under target CPL | Winner candidate |
| Otherwise | Keep running |

Then diagnose (vs the account's own medians first, playbook benchmarks second):
- Low hook rate -> new opening (visual + spoken hook).
- Good hook, low hold -> body and pacing, earlier proof, re-hooks.
- Good hold, low CTR -> offer clarity and CTA.
- Good CTR, high CPL or poor lead quality -> form, landing page, follow-up speed, or audience.

Iterate on winners one variable at a time, as a big swing (a new hook is one variable: a new opening shot and line, not a word) (Dara Denney, V7). Never pause or edit live ads without Bruce's approval of the specific change.
