# Angles and hooks

## Angle families

Pick 5-6 angles per batch from at least 4 different families. Examples are for a review-generation offer; adapt to the real offer.

| Family | Example | Notes |
|---|---|---|
| Problem / pain agitation | "You did the best job on the street. Your competitor has 140 reviews. You have 9." | Numbers must be real for the viewer's market or clearly framed as an example. |
| Lost money math | "Every customer who picks the other guy because of reviews costs you a $X job." | Real figures, or labeled "example" on screen. |
| Mechanism / how it works | Show the actual text request going out and the review landing. | Strong for solution-aware, skeptical markets. |
| Local proof / case study | Real client, real screenshot, real result. | Only with written permission. Strongest angle when available. |
| Founder story / trust | "I'm a student at Auburn, I live here, here's why I built this." | Lean into local and accountable; never overstate experience. |
| Comparison / us vs them | vs big agencies, vs doing nothing, vs asking for reviews manually. | Never name or disparage a real competitor. |
| Objection crusher | Lead with the #1 objection and kill it ("I get all my work from word of mouth."). | Use their exact words from ICP research. |
| Curiosity / pattern interrupt | Unexpected visual or statement that demands the next second. | Must pay off within the ad; no bait. |
| Demo / screen recording | Phone screen showing it working in real time. | Real account or a clearly labeled demo account. |
| Before / after | Google profile before vs after (real client with permission). | Strong as a static too. |

## Concept rules (training pass, 2026-11-23)

- **Big idea in one sentence.** Every concept states its big idea in one sentence before anything is scripted, so it can be judged and later ported to other formats (Dara Denney, V1).
- **Hello and close.** Label each concept "hello" (cold: problem, curiosity, story, education) or "close" (offer, objection, earned urgency, real proof). Aim for about 3 hello and 1-2 close per batch. Close concepts work well as statics (Professor Charley T, V14; Alex Cooper, V11).
- **Awareness coverage.** Every batch includes at least one unaware or problem-aware concept; most accounts starve the top of the funnel (Dara Denney, V2).
- **One non-PAS concept per batch.** At least one concept is a personal story or an investigation, not problem-agitate-solution. Polished VO plus B-roll problem-solution reads as an ad and is fatigued (Dara Denney, V2 and V9). PAS stays the default beat structure (Alessio Cordeddu, V8).
- **Validate cheap first.** An expensive concept (a client shoot, a location day) is tested first as a static or a Bruce-to-camera take (Dara Denney, V1).

## Format templates

Pick by the concept's job, not by what looks new. Each needs real footage and real proof; nothing synthetic presented as real.

| Format | What it is | Notes |
|---|---|---|
| Personal-history yapper | Bruce opens on a true first-person story, then ties it to the offer | Scaling format in Sep 2026 (Dara Denney, V2). Story first, product last. |
| Amateur investigation | Bruce searches "roofer near me Auburn AL" on his phone (screen-recorded with `tools/capture.py` or the phone) and shows what the top map-pack profiles have | No competitor named or disparaged. V2's version uses AI; ours does not. |
| David vs Goliath | Local owner-operator against national lead sellers and franchises, as a category | Never name a real company (Dara Denney, V9). |
| Green-screen commentary | `speaker_inset` over a capture of a profile, a search result or a review page | Dara Denney, V9. |
| Challenging beliefs | Takes on "word of mouth is enough" | Needs good B-roll and the persona's real limiting belief (Dara Denney, V9). |
| Objection handling | The top objection from sales calls, answered | Mid-funnel; strong as a close concept (Sabri Suby, V3; Dara Denney, V9). |
| Comment reply | Answers a real comment on a live ad | Real comment, permission, generic card (`quote` plate), never a copy of the platform UI. |
| Short 9:16 VSL | 45-60 s education for a cold audience that needs the mechanism explained | S tier for "anything that needs a lot of upfront education" (Dara Denney, V9). |

## Hook types

Use a mix across the batch: call-out ("Huntsville roofers..."), bold claim (provable), question, negative/warning ("Stop asking customers for reviews like this"), number/list, story open ("Last week a homeowner picked my client over..."), visual demo, contrarian, before/after.

## Hook templates

Hook type slugs go in the ad name's `hooktype` part so `tools/metrics.py` groups results by them. Local examples use the trade and city and never an invented result.

