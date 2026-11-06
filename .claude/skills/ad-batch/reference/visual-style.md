# Visual style guide (design rules the engine and the editor follow)

AI edits drift toward "busy and generic". These rules pull every ad toward one clean, high-contrast, phone-native look that converts for local trade owners. Sources: the 2026 caption and creative research in `docs/`, Meta's Reels safe zone, and the open-source Claude Code editors reviewed there (video-use, claude-shorts, ghost-editor, HyperFrames caption blocks). Where a rule has no data behind it, it is marked "house".

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
- Text appears instantly (no fade-in) and leaves instantly. Caption words pop at most 8% for 90 ms (`highlight`, `reveal`, `hormozi` styles). No slides, no bounces, no spins.
- B-roll: one insert per idea, 1.5 to 3 s, cut in on the word it illustrates, cut out before the next idea. Picture-in-picture for anything with text (screenshots), full frame for action footage.
- No transitions between A-roll clips (hard cuts). No dissolves except on a still, never on faces.

## Sound

- Voice first, always intelligible with music muted. Music is a bed, 18 to 22 dB under the voice before ducking, ducked a further 10 to 15 dB while speaking.
- Music energy matches the angle: minimal and low for pain and story, mid-tempo for mechanism and proof, lift on the CTA. Nothing with lyrics.
- One SFX per visual event at most (whoosh on a B-roll cut, soft pop on a callout, ding on "review received"). Never on captions.

## First frame rules (the thumbnail that stops the scroll)

- Face sharp and lit, eyes open, mouth not mid-word. Headline already on screen. No logo, no lower third yet.
- Contrast between the subject and the background. If the background is busy, move the speaker, do not add a blur.
- Each concept's first frame differs from every other concept's in shot, setting, or framing (QA checks this).

## What to reject on sight

- Three or more text elements visible at once.
- Any text touching the red safe-zone bands in the QA frames.
- Captions wider than the face band; pages of 5+ words; captions that change faster than 3 per second.
- Zoom past the footage's real resolution (soft face).
- Music audible over consonants; a hard music stop at the end card.
- A stock image, an AI-generated person, an emoji, or a flashing color.
