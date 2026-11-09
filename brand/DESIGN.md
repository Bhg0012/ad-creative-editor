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

## Reference 2 (2026-11-09): "Claude edited this whole video", 98 s, 9:16, Instagram

Measured: 98 s, 19 real cuts (median shot 3.7 s), but a visible change about every 0.3 s in the first
minute, -14.1 LUFS, loudness range 4.4 LU.

What it does:
- **Hook (0-3 s):** presenter full frame, two-line ALL CAPS headline in a white box with black text,
  upper third. No other graphic.
- **Meta-shot:** most of the video is the presenter's own monitor filmed handheld with a phone, showing his
  edited reel playing inside a review app. The handheld drift is what makes the frame move every 0.3 s.
  That is a filming choice (record your screen with the phone instead of a screen capture), not an edit.
- **Graphics inside the reel, one per idea, 2-4 s each, all on the same dark-card system with one orange:**
  numbered step pills ("03 GIVE IT A STYLE"); big counters with commas and thumbnails under them
  ("4,095,186 VIEWS"); a grid of frame thumbnails with a count headline ("20 CUTS FOUND"); a before/after
  with a red "DEAD SPACE" pill, a green waveform and "12.5s -> 4.9s" struck through; percentage stat
  cards with screenshots; word-box labels ("THE MOTION GRAPHICS", each word in a white box, one orange);
  a chip grid of sound names; a card titled "ElevenLabs - Music"; screenshots and repo pages with a
  highlight; corner brackets with a "RAW FOOTAGE" tag and a running timecode.
- **Captions:** only the white-box hook; the graphics carry the text after that.
- **Sound:** a pop or click on every graphic; music bed low; voice compressed.

Adopted (all in `tools/plates/`, usable from the EDL `plates:` list):
- `step` (number pill), `grid` (thumbnails pulled from a clip plus "N cuts found" style headline),
  `before_after` (pill label, waveform, struck-through old value, green new value), `chips` (grid of
  short words with sub-labels), `frame_label` (corner brackets, REC dot, timecode), `label` with
  `variant: boxes` (each word boxed, `*word*` in accent), `stat` now counts up with thousands separators
  and takes `thumbs`, hook takes `hook_variant: light` and `hook_uppercase: true`.
- `tools/capture.py`: screenshots or scroll-through videos of web pages (your site, a Google Business
  Profile, a review page) as B-roll, phone or desktop viewport.
- Shot list note: filming your own screen with the phone is a legitimate B-roll technique; the engine
  treats it as A-roll or B-roll like any clip.
- Sound effects set extended with thud, swipe, sub.

Not adopted: generative music (bring a licensed bed; the engine ducks whatever you give it).

## Reference 3 (2026-11-09): "Claude Code edited this entire video", 82 s, 9:16

Measured by eye and by `tools/reference.py`: 82 s, 16 hard cuts (median shot about 5 s), but the frame
changes every 0.4 to 0.8 s because the graphics stage keeps moving while the speaker holds still.

What it does:
- **Framing grammar:** the speaker is not full frame. He sits in a band across the bottom 40-45% of the
  frame; the top 55-60% is a dark navy "stage" with a faint grid and a soft brand glow. Graphics live on
  the stage, never on his face, so nothing ever covers the mouth and captions never fight a card.
- **Stage graphics, one per idea:** numbered cards ("01 Scripting", "02 Editing"), wireframe-style
  diagrams (boxes and arrows for the sub-agent fan-out), a single giant word or number that takes the
  whole frame for a beat ("600 million tokens"), a struck-through list with the real answer below it, a
  thin progress bar across the top for the whole video, screenshots with a stamp ("LIVE", "RAW") and a
  highlighted band over the line that matters, waveform annotations for "dead space".
- **Captions:** one to two words per page, large, white, the spoken word in a pill; pain and cost words in
  red, win words in green. No ALL CAPS.
