# Playbook changelog

Every `/refresh-playbook` run adds an entry: date, facts re-verified, facts changed (old -> new, with source), facts added or retired.

## 2026-11-05: agentic editor research

Added (sourced in `docs/2026-11-05_agentic-editor-research-and-plan.md`): `hormozi_vibe_editing_ads`
(what Bruce saw: Hormozi's "Get the Free Vibe Editing System" lead-magnet campaign, live since
2026-10-07), `agentic_editing_recipe` (the open-source Claude Code editing consensus the engine now
follows), `captions_sound_off`, `creative_hit_rate`, `creatives_per_adset`, `creative_fatigue`.
Tools changed as a result: new `tools/render.py` (EDL to finished ad), `tools/selects.py`,
`tools/statics.py`; caption styles in `tools/captions.py`; multi-backend `tools/transcribe.py`.
Existing facts were not re-verified in this pass (all still within shelf life).

## 2026-10-22: initial build

Verified all facts in `facts.yaml` against live sources. Corrections to the original master prompt:

- **Reels resolution:** Meta now recommends 1440x2560 (1080x1920 still accepted). Feed recommends 4:5 at 1440x1800, so 1:1 is dropped from the default set.
- **Safe zone confirmed** on Meta's Reels ad guide: top 14%, bottom 35%, sides 6%.
- **Headline length:** Meta recommends 27 characters for Feed, not ~40.
- **Loudness:** -14 LUFS is a social-video convention. Meta does not publish it as a spec.
- **Hold rate:** sources define it differently. The engine now names three separate metrics (see `tools/metrics.py`).
- **Hook rate benchmark:** the largest transparent 2026 dataset puts the median near 21%, not the 25-30% "good" bar many blogs quote.
- **"Entity ID" and the 40%/60% similarity thresholds** are not from Meta. The engine keeps the principle of genuine diversity and drops the numbers.
- **"Max 20% budget change"** is practitioner lore, not a Meta rule.
- **New rules:** audit Advantage+ creative enhancements before publishing, disclose AI content, use Meta Sound Collection or ad-licensed music only, and send CRM lead-quality signals back to Meta (Conversion Leads).
- **Mac tooling:** Homebrew's `ffmpeg` formula was slimmed in January 2026 and no longer includes libass/freetype, so captions and drawtext fail. Use `ffmpeg-full` instead (handled by `tools/setup_mac.sh`).

## 2026-11-23: training pass, 20 YouTube videos (post-Andromeda creative, gurus, AI editors)

Source: `docs/training/meta_ad_creative_training_transcripts.md` (kept local, not in git), read in full in three parts; every adopted rule is credited by video in the reference docs.
- Added `instant_form_disqualify` (low; Ben Heath), `small_budget_fair_test` (low; Sergio C), `protect_working_campaign` (medium; Professor Charley T, Sergio C), `evaluation_window` (medium; Sabri Suby, Charley T), `flexible_ad_322` (low; Charley T).
- Notes added to `creative_similarity` (creative is the targeting: Suby, Cordeddu, Sergio C), `reels_video_specs` (lead-in is the first 7-8 words on Reels), `creatives_per_adset` (Hormozi via Ben Heath says no cap; Charley T's small-account fallback agrees with 4-8; keep 4-8), `creative_fatigue` (frequency never alone; refresh order).
- Rules changed as a result: launch.md (7-day kill window, account-wide step 0, small-budget fair test, batch 2+ side tests, budget step gate, form disqualification), copy-package.md, angles-and-hooks.md, visual-style.md, scripts-and-editing.md, edit-checklist.md, both skills.
- Rejected (do not transfer to a small local lead-gen account, or break compliance): partnership-ad spend targets, zombie campaigns, phantom unbranded pages, faked street interviews, AI investigation ads, press logos, price anchors and BOGO, 20-40 headlines per ad, ROAS scorecards, interest stacking.

## 2026-11-23: November news refresh

- Retired `meta_news_2026_10` (expired 2026-11-21); its October items are summarized in the notes of the new fact.
- Added `meta_news_2026_11` (confidence low, four third-party roundups, not yet confirmed on Meta's pages): per-creative reporting in Ads Manager, Advantage+ Creative Image Animation and Muse Image, enforced minimum budgets at publish, per-creative age and gender with Advantage+ Audience off, on-device Pixel matching on by default, Marketing API v24.0 retired, and a disputed Nov 20 Commercial Terms change on AI-generated creative.
- Lead ads and AI-disclosure searches found nothing new dated November 2026; `conversion_leads` and `ai_content_disclosure` left as they were (within shelf life).
- No rule or tool changed. Launch plan note: confirm the minimum budget per objective before publishing a small test.

## 2026-11-11
- `reels_safe_zone`: re-checked against current secondary guides (14/35/6 unchanged). Added the 40% bottom rule for ads with a disclaimer and the Ads Manager safe zone guardrail preview as the final check. Noted Bruce's audience is about 95% mobile Reels.
