# Decisions

Every major creative or strategy decision, with its evidence. One row per decision.

Evidence types: `own-data` (Bruce's ad results), `swipe` (competitor ad seen in Ad Library, with link or screenshot path), `playbook:<fact id>`, `research` (URL + date), `Bruce` (his call at a gate).

Concept type: `new` = a genuinely different concept; `iteration` = a variant of an existing concept (say which).

| Date | Batch | Decision | Concept type | Evidence | Expected effect |
|---|---|---|---|---|---|
| 2026-11-05 | (engine) | Build the editor as EDL yaml + ffmpeg render (tools/render.py) with ASS caption styles, instead of Remotion-first or a hosted render API. Remotion stays optional for motion graphics. | new | research (docs/2026-11-05_agentic-editor-research-and-plan.md); playbook:agentic_editing_recipe | Every revision is a small diff to the EDL; renders are free, local, and reproducible; one EDL yields 9:16 and 4:5. |
| 2026-11-23 | (engine) | Not adopting Eddie AI (paid MCP editor, credits per hour of footage) after reading its Claude guide; built its three transferable ideas free and local instead: timeline export to Premiere, Resolve and Final Cut (`tools/export_timeline.py`), topic search across transcripts (`tools/find.py`), filler and repeat removal (`tools/fillers.py`, `captions.drop_fillers`). | new | research (https://www.heyeddie.ai/learn/eddie/how-to-edit-video-with-claude, read 2026-11-23); Bruce | Every cut can be finished by hand in an NLE; interview footage can be mined by topic; ums never reach the ad. No per-hour cost. |
| 2026-11-23 | (engine) | At Bruce's budget, run few data buckets: produce 5-6 concepts, run 4-8 live ads or a few flexible 3-2-2 ads, keep the rest for side tests. Volume grows with budget. | new | research (Sergio C V15, Professor Charley T V14 vs Ben Heath V12, Sabri Suby V13; brand/DESIGN.md training library); playbook:small_budget_fair_test | Each live ad gets enough spend to be judged; no starved winners. |
| 2026-11-23 | (engine) | Kill and crown only after 7 days on 7-day rolling numbers, after an account-wide CPM and CTR check; frequency never judged alone. | new | research (Sabri Suby V13, Professor Charley T V14); playbook:evaluation_window, creative_fatigue | Fewer false kills on small samples and seasonal swings. |
| 2026-11-23 | (engine) | Instant Forms route clear non-fits to a closing screen and verify phones; report cost per qualified lead. | new | research (Ben Heath V12); playbook:instant_form_disqualify | Meta stops optimizing toward junk leads; slower learning accepted only for clear non-fits. |
| 2026-11-23 | (engine) | A fresh-eyes subagent with no edit history reviews every cut from a review pack before Bruce sees it; a session log records dead ends. | new | research (Mr. Paid Social V17 second-model QA and session logs, free version with Claude) | Fewer defects reach Bruce; repeated mistakes drop. |
