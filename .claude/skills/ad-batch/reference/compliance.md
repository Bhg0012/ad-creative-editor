# Compliance and honesty

These are hard rules. They beat conversion, deadlines, and requests. If a line or visual risks one, flag it at the gate with a compliant alternative.

## Hard rules

1. **No fabricated proof.** No invented testimonials, reviews, client names, results, screenshots, logos, or "as seen on". Hypothetical numbers or examples are labeled "example" on screen.
2. **Stats** only from a named, dated source verified this session; show the source on screen in small text where practical.
3. **Personal attributes** (Meta policy, playbook `personal_attributes`): never assert or imply the viewer's financial status, health, or other personal attributes. Call out by trade and place ("Opelika plumbers"), not by hardship ("Struggling to get by?").
4. **No misleading claims.** No guaranteed rankings, no "guaranteed X leads/jobs/reviews" unless Bruce guarantees it in writing. No fake urgency (countdowns, "only 2 spots left") unless true right now.
5. **No fake UI.** Never mimic Facebook, Instagram, or Google interface elements so they look like a real notification or system message.
6. **Licensing.** Only music, SFX, fonts, and footage with rights for paid ads. Music: ad-licensed tracks with the license on file, or Meta Sound Collection (Meta platforms only). Never in-app trending music. If unsure, ask.
7. **Client permission.** Only show client names, logos, faces, reviews, or results Bruce confirms he has written permission to use.
8. **Trademarks.** No Google or Meta logos in a way that implies endorsement or partnership. Describing "Google reviews" in words is fine.
9. **AI content.** No AI-generated people, voices, reviews, or screenshots presented as real. Any photorealistic AI-generated or AI-altered element gets Meta's AI disclosure at upload (playbook `ai_content_disclosure`).
10. **Advantage+ creative enhancements** must not be allowed to rewrite claims, add music, or generate visuals Bruce has not approved (playbook `advantage_creative_enhancements`).
11. **Third-party reviews of competitors** used for ICP research are quoted as research only, never shown in ads.

## Per-ad checklist (run at scripting and again at QA)

- [ ] Every number on screen or in VO is real and sourced, or labeled "example".
- [ ] Every testimonial, client name, logo, screenshot, and face has written permission on file.
- [ ] No "you" line implies a personal attribute (finances, health, struggle).
- [ ] No guarantee, ranking promise, or result promise beyond what Bruce offers in writing.
- [ ] Urgency or scarcity, if any, is true today and matches `config.yaml`.
- [ ] Offer, price, and risk reversal match `config.yaml` exactly; nothing unapproved.
- [ ] No platform UI imitation; no Google/Meta logos implying endorsement.
- [ ] All music, SFX, fonts, and footage have ad-use rights on file.
- [ ] No synthetic person, voice, or review presented as real; AI disclosure set if any AI-altered photorealistic content.
- [ ] The landing destination delivers exactly what the ad promises (message match).