| Template (slug) | Funnel | Visual / audible / text | Local example | Source |
|---|---|---|---|---|
| Trigger word (`trigger`) | TOF | Text and VO carry an emotionally loaded phrase dropped into a hook structure that already won | "Losing jobs to the guy with more stars?" | Dara Denney, V7 |
| Why it matters (`why`) | MOF | VO and text question on the biggest value; native talking head | "Why do Auburn homeowners pick the roofer with more reviews?" | Dara Denney, V7 |
| A day without (`daywithout`) | TOF | Leads with the after state, not the problem; shows the calm version | "A week where the phone rings without you asking." | Dara Denney, V7 |
| How to know if (`howtoknow`) | TOF, problem-aware | VO and text | "How to know if your Google profile is costing you jobs" | Dara Denney, V7 |
| How to pick (`howtopick`) | Decision stage | VO and text | "How to pick who handles your reviews" | Dara Denney, V7 |
| How to start (`howtostart`) | Any stage; strong for service businesses | VO and text | "How to start getting reviews without asking twice" | Dara Denney, V7 |
| If you (`ifyou`) | TOF / MOF | Call-out by trade and place | "If you run a roofing crew in Opelika..." | Dara Denney, V7 |
| This one thing (`onething`) | TOF / MOF | Promises one simple fix | "One text after every job. That's it." | Dara Denney, V7 |
| Sorry / you're welcome (`sorry`) | BOF | Only with a real reason (a real deadline, a real limit) | none until a real reason exists | Dara Denney, V7 ("a cheap trick") |
| Most X isn't X (`mostxisnt`) | TOF | VO sets up a reframe the whole ad pays off | "Most 'marketing' for roofers isn't marketing anymore." | Fraser Cottrell, V10 |
| N truths (`truths`) | TOF | Listicle promise; body numbered with `step` plates | "3 truths about Google reviews every Auburn plumber should know" | Fraser Cottrell, V10 |
| Not your regular X (`notregular`) | MOF | Curiosity action in the first second (reaching into the truck, pulling out the phone), 0.5x walking shot | "This isn't your regular marketing guy." | Fraser Cottrell, V10 |
| I tried X (`tried`) | MOF | Doing it, then the close-up of the result | Only with real data from Bruce's own test | Fraser Cottrell, V10 |
| Offer first (`offerfirst`) | BOF | First frame states the real offer, close to camera | Only once the offer fields in `config.yaml` are filled | Fraser Cottrell, V10 |
| Whisper take (`whisper`) | Iteration | The winning hook line re-recorded as a whisper | Same line as the winner, whispered | Dara Denney, V7 (her clients' best-converting VO test) |
| Filter take (`filter`) | Iteration | Same hook with a native face filter, behind-the-scenes feel | Use only on a proven winner | Dara Denney, V7 |

Hook rates quoted in the videos (45%+ in V7, 77% in V2) are top performers from those creators' accounts, not targets; the playbook median is about 21% (`hook_hold_benchmarks`).

**Hook tests.** A hook variant is one variable, but it must be a big swing: a new opening shot and a new line, never a one-word swap (Dara Denney, V7). Test 3-6 hooks per hero when the budget allows, 2-3 at Bruce's budget.

**Hook payoff.** A hook that promises structure ("3 truths", "one thing") must structure the body (numbered `step` plates double as re-hooks) and pay off before the CTA. The hook sets up the rest of the video; it is not glued onto the front (Fraser Cottrell, V10).

**Three checks before a hook ships** (Sabri Suby, V13): does it interrupt the pattern; does it open a curiosity loop; does it carry a hyper-specific benefit the trade owner wants. Curiosity must pay off inside the ad, or it attracts everyone and the wrong people.

## Three layers, all synced

- **Visual hook (0-1.5s):** what is on screen in frame one. It must work with sound off and before the viewer reads anything. Different shot, location, framing, or prop from every other concept in the batch.
- **Text hook:** max ~7 words, on screen from frame 1 (no fade-in), inside the safe zone.
- **Spoken hook:** first sentence, under ~2 seconds to say.
- **The vibe** is the fourth layer: what the whole package says about who it is for (Dara Denney, V7). Fraser Cottrell (V10) has strategists brief the visual, audible and text hook separately; do the same in `brief/07_hooks.md`.
- **Creative is the targeting.** Casting, setting (truck, job site, office), the opening problem and the tone tell Meta who the ad is for (Alessio Cordeddu, V8; Sabri Suby, V3; Sergio C, V15). Ask "who will this attract?" for every hook. Reject hooks that stop everyone, such as generic shock visuals: they confuse delivery (Dara Denney, V9).

## Scoring rubric (1-5 each, 30 max)

| Criterion | 1 | 5 |
|---|---|---|
| Scroll-stop power | Looks like every other ad | Impossible not to look at for a second |
| Clarity in 2 seconds | Needs context to understand | A tired contractor gets it instantly |
| Relevance to ICP | Could be for anyone | Unmistakably for this trade owner in this town |
| Differentiation from swipe file | Same as top competitors | Nobody in the market says or shows this |
| Truthfulness | Implies something unproven | Fully provable with real proof on hand |
| Self-selection | A homeowner or a random scroller would stop too | Only a [trade] owner in [market] would stop (Alessio Cordeddu, V8; Dara Denney, V9; Fraser Cottrell, V10) |

Any hook scoring below 4 on truthfulness is dropped regardless of total. Tag each hook with its funnel stage (TOF, MOF, BOF) and its template slug. Pick the top 1-2 per angle and say why.
