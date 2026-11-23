# Copy package

One file per ad: `exports/<adname>_copy.md`. Every line follows the wording rules (grade 5-6, local voice, specific, "you" over "we", no em dashes) and the compliance checklist.

## Primary text (3 variants)

- Short by default: 1-3 punchy lines. The hook is the first line and must work alone, because Reels shows only about 44 characters and Feed truncates at "See more" (Meta recommends 50-150 characters for Feed). On Reels the first 7-8 words carry the lead-in; Sabri Suby's "first 11 or 14 words" (V13) applies to Feed.
- **One long-form story variant per batch** for cold traffic: hook, the story, problem, how it works, proof, offer, CTA, in short scannable lines. Long story copy does best on cold traffic and gives delivery more context about who the ad is for (Sabri Suby, V3 and V13). Short stays the default for Reels.
- **Lead-in:** open on the high point of a real story, conversational, in the person's own words (quotes are fine). Only from a real quote or a real result (compliance rule 1). Reject the pattern "Are you a business owner who wants more leads?" (Sabri Suby, V13).
- **Assume no one knows AuburnSEO.** Top-of-funnel headlines and hook lines must make sense to a stranger; no brand name as the hook. Offer and close ads are exempt (Alex Cooper, V11: "Assume no one knows or cares").
- **Clarity over curiosity by default.** An Instant Form has no advertorial to do the selling after the click, so the ad must be clear. Pick one and do not get stuck in the middle (Alex Cooper, V11).
- **Customer's exact words.** Pull the most emotionally loaded phrases from real reviews, ad comments and sales-call notes, unpolished, even if the grammar is off. A customer talking to a customer beats a business talking to a customer (Alex Cooper, V11). Run real reviews through an LLM to find "golden nugget" lines (Dara Denney, V4). Real and permitted only.
- **Frames that work** (Dara Denney, V4; Alessio Cordeddu, V5): taboo ("what most agencies won't tell you"), myth buster ("It's not X, it's Y", the industry as the villain), the hack frame ("Before you pay for ads, try this"), negative marketing that names the fear (losing the job to the competitor with more reviews). Never personal-attribute wording ("Are you struggling...?").
- Each variant opens differently (question, call-out, result), not just reworded.
- **No AI-isms:** "it's not just X, it's Y", "game changer", "unlock", "here's the thing" (Matt Wolfe, V20). `tools/lint_copy.py` flags them in copy files and in `brief/08_scripts.md`.

## Headline (3 variants; 2 for a flexible ad)

For a flexible 3-2-2 ad (`reference/launch.md`) write 2 meaningfully different primary texts and 2 headlines: different angles, not two wordings of one idea (Professor Charley T, V14). The headline is the ad on statics (Alex Cooper, V11).

Outcome-focused, about 27 characters (Meta's Feed recommendation; longer gets cut). Example: "More 5-star reviews, on autopilot" is 33, too long; "Get 5-star reviews on autopilot" is 31, still long; "5-star reviews on autopilot" is 27.

Count characters for every headline and show the count.

## Description (1-2 variants, optional)

Short supporting line; often hidden on mobile placements, so never put anything essential here.

## CTA button

Recommend one (Learn More, Get Quote, Book Now, Sign Up, Apply Now) with a one-line reason. It must match the actual next step: "Book Now" only if the destination is a booking page.

## Instant Form or landing page notes

- Form type: "Higher intent" (adds a review step) unless Bruce has a reason for "More volume".
- Intro headline matching the ad's promise.
- 3-5 qualifying questions to filter bad leads: trade, city/market, current number of Google reviews (multiple choice), how soon they want to start, best time to call. Prefer multiple choice over short answer.
- **Disqualify clear non-fits with conditional logic** (Ben Heath, V12): one multiple-choice question whose non-qualifying answers lead to a closing screen for non-leads, so they never submit and never count as a lead, and Meta stops optimizing toward them. Disqualify only clear non-fits: outside the batch's market or service area, not the owner or decision maker, a trade AuburnSEO does not serve. Do not filter on soft signals until volume allows; fewer counted leads slows learning (playbook `learning_phase`, `instant_form_disqualify`).
- **Phone verification:** on Higher intent forms, require a one-time passcode by SMS (Ben Heath's own default, V12). Confirm both options exist in Bruce's form builder before promising them.
- Write the question, each answer, and which answers close the form into this file.
- Privacy policy link (required by Meta for lead forms).
- Thank-you screen copy that pushes to book a call now, with the booking link, and sets the expectation ("Bruce will text you within 1 business hour"). Only promise a response time Bruce will actually meet.
- Lead quality loop: the CRM should send qualified / booked events back to Meta (see `reference/launch.md`).
- Judge results by cost per qualified lead (form completed with qualifying answers), not cost per raw lead (Ben Heath, V12).

## Message match check

Last line of the file: one sentence confirming the video's angle, promise, offer, and CTA match the copy and the destination, or listing the mismatch to fix.
