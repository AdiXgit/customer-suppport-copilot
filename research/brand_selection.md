# Brand Selection

Decision document for which brand's Twitter support conversations will
be used as the historical-resolution source of truth for the Hiver
take-home assignment.

Supporting evidence: `docs/DATA.md` (structure/quality) and
`research/dataset_reconnaissance.md` (topic sampling + real example
conversations). This document only scores and decides.

Do not confuse this with the final intent taxonomy — that has
deliberately not been created yet.

---

## Candidates Considered

Out of 108 brand accounts in the dataset, the following were evaluated
in depth based on tweet volume, topical focus, and initial skim:
AmazonHelp, AppleSupport, Uber_Support, SpotifyCares, Delta,
AmericanAir, British_Airways, SouthwestAir, TMobileHelp, comcastcares,
Ask_Spectrum, XboxSupport, sprintcare, AskPlayStation.

## Scoring Framework

Each finalist scored 1 (weak) – 5 (strong) on the 10 criteria from
CLAUDE.md/ENVIRONMENT recon instructions. Scores are judgment calls
grounded in the MEASURED/OBSERVED evidence in the companion documents,
not a formula — shown for comparative reasoning, not false precision.

| Criterion | AmazonHelp | AppleSupport | SpotifyCares | Delta | AmericanAir |
|---|---|---|---|---|---|
| 1. Conversation volume | 5 (82,556 convs) | 5 (80,717 convs) | 4 (28,280 convs) | 4 (26,168 convs) | 4 (26,386 convs) |
| 2. Multi-turn conversation quality | 3 (39,681 four+turn, but many trail into open-ended product issues) | 3 (20,108 four+turn, but often truncated by DM redirect) | 4 (8,117 four+turn, high ends-with-brand rate 94.0%) | 3 (7,915 four+turn, often ends in apology not fix) | 3 (8,203 four+turn, similar to Delta) |
| 3. Customer/support interaction density | 4 | 4 | 4 | 4 | 3 |
| 4. Diversity of support issues | 2 (too diverse — open-ended product catalog) | 3 (multiple device/software lines) | 5 (tight single-product domain) | 4 (coherent flight-ops domain) | 4 |
| 5. Historical resolution quality (visible, not DM-hidden) | 4 (DM-redirect only 0.6%, resolutions often visible) | 2 (DM-redirect 52.5% — resolution frequently invisible) | 4 (DM-redirect 30.8%, resolutions usually visible in-thread) | 4 (DM-redirect 16.5%) | 4 (DM-redirect 16.8%) |
| 6. Data cleanliness | 2 (5.2%+ non-English, broad long-tail topics) | 4 (99% English) | 5 (99.4% English, tight vocabulary) | 4 (99.6% English) | 4 (99.7% English) |
| 7. Suitability for intent classification (6–12 coherent intents) | 2 (would need dozens of intents or a lossy catch-all) | 3 (workable but spans many product lines) | 5 (account/billing/plan/playback/library/licensing/device map cleanly to ~9 intents) | 4 (delay/cancellation/baggage/booking/seat/refund/loyalty map to ~7-8) | 4 |
| 8. Suitability for historical retrieval/RAG | 3 (volume is great, but retrieval evidence is diluted by multilingual + open-ended content) | 2 (DM redirects mean much of the "evidence" is just a triage question, not a resolution) | 5 (visible, reusable resolution text: links, policy explanations, diagnostic steps) | 4 (visible policy answers for general questions; weaker for account-specific disruptions) | 4 |
| 9. Suitability for escalation analysis | 3 (escalation signal is diluted — near everything eventually gets a reply) | 4 (DM redirect itself is a natural, frequent escalation-like signal) | 4 (billing/account/refund cases plausibly need escalation; technical bugs don't — good mix) | 5 (compensation/rebooking/safety cases are natural escalations, policy Qs are not — clear mix) | 5 |
| 10. Evaluation feasibility (golden set of 150–250 examples) | 4 (plenty of volume, but harder to get balanced intent coverage) | 4 | 5 (easy to get balanced coverage across ~9 clear intents at this volume) | 4 | 4 |
| **Total (/50)** | **32** | **34** | **45** | **40** | **39** |

---

## Recommendation: **SpotifyCares**

### Why it wins

1. **Topically coherent** (OBSERVED, `research/dataset_reconnaissance.md`):
   a single product (the Spotify app/service) produces a naturally
   tight set of ~8–10 candidate intents — account/login, premium
   subscription & billing, family/student plan, app crashes/playback
   bugs, offline downloads, playlist/library management, content
   licensing/availability, device connectivity, and payment/refund.
   This fits the "6–12 useful intents" requirement without forcing or
   over-splitting.

2. **Best visible-resolution rate of any strong candidate.** DM-redirect
   is 30.8% (MEASURED) — lower than AppleSupport (52.5%), sprintcare
   (47.7%), comcastcares (71.5%), TMobileHelp (81.8%). The majority of
   SpotifyCares conversations contain the actual fix/answer in the
   public thread (a help-center link, a specific diagnostic step, a
   policy explanation), not just "please DM us." That directly matters
   for the RAG/retrieval corpus, whose entire value depends on the
   retrieved evidence containing a real resolution.

3. **Highest "conversation reaches closure" rate measured**: 94.0% of
   sampled SpotifyCares conversations end with a brand message
   (MEASURED), the highest among all candidates checked — a proxy for
   the brand consistently following through rather than leaving threads
   hanging.

4. **Nearly all English** (99.4% MEASURED, ASCII-heuristic lower bound)
   with a small, focused vocabulary — reduces the risk of a
   multilingual pipeline complication that AmazonHelp would introduce.

5. **A realistic AUTO_HANDLE / ESCALATE mix.** Technical/app issues
   (playback bugs, downloads, connectivity) are usually resolvable with
   documented fixes — good AUTO_HANDLE candidates. Account-specific
   billing, refund, and unauthorized-charge issues plausibly require
   escalation. This gives the escalation-policy component something
   real to discriminate between, rather than a domain that's either
   "everything can be auto-answered" or "everything needs a human."

6. **Volume is sufficient, not excessive**: 43,265 tweets, 28,280
   conversations, 8,117 with 4+ turns (MEASURED). That's easily enough
   to build a 150–250 example golden set with balanced intent coverage,
   a retrieval corpus with real depth, and room left over for held-out
   evaluation — without needing to subsample a firehose the way
   AmazonHelp or AppleSupport would require.

### Tradeoffs against the runners-up

- **vs. AppleSupport** (34/50): Apple has ~2.5x the tweet volume, but
  scores worse on exactly the two criteria that matter most for this
  assignment's stated priorities (evaluation and proof of quality over
  complexity) — resolution visibility and intent coherence. Half of
  Apple's replies are DM redirects; building a retrieval corpus on top
  of that means roughly half the "evidence" is a triage question with
  no visible answer. Apple remains a reasonable fallback if Spotify's
  smaller volume turns out to be limiting during golden-set
  construction.

