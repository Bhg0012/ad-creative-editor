# Scripts and editing

## Beat structure

| Beat | 15s | 30s | 45s | Purpose |
|---|---|---|---|---|
| Hook | 0-2s | 0-3s | 0-3s | Stop the scroll |
| Problem / tension | 2-5s | 3-8s | 3-10s | Make it about them |
| Mechanism / solution | 5-9s | 8-16s | 10-22s | Show how it works |
| Proof | 9-12s | 16-23s | 22-34s | Make it believable |
| Offer + risk reversal | (merge into CTA) | 23-27s | 34-40s | Make it easy |
| CTA | 12-15s | 27-30s | 40-45s | One clear ask |

Median average watch time on Meta video ads is about 4 seconds (playbook `hook_hold_benchmarks`), so the first 3 seconds carry the ad. Ads over 20s get 2-3 re-hooks (a new visual, a question, a number, a "here's the part nobody tells you") at the points where viewers typically drop: around 3s, 8-10s, and just before the proof.

Script line format:

`[timecode] | VO / dialogue | on-screen text | visual (A-roll / B-roll / graphic / screen rec) | SFX | music cue`

## Visual cadence

- Pattern interrupt every 2-4s in the first 10s (cut, punch-in, B-roll, graphic, text change), then relax slightly. Match the VO's energy; fast is good, chaotic is not.
- Every cut gets a 30 ms audio fade (render.py does it); cut on word boundaries, never inside a word, and leave 0.12 s of air at each tightened pause so breaths do not clip.
- Punch-in zooms of 105-115% on emphasis words; alternate framing so jump cuts look intentional. Do not punch in past the footage's real resolution (soft faces kill trust).
- B-roll and screen recordings show what the VO says ("a text goes out" -> show the phone receiving it).
- Real footage and real client screenshots over stock. No AI-generated people, and nothing synthetic presented as real.
- Speaker's face on screen in the hook and the CTA.
- Final 2-3s: CTA card in brand colors with the exact action ("Tap Learn More") and, if relevant, the local identifier ("Huntsville contractors"). The card's text sits inside the safe zone.

## The EDL is the edit

Every ad is described by `work/edl/<adname>.yaml` (print a template with `tools/render.py --example`). The render engine turns it into a finished file; Bruce's notes are applied by changing the EDL and re-rendering, so nothing is ever re-cut by hand and every version is a small diff. Fields:

| Key | What it does |
|---|---|
| `clips[]` | A-roll in order: `src`, `in`, `out` (seconds in the source); `zoom` (static punch-in, 1.05-1.15), `push` (slow push to this factor), `focus: auto` (face-centered reframe) or `[x, y]`, `tighten: 0.45` (shorten internal pauses longer than 0.45s, leaving 0.12s each side). A still image takes `duration` instead of in/out. |
| `broll[]` | Picture-only overlays: `src`, `at`, `duration`, `src_in`, optional `label` text. The voice keeps playing. Add `pip: {w: 0.7, x: 0.5, y: 0.4}` for a picture-in-picture inset (screenshots, phone photos, HEIC is fine) instead of full frame. |
| `callouts[]` | Short on-screen text mid-video: `text`, `at`, `duration`, `position` (top, center, lower), `accent: true` for the orange box. Use for the number, the re-hook, the offer line. Always labeled "(example)" when the number is not real. |
| `slot` on a clip | A name (`hook`, `offer`, `cta`) that `tools/variants.py` can swap. |
| `look` | Optional light grade for A-roll: `contrast`, `brightness`, `saturation`, `gamma`, `sharpen`. Keep it subtle (1.03-1.08); phone footage is already contrasty. |
| `hook_text`, `hook_text_seconds` | Headline from frame 1, inside the top safe zone, with a dark box. Max about 7 words. |
| `lower_third` | `text`, `at`, `duration`: name + "Auburn, AL" in the accent color, above the caption band. |
| `music` | `src`, `gain_db` (default -18), `duck: true` (sidechain under the voice), `fade_out`. Loops if shorter than the ad. |
| `sfx[]` | `src`, `at`, `gain_db`. |
| `end_card` | `headline` (optional promise line), `text` (the CTA, drawn as an accent pill button), `subtext`, `seconds`, `logo`: brand-primary card with the exact action. |

The output sidecar `exports/<adname>.render.json` lists where every clip, overlay, and graphic landed on the timeline.

## Captions

- Burned in on every ad. Meta calls captions "recommended" and sound "strongly recommended": design for both sound off and sound on.
- Pipeline: `tools/render.py` renders the master, `tools/transcribe.py` transcribes it, `tools/render.py --captions <words.json>` burns the captions. This keeps captions frame-accurate to the final timeline. Fix recurring transcription errors via `captions.fixes` in `config.yaml`, not by hand-editing. For the tightest word timing (karaoke styles) install WhisperX; mlx-whisper is fine for `chunk`.
- Engines: `captions.engine: html` (default) renders word-timed pages in the browser: `pill` (the spoken word sits in an accent pill, the Captions-app look), `highlight` (the spoken word turns accent), `clean` (pages only, one keyword accent). `captions.engine: ass` is the fast libass path with `chunk`, `highlight`, `karaoke`, `reveal`, `hormozi`. Per ad, `caption_style` and `caption_engine` in the EDL override config. No independent study shows one style wins; the mechanism that matters is word-timed, high-contrast, few words per page. Make one variant per batch in a different style and let hook and hold rates decide.
- All styles: heavy sans (Montserrat ExtraBold), white with black outline and shadow, accent `#E55B13`, max 2 lines, positioned above the bottom safe zone.
- Burn in with `ass=<file>.ass:fontsdir=brand/fonts`. Check the ffmpeg log for `fontselect` fallback warnings and look at a frame: if the brand font did not load, libass silently substitutes another font.
- Headline text hook visible on frame 1, not after a fade-in.
- Caption and headline must never overlap each other; move the headline up if needed.

