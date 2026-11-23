# Visual style guide (design rules the engine and the editor follow)

AI edits drift toward "busy and generic". These rules pull every ad toward one clean, high-contrast, phone-native look that converts for local trade owners. Sources: the 2026 caption and creative research in `docs/`, Meta's Reels safe zone, and the open-source Claude Code editors reviewed there (video-use, claude-shorts, ghost-editor, HyperFrames caption blocks). Where a rule has no data behind it, it is marked "house".

## Safe zones first (Bruce's standing rule, 2026-11-17)

About 95% of the audience watches on a phone, on Facebook and Instagram Reels, where the app's own buttons, caption and profile bar sit on top of the video. Every graphic, caption, headline and CTA lives inside the clear area (9:16: top 14%, bottom 35%, 6% each side; `playbook/facts.yaml` `reels_safe_zone`). The engine places things there by construction and QA fails anything that crosses the line. This matters most on ads; a pre-sale or long-form video after the click can be looser (16:9 has its own lighter zone).

## One look per batch

- Native, not produced: phone footage, natural light, real locations (truck, job site, office, kitchen table). No stock, no gradients behind the speaker, no stock-style icons.
- One typeface (Montserrat ExtraBold for everything on screen; Black for a single shouted hook word at most). Never mix fonts inside an ad.
- Two colors plus white and black: primary `#3B96F6` for the end card, accent `#E55B13` for the one word that matters, the CTA button and the lower third. Nothing else colored. Yellow Hormozi captions are a variant, not the default (house).
- One visual idea per frame: a face, or a screenshot, or a callout. Not a face plus a callout plus a label plus a logo.

## Hierarchy inside the frame (9:16)

| Band | Height | What lives there |
|---|---|---|
| Top safe zone | 0 to 14% | nothing (Reels UI) |
| Headline band | 14% to 28% | hook text, then B-roll labels and top callouts |
| Face band | 28% to 55% | the speaker's eyes at about 40% height (`focus` keeps them there) |
| Mid band | 42% to 50% | center callouts, picture-in-picture top edge |
| Lower third | 50% to 55% | name tag, only during the hook |
| Caption band | 55% to 65% | captions, baseline above the bottom safe zone |
| Bottom safe zone | 65% to 100% | nothing (Reels UI, CTA sheet) |

4:5 Feed keeps the same order with smaller safe zones (5% top, 20% bottom).

## Type

- Captions: 4.2% of frame height (about 80 px at 1920), 2 to 4 words per page, max 2 lines, white, 3 to 4 px dark outline, soft shadow. One accent word per page: a number, the city, the trade, the pain word, the outcome word. Sentence case by default; ALL CAPS only in the `hormozi` variant.
- Hook headline: 4.6% of frame height, max 7 words, 1 to 2 lines, white on a 60% black box. It must read in one glance at 360 px wide. If it needs three lines, it is too long.
- Callouts: 5% of frame height, max 4 words, accent box for the number or the offer, dark box for everything else. On screen only while the words are being said (1.5 to 2.5 s).
- Lower third: 2.8% of frame height, name plus "Auburn, AL", accent box, 2 to 3 s during the hook only.
- End card: CTA in a pill button (accent), one supporting line, optional promise headline above. Nothing else.
- Numbers always read as numerals ("140", "$4,800"), never spelled out, and labeled "(example)" unless real.

## Motion

- Cuts are the motion. Jump cuts on word boundaries every 2 to 4 s in the first 10 s, then every 3 to 6 s.
- Punch-in alternation between 1.0 and 1.08 to 1.12. A push (`push`) only on stills and proof screenshots, 1.08 to 1.12 over the clip's length.
- Graphics enter with one spring pop (380 ms, slight overshoot) and leave with a short fade (250 ms); the hook card is the exception and is simply on from frame 1. Captions pop at most 6% per word. No slides across the frame, no spins, no bounces after the first settle.
- Cards are rounded (28 px at 1920 tall), dark at 86% over footage, with one soft shadow. Accent only for the one card that carries the number or the offer.
- B-roll: one insert per idea, 1.5 to 3 s, cut in on the word it illustrates, cut out before the next idea. Picture-in-picture for anything with text (screenshots), full frame for action footage.
- No transitions between A-roll clips (hard cuts). No dissolves except on a still, never on faces.
- Framing grammar: full frame for the hook and the CTA (the face sells); `layout: split` for the mechanism and proof, where the speaker holds the bottom band and every card lands on the stage above him. Never put a card on a full-frame face when a split would do.
- Card archetypes, one per idea: `label` for a line, `stat` for a number, `compare` for you vs them, `card` for a list, `step` for the sequence, `takeover` for the one number or word that is the ad, `strike` for what they tried before, `before_after` for a change, `grid` for "look how many", `pip` with `stamp` and `highlight` for a screenshot where one line matters. Pick by the idea, not by what looks cool.
- Punches (`punches`) on at most 3-5 key words per 30 s, on the stressed syllable. Not on every sentence.

## The light look (when the batch wants "cute, fun, modern" instead of dark cards)

One look per batch still holds; this is the second look available, from reference 4 in `brand/DESIGN.md`.
- Hook: `hook_variant: clean` with a kicker and a sub line, no box.
- Captions: `caption_style: word`, `caption_position: high`. One word, soft shadow, above the head after the hook.
- Graphics: floating cutouts (`pip: {style: cutout, float: true}`) of real objects from the trade, square image cards, `words` on cream paper, `toast` for a notice, `takeover` with `bg: none` for the one word at the CTA.
- Grade: `look: {temperature: 5200, vignette: 0.35}` on dim indoor footage; skip it outdoors.
- Still one graphic per idea, still 2-3 s each, still a low music bed. The cute comes from warmth, pastels and the bob, not from more things on screen.

