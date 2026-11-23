# Launch plan

Write to `brief/10_launch.md`. Check every point against `playbook/facts.yaml` first; Meta changes these settings often.

## Structure

- One campaign per objective (Leads). One broad ad set per market; never blend Auburn-Opelika and Huntsville. Location targeting by the market's real service radius.
- Advantage+ placements unless the data says otherwise.
- All the batch's ads in that one ad set so delivery can pick winners. Upload all ads at once so they share one learning period (playbook `learning_phase`).
- Ad names in Ads Manager exactly match the export filenames (naming convention) so `tools/metrics.py` can group results.
- Budget clears the minimum Ads Manager enforces at publish for the objective and country (reported Nov 2026, playbook `meta_news_2026_11`); a too-small test campaign is refused, not warned.

## Budget sanity check

- Learning needs roughly 50 optimization events per ad set in 7 days. Compute: weekly budget / expected CPL. If that is far below 50, say so and propose the fix: one ad set only, a longer evaluation window, or temporarily optimizing for a more frequent event. Do not pretend the ad set will exit learning.
- Each ad needs enough spend to be judged: at least 2-3x `target_cpl` per ad over the test. If the budget cannot give every ad that, cut the number of live ads.
- Budget changes: batch edits together; large jumps can restart learning. Raising budget about 20% at a time is a common heuristic, not a Meta rule.

## Lead quality

- Instant Form: "Higher intent" type plus qualifying questions (see `reference/copy-package.md`).
- Connect the CRM (config `offer.crm`) so lead stages (qualified, booked, won) flow back to Meta via the Conversions API for CRM. Once volume allows, test the Conversion Leads performance goal (playbook `conversion_leads`), which optimizes for leads that qualify, not just form fills.
- Speed to lead decides cost per booked call more than the ad does: set up instant text/call follow-up before launch.

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

Evaluate an ad only after BOTH a spend threshold and a minimum run time (e.g. 2x target CPL and 3-4 days), whichever comes later. `tools/metrics.py --target-cpl` applies these defaults:

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

Iterate on winners one variable at a time. Never pause or edit live ads without Bruce's approval of the specific change.
