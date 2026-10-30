---
name: refresh-playbook
description: Re-verify the Meta ads playbook (playbook/facts.yaml) against live sources so specs, policies, algorithm guidance, benchmarks, and creative trends stay current. Use when tools/doctor.py reports expired facts, before starting a new ad batch if the last refresh was over 30 days ago, when Bruce asks what is new or trending in Meta ads, or on a scheduled monthly refresh.
---

# Refresh the playbook

The playbook is only useful if it is true today. This skill re-checks it against live sources, updates it, and records what changed.

## Steps

1. Run `.venv/bin/python tools/doctor.py` and note expired facts. Refresh those first, then every fact with `confidence: low` or `topic: news`, then the rest if time allows.
2. For each fact, find the **best current source**:
   - Specs, safe zones, policies: Meta's own pages first (facebook.com/business/ads-guide, facebook.com/business/help, transparency.meta.com, developers.facebook.com). Fetch the page itself; do not rely on a blog's summary of it.
   - Algorithm and creative strategy: at least 2 independent practitioner sources from the last 90 days, preferring ones with disclosed data. If a claim traces back to a single blog, mark `confidence: low`.
   - Benchmarks: only sources that state sample size, date range, and definitions. Note when the sample is not local services.
3. Update the fact in `playbook/facts.yaml`:
   - Unchanged and confirmed: update `verified_on` to today only.
   - Changed: rewrite `claim`, update `sources`, `verified_on`, `confidence`, and add a note on what changed.
   - Could not verify: leave `verified_on` as is (it stays expired) and add a note saying what was tried. Never extend a date without a source.
   - No longer true: remove it and record the retirement in the changelog.
4. **Scan for what is new.** Search for Meta ads changes in the last 30-60 days (creative tools, Advantage+ defaults, lead ads, policy, Ads Manager metrics, delivery) and for current creative trends in local-service and B2B-to-small-business ads. Add new facts with every field filled (`id`, `topic`, `claim`, `sources`, `verified_on`, `shelf_life_days`, `confidence`, `applies_as`, optional `notes`).
5. **Propagate.** If a change affects a rule the engine uses (safe zones, specs, loudness, compliance, launch settings), update the matching place too: `tools/common.py` (`SAFE_ZONES`, `RESOLUTIONS`), `config.yaml` defaults, or `.claude/skills/ad-batch/reference/*.md`. Run `.venv/bin/python -m pytest -q` after any tool change.
6. Add a dated entry at the top of `playbook/CHANGELOG.md`: facts re-verified, facts changed (old -> new, with source), added, retired, and any rule or tool updated as a result.
7. Report to Bruce: the 3-5 changes that matter most for his next batch, in plain words.

## Rules

- Source and date on everything. Blog claims are hints until confirmed.
- Quote Meta's exact numbers; do not round them in the claim (round only in derived pixel values, always rounding up for keep-clear margins).
- No em dashes in any file.
- If this runs unattended (scheduled), commit the playbook changes on a branch and leave the summary as the commit message; do not change tools or skill files unattended, list proposed changes instead.