## Safe zones

| Ratio | Keep clear (top / bottom / each side) | Source |
|---|---|---|
| 9:16 | 14% / 35% / 6% | Meta Reels ad guide (playbook `reels_safe_zone`) |
| 4:5, 1:1 | 5% / 20% / 5% | House default; Meta publishes none |

`tools/qa.py` draws these zones in red on sample frames. Nothing important may touch red.

## Motion plates

Every graphic is a motion plate: an HTML template in `tools/plates/` filled from the EDL, rendered frame by frame in headless Chromium with a transparent background (`tools/plates.py`), and composited by `tools/render.py` at its time. All templates share `tools/plates/theme.css` (font, colors, radius, shadow, spring easing), so the look is one system and a restyle is one file. Each plate enters with a spring pop, exits with a short fade, and triggers a sound effect (`graphics.auto_sfx`: pop, click, whoosh, ding, riser from `audio/sfx/` or synthesized defaults).

| EDL key | Plate | Use it for |
|---|---|---|
| `hook_text` | hook card at the top, on from frame 1 | the text hook; `*word*` turns the word accent |
| `callouts[]` | label (dark, light, or `accent: true`) | one number, one re-hook, one offer line; `emoji` optional |
| `plates[] type: stat` | big number counting up, `prefix`, `suffix`, `label` | the one figure that matters |
| `plates[] type: compare` | two growing bars with values, `title`, `left`, `right`, `note` | you vs them, before vs after |
| `plates[] type: card` | title plus up to 5 ticked lines appearing one by one | what they get, the steps |
| `broll[]` still with `pip` | rounded, shadowed inset with slow zoom; `pip.device: phone` adds a bezel; `label` becomes a caption | screenshots, review cards, photos |
| `lower_third` | name tag sliding in (`text: "Bruce, Auburn AL"` splits into name and sub) | the hook only |
| `end_card` | brand background, logo pop, `headline`, pulsing CTA button, `subtext` | the last 2-3 s |
| `captions` (config `captions.engine: html`) | word-timed pages, `pill` (spoken word in an accent pill), `highlight`, or `clean` | every ad |

Positions: `position: top | center | lower` (center means the card's centre at 38% of the frame, above the caption band). Preview every plate on its frame with `tools/render.py <edl> --storyboard` before rendering; one still per type with `tools/plates.py demo --out work/plates_demo`.

Only when a concept needs something these templates cannot do (a chart, a map, a phone mockup with scrolling): add a template to `tools/plates/` following the same structure (theme include, `.in`/`.out` classes, `{{placeholders}}`, the harness script) and register it in `tools/plates.py`. For animated counters, review cards, phone mockups, draw-on arrows, before/after splits, and lower thirds, use Remotion in `graphics/` (Node/React; Remotion's license is free for individuals and companies of up to 3 people; confirm at remotion.dev before using it if AuburnSEO grows past that). Keep one reusable composition per graphic type so later batches reuse them.

- Brand colors `#3B96F6` / `#E55B13`. Motion 150-300ms ease-out. Every graphic readable in under 1 second.
- Stat counters: only real numbers with a source shown.
- Review cards: only real reviews with permission, or labeled "example".
- Lower third: name + "Auburn, AL" for founder trust.
- Never imitate Facebook, Instagram, or Google interface elements so they look like real notifications.

## Sound

- **Voice first:** high-pass ~80 Hz, gentle de-ess, light compression, noise reduction only if needed. It must not sound processed.
- **Music:** only from `audio/music` with an ad-use license on file, or Meta Sound Collection. Never in-app trending music. Energy matches angle (upbeat for opportunity, minimal for pain). Duck under VO by roughly 15-20 dB. Hit a musical change on the CTA if possible.
- **SFX** from `audio/sfx`, sparingly: whoosh on transitions, soft pop on text, ding on "review received" or "phone ringing" moments, riser into the proof. Always below the voice.
- **Loudness:** two-pass `loudnorm` to `audio.target_lufs` and `audio.true_peak_max_dbtp` from `config.yaml`; `tools/qa.py` verifies.
- Silence test (sound off still makes complete sense) and eyes-closed test (sound alone still makes sense).

## Render settings (finals)

`tools/render.py` applies all of this. For ad-hoc work use the ffmpeg at `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`.

```
-c:v libx264 -preset slow -crf 18 -profile:v high -pix_fmt yuv420p -r <source fps, constant>
-c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart
```

Sizes: 9:16 at 1440x2560 when the source is at least 1440 px wide, else 1080x1920. 4:5 at 1440x1800 or 1080x1350. Phone footage is often variable frame rate or HDR: convert to constant frame rate and SDR (`zscale`/`tonemap` or re-export from Photos as SDR) before editing so sync and color hold.

Two-pass loudness (measure, then apply measured values):

```
ffmpeg -i in.mp4 -af loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json -f null -
ffmpeg -i in.mp4 -af loudnorm=I=-14:TP=-1.0:LRA=11:measured_I=..:measured_TP=..:measured_LRA=..:measured_thresh=..:offset=..:linear=true -ar 48000 ...
```

Proxies for review: 540 px wide, CRF 28, with timecode (`drawtext=text='%{pts\:hms}'`).