## The studio look (dark stage, glowing panel)

The third look, from reference 5 in `brand/DESIGN.md`. Use it when the batch is mechanism-heavy and the graphics carry the argument.
- `layout: split` on the body clips with `split: {style: panel}`; `caption_position: mid`; hook and CTA full frame.
- Stage graphics by idea: `fan` for "look how many", `steps` for the mechanism in order, `timer` for the old way's cost, `tracks` for "the part you see", `quote` for a real review, `files` for years of work, `pip` with a phone or browser frame for a screen.
- A full-frame cutaway from a second angle or room every 10-15 s so the panel never feels static.
- Still one graphic per idea, 2-3 s each, a low bed, pops and clicks only.

## Sound

- Voice first, always intelligible with music muted. Music is a bed set 20 LU under the measured voice (`audio.music_under_voice_lu`), with an EQ dip in the voice band (Gavin Herman, V6), then ducked a further 10 to 15 dB while speaking. Optional: a suspense bed under the hook, then the main bed (`music:` sections; Christian Peverelli, V18).
- Music energy matches the angle: minimal and low for pain and story, mid-tempo for mechanism and proof, lift on the CTA. Nothing with lyrics.
- One SFX per visual event at most (soft pop or click on a card, thud on a takeover, ding on "review received"). A whoosh only when something crosses the frame. Never on captions.
- The SFX peak lands on the graphic's visual peak (Gavin Herman, V6). A first draft that is "a little too busy" loses sounds, it does not gain them (Christian Peverelli, V18).

## Static ads

Statics are the cheap test bed for big ideas (Sabri Suby, V3; Dara Denney, V1 and V4). Every rule here is checked at 360 px wide.

- **Hierarchy:** the hook is the largest element, then the qualifier (trade and city), then the offer or what it is, then the proof. People scan, they do not read top to bottom (Alex Cooper, V11; Dara Denney, V4). Control it with size, contrast and white space.
- **One-second test:** a stranger knows what it is about in one second, or it is cut. Clarity beats creativity (Dara Denney, V4).
- **Headline on two lines,** broken on word boundaries, with one key word highlighted (the red `keywords_neg` color on a pain word, the accent on an outcome) (Alex Cooper, V11).
- **Limits:** at most 3 text elements, at most 2 stacked concepts, one focal point. Less is more; review collages and walls of text fail (Dara Denney, V4). Alessio Cordeddu's stacking (V5) is capped at 2 here.
- **One job per static:** pick one goal (Dara Denney, V4).
- **Templates** (`tools/statics.py --template`): `headliner` (one giant claim), `problem` (problem in personal words top half, image bottom half), `question` (a direct question that self-selects), `mythbuster` ("It's not X, it's Y"), `versus` (two columns against doing nothing or asking by hand, never a named competitor), `listicle` (3 reasons is the sweet spot, 5 max, the answer at the bottom), `howitworks` (3 numbered steps of one mechanism), `quote` (a real customer line as the headline, texting tone, unpolished, permission on file), `postit` (handwritten note over a real photo), `letter` (a short founder letter, text only), `lofi` (Bruce's raw phone photo with no overlay at all, carried by a long story in the primary text: Sabri Suby's "if I had to run one single ad", V13). Sources: Alessio Cordeddu, V5; Alex Cooper, V11; Dara Denney, V4.
- **Atypical text, done for real:** "9 reviews?" written in the dust on a truck window or on a job-site whiteboard, photographed (local inference from Alex Cooper's "make the invisible visible", V11; his examples are AI, ours are real).
- Real screenshots of Google profiles only with permission. Never a fabricated review, notes-app mockup or platform UI (compliance; Dara Denney ranks notes-app ads F tier anyway, V9).

## Do not drift into the polished middle

Sabri Suby's barbell (V13): raw native content on one end, big productions on the other, and most ads die in the polished middle. Bruce's raw founder footage is the raw end. The motion-graphics layer must make that footage clearer, never turn it into a glossy brand ad. The default "voiceover plus B-roll problem-solution" cut is a known fatigued look (Dara Denney, V2 and V9); every batch carries at least one story or investigation concept (`angles-and-hooks.md`).

## First frame rules (the thumbnail that stops the scroll)

- Face sharp and lit, eyes open, mouth not mid-word. Headline already on screen. No logo, no lower third yet.
- Contrast between the subject and the background. If the background is busy, move the speaker, do not add a blur.
- Each concept's first frame differs from every other concept's in shot, setting, or framing (QA checks this).
- A generic text-post card (`post` plate) as frame 1 still works as a hook (Dara Denney, V9). Real line or clearly hypothetical, no platform branding.

## What to reject on sight

- Three or more text elements visible at once.
- Any text touching the red safe-zone bands in the QA frames.
- Captions wider than the face band; pages of 5+ words; captions that change faster than 3 per second.
- A whoosh on a pop, a graphic over a mouth, a repeated word across a cut, a breathy lull longer half a second: the four tells of a machine cut. QA flags all four; fix them in the EDL.
- Zoom past the footage's real resolution (soft face).
- Music audible over consonants; a hard music stop at the end card.
- A stock image, an AI-generated person, an emoji, or a flashing color.
