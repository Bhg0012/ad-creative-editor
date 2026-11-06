# Design notes from references

What the references Bruce likes have in common, and what the engine adopted. Updated whenever a
file lands in `brand/references/`. Media is not in git; the notes are.

## Reference 1 (2026-11-06): creator ad for an AI short-form editor, 30 s, 9:16, Instagram

Measured: 30.3 s, one real cut (at 20.5 s), -14.4 LUFS integrated, loudness range 4 LU (very even).
Visual change arrives every 1 to 1.5 s from the screen content, not from cuts.

What it does:
- **The screen is the set.** A dark product UI fills the frame; the presenter sits bottom right, head and
  shoulders, mic in hand, cut out from his background, same position for 20 s. The UI itself changes
  (progress 4% to 99%, panels, a phone mockup) and that is the pattern interrupt. Last 10 s: a bright
  white web page with the presenter in the same spot. Two "sets" total.
- **Captions:** ALL CAPS, one line, 3 to 4 words per page, condensed heavy sans, white with a thin black
  stroke and a drop shadow, placed at about 62% of the frame height. One word per page sits in a solid
  red-orange box with a small corner radius. No pill, no bounce.
- **Hook:** no separate hook card. The first frame is the product's own title block ("Raw clip in.
  Finished short out." with an italic serif accent) with the first caption page over the presenter.
- **Graphics:** almost none beyond the UI. No lower third, no logo, no animated cards. One accent color.
- **CTA:** the destination page itself on screen for the last third, presenter pointing at it.
- **Sound:** voice only, tightly compressed, no audible music bed.

Adopted:
- Caption style `box` (`captions.style: box`): ALL CAPS, 3 to 4 words, key word in a solid accent box
  with a small radius, stroke plus shadow. `captions.font_name` can point at a condensed face in
  `brand/fonts/` (Anton or Bebas Neue, both Open Font License) when a batch wants that look.
- `speaker_inset` on a B-roll entry: the screen recording or screenshot fills the frame and the speaker
  stays in a rounded, shadowed inset in a corner, taken from the A-roll so lip sync is untouched.
  Default 40% wide, lower right, bottom edge 10% off the frame bottom, so the face sits near 60% height
  and captions overlap the inset's lower left the way the reference does.
- Rounded corners and a soft shadow on every video inset (no hard white border).
- Rule for the beat map: when the mechanism is a screen, let the screen be the set for that beat and
  keep the speaker in the inset; change what is on the screen every 1 to 2 s instead of cutting.

Not adopted:
- Background removal of the presenter (would need a matting model; a rounded inset gets most of the
  effect without the halo risk). Revisit if two more references do it.
- Dropping the hook card. For cold local traffic the text hook on frame 1 still earns its place; the
  reference is for a warm audience that knows the presenter.
