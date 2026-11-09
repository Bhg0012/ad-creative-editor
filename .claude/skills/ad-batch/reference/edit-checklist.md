# Edit checklist (run on every render before a gate)

What a trained editor checks by reflex. The tools catch most of it; this is the part that needs eyes and judgment. Look at the evidence images in `qa/<ad>/` and the review page, then tick each line.

## Opening (0-3 s)
- [ ] Frame 1 is a usable still: face visible, sharp, not mid-blink, not mid-word mouth shape. If not, nudge `in` by a few frames.
- [ ] Text hook on screen from frame 1 (no fade-in), one or two lines, readable in the 360 px mobile frame.
- [ ] Spoken hook starts within the first 0.3 s of audio; no breath or "um" before it (tighten the `in` point).
- [ ] Opening shot and opening line are different from every other concept in the batch (QA opening diversity).

## Cuts and rhythm
- [ ] Every cut lands on a word boundary or a breath, never inside a word (check caption pages against the timeline).
- [ ] Jump cuts alternate framing (`zoom` 1.0 vs 1.08-1.12) so they read as intentional; no two identical framings back to back.
- [ ] No pause longer than about 0.4 s inside a sentence (use `tighten`); no clipped breaths (keep 0.12 s).
- [ ] A visual change every 2-4 s in the first 10 s; B-roll shows exactly what the voice says at that moment.
- [ ] No B-roll or picture-in-picture covers the speaker's face during the hook or the CTA.
- [ ] QA seam checks clean: no click at a cut, no repeated word across a cut (a surviving retake), no breathy lull over 0.5 s. Fix in the EDL (`tighten`, move the cut, cover with a card), never by hand.
- [ ] Punches (if any) land on the stressed word, at most 3-5 per 30 s.

## Text and graphics
- [ ] Every text element sits inside the safe zone (QA geometry) and is readable at 360 px wide.
- [ ] Captions never overlap the lower third, a callout, or the hook text. Timing of the lower third moved if needed.
- [ ] Caption spelling: brand name, city names and trade words correct (`captions.fixes`), numbers labeled "(example)" unless real.
- [ ] Callouts appear when the word is spoken, not before.
- [ ] Split sections: the speaker band and the stage never swap mid-idea; every stage card is `position: stage`; back to full frame for the CTA.
- [ ] Captions came from the source transcripts (`--captions source`), not a re-transcribed cut; sentiment colours only on words that earn them.
- [ ] End card: exact action ("Tap Learn More"), local identifier if relevant, 2-3 s, brand colors, logo if available.

## Sound
- [ ] Voice clear and consistent across clips (no level jumps between takes; if there are, split the clip and set per-clip gain or re-record).
- [ ] Music under the voice at all times (duck audible), stops or fades on the end card, never a hard stop.
- [ ] SFX below the voice, used sparingly, on a visual event.
- [ ] Loudness within target (QA), true peak at or under -1 dBTP.
- [ ] Sound-off test: the ad makes complete sense muted. Eyes-closed test: the audio alone makes sense.

## Truth and compliance
- [ ] `tools/lint_copy.py` run: no FAIL rows; every WARN resolved or justified at the gate.
- [ ] Compliance checklist in `reference/compliance.md` passed line by line.
- [ ] Message match: video promise, copy, CTA and destination all say the same thing.

## Before the gate
- [ ] Proxy or final watched end to end once at phone size.
- [ ] `exports/<ad>.render.json` matches the EDL (nothing silently skipped).
- [ ] Notes from the previous gate are all applied and logged in `LEARNINGS.md`.
- [ ] Every revision is a new EDL version (`_v2`, `_v3`), never an overwrite; the review page notes carry timestamps ("Stamp time").
- [ ] For every note from the gate, write the evidence row: note, time, which EDL key changed, which rule in the skill should have prevented it.