- **Motion:** quick 1.07x punches on key words (zoom in over about 0.15 s, back over 0.35 s), no whooshes;
  a soft pop or click per graphic, a low thud under the full-frame takeover.
- **Sound:** music bed low, voice clean, no music hit on the end card.

Adopted (all usable from the EDL, see `scripts-and-editing.md`):
- `layout: split` on any clip: the speaker drops into the bottom band over a brand `backdrop` plate and
  graphics with `position: stage` land centred in the open stage above him.
- `progress_bar: true`: a thin brand-gradient bar across the top for the whole ad (a retention device
  that tells the viewer the ad is short).
- `punches: [t, t]`: quick zoom punches on key-word times.
- Plates `takeover` (one giant word or number, full frame, with a sub line), `strike` (list struck
  through one by one, then the answer), `progress`, `backdrop`; `pip` stills take `stamp` ("LIVE") and
  `highlight: {x, y, w, h}` for a highlighted band over a screenshot line.
- Caption sentiment: `captions.keywords_neg` (red) and `captions.keywords_pos` (green) in `config.yaml`
  or per EDL (`caption_keywords_neg/pos`).
- Whooshes removed from the default entrance sounds; pops and clicks only, thud for the takeover.

Not adopted: his cards are up 4-6 s because the video is 82 s long; in a 30-45 s ad a stage card is up
2-3 s. Keep the one-graphic-per-idea rule from reference 2.

## Lessons from the mrpaidsocial "video editor agent" repo (2026-11-09)

Read in full (README, ARCHITECTURE, skills for pipeline, branded edit, QA, image overlays, reel recut,
EDL tightening, sound design, style clone, variants, hook variations). What moved into this engine:

| Repo practice | Here | Why |
|---|---|---|
| Caption the SOURCE transcript through the cut, never re-whisper the cut | `tools/render.py <edl> --captions source` maps the raw takes' `words.json` through the clip map | Whisper on a concatenated cut drifts late and merges retakes; the source timings are exact |
| Transcribe multi-take raws per pause-separated take | `tools/transcribe.py --split` | Continuous audio hides the stumble between two attempts at the same line |
| Butt-splice click check and repeated-word check at every seam | `tools/qa.py`: "no clicks at cuts", "no repeated words across cuts" | The two most common tells of a machine cut |
| RMS lull scan under the silence threshold | `tools/qa.py`: "no breathy lulls over 0.5s" | Breathy -30 dB stretches pass silencedetect and still read as dead air |
| Framing grammar (speaker panel plus graphics stage) | `layout: split`, `position: stage`, `backdrop` plate | Graphics never touch the face; the stage is a designed space, not a sticker on footage |
| Zoom punches, progress bar, takeover, strike, stamp, highlight | EDL keys and plates above | The retention devices that make a talking head feel edited |
| Sentiment caption colours | `keywords_neg` red, `keywords_pos` green | One more layer of meaning without more words |
| Whoosh only when something crosses the frame | `ENTRANCE_SFX` map: pops, clicks, thud | Whooshes on pops are the loudest "AI edit" tell |
| Timestamped review notes | `tools/review.py` "Stamp time" button drops the player time into the notes box | Notes land as "12.4s: card too late", which maps straight to an EDL change |
| Short GOP on drafts | proxies render with a 1 s keyframe interval | Scrubbing a draft in the review page is frame-accurate |
| Measure references as numbers | `tools/reference.py` writes cuts, change events per second by hook/body/CTA, loudness, music-bed guess, sheets and frames | "Copy the style" becomes a spec, not a vibe |
| Every revision is a new file, never overwrite | EDL versions `_v2`, `_v3` and exports keep their name | You can go back, and QA can diff |

Deliberately not adopted: HyperFrames or Remotion as a dependency (our HTML plates already render in the
same headless Chromium with zero Node), ElevenLabs music and voice (bring licensed audio, the engine
ducks it), a web canvas editor, CapCut export, AI-generated B-roll (compliance and the "no inkling this
is AI" brief), AVFoundation probing (ffprobe does it everywhere).
