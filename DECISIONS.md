# Decisions

Every major creative or strategy decision, with its evidence. One row per decision.

Evidence types: `own-data` (Bruce's ad results), `swipe` (competitor ad seen in Ad Library, with link or screenshot path), `playbook:<fact id>`, `research` (URL + date), `Bruce` (his call at a gate).

Concept type: `new` = a genuinely different concept; `iteration` = a variant of an existing concept (say which).

| Date | Batch | Decision | Concept type | Evidence | Expected effect |
|---|---|---|---|---|---|
| 2026-11-05 | (engine) | Build the editor as EDL yaml + ffmpeg render (tools/render.py) with ASS caption styles, instead of Remotion-first or a hosted render API. Remotion stays optional for motion graphics. | new | research (docs/2026-11-05_agentic-editor-research-and-plan.md); playbook:agentic_editing_recipe | Every revision is a small diff to the EDL; renders are free, local, and reproducible; one EDL yields 9:16 and 4:5. |