- **vs. Delta/AmericanAir** (40/39 of 50): Airlines have excellent
  DM-redirect rates and a strong natural AUTO_HANDLE/ESCALATE split
  (general policy questions vs. account-specific disruptions/
  compensation), and are a legitimate alternative. They score slightly
  lower than SpotifyCares mainly on criterion 4/7/8 — flight-ops issues
  (delays, cancellations, overbooking) are often not resolvable by any
  reply, generic or human, until the operational situation itself
  changes; the "resolution" is frequently just an apology or a status
  update rather than a fix, which produces thinner grounded-generation
  evidence than Spotify's "here's the specific step that solves your
  problem" pattern.

- **vs. AmazonHelp** (32/50): despite the largest volume and
  surprisingly low DM-redirect rate, Amazon's topic space is
  effectively unbounded (any product Amazon sells can generate a
  support tweet) and measurably more multilingual (5.2%+ non-English,
  MEASURED lower bound; French/Spanish/Japanese conversations directly
  OBSERVED in samples). Compressing this into 6–12 coherent intents
  would require either an aggressive catch-all bucket (hurting
  classification quality) or scoping down to a subset of Amazon issues
  — at which point the effective usable volume advantage over Spotify
  mostly disappears.

### Decision

**Selected brand: SpotifyCares.**

This is a recommendation for sign-off, not a final irreversible choice
— it is cheap to revisit if intent-taxonomy drafting (next phase)
reveals a problem not visible at this reconnaissance depth (e.g. too
few examples in a particular intent bucket once real labels are drawn
up). AppleSupport and Delta are documented as the two credible
fallbacks in that case.

## Next Step

Per CLAUDE.md, do not build the intent taxonomy yet. The next phase
should draft a candidate taxonomy from a labeled sample of SpotifyCares
customer messages, then validate coverage/balance before touching
`.venv` or any modeling code.
