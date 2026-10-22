# Playbook changelog

Every `/refresh-playbook` run adds an entry: date, facts re-verified, facts changed (old -> new, with source), facts added or retired.

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
