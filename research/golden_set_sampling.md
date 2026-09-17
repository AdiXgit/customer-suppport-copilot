# Golden Set Sampling — Method, Evidence, and Pipeline Detail

Companion to `docs/GOLDEN_SET.md` (the user-facing summary). This file
holds the full method, intermediate measurements, and the reasoning
behind each design decision.

Labels: **MEASURED** (computed), **OBSERVED** (read directly from
data), **HYPOTHESIS** (plausible, not yet validated).

No `.venv` changes, classifier, embeddings, RAG, or model training were
performed in this phase. All processing used the project `.venv`
(pandas 3.0.5, pyarrow 25.0.1 — set up in Phase 4) against the
SpotifyCares-only conversation subset already materialized in Phase 1/2
(`spotify_all_convs.parquet`, 91,889 rows / ~9MB, covering all 28,280
SpotifyCares conversations). `data/raw/twitter/twcs.csv` was not
re-read or modified in this phase — see "Why the raw CSV wasn't
touched" below.

---

## Why the raw CSV wasn't touched (requirement 11)

Requirement 11 asks for chunked/streaming processing and to avoid
loading the full 493MB raw CSV unnecessarily. This phase satisfies that
by **not loading it at all**: Phase 1 already performed a single,
memory-conscious full read of `data/raw/twitter/twcs.csv` (dtype-
optimized, not chunked, but a one-time cost already paid and
documented in `docs/DATA.md`) to reconstruct all 798,197 conversations
across the whole dataset, then Phase 2 isolated just the SpotifyCares
subset. That subset (~9MB) is what this phase operates on. Re-deriving
it from scratch would require re-reading the 493MB file; reusing the
already-materialized artifact avoids that entirely, which is a
stronger form of "avoid loading the CSV unnecessarily" than merely
chunking a re-read would be. If this subset needs to be regenerated in
a future session (e.g. a fresh environment without the cached
artifact), the regeneration should follow the same chunked approach
already used and documented in Phase 1 (`docs/DATA.md` §2).

---

## Step 1 — Inspect conversation-size distribution (MEASURED)

| Percentile | Conversation size (messages) |
|---|---|
| p50 | 2 |
| p75 | 4 |
| p90 | 6 |
| p95 | 8 |
| p99 | 12 |
| p99.5 | 15 |
| p99.9 | ~34 |
| max | 354 |

157 of 28,280 conversations (0.56%) have 15+ messages; 67 (0.24%) have
20+; 34 (0.12%) have 30+. The `flag_mega_thread_suspect` threshold
(`conv_size >= 15`) uses the p99.5 cutoff — a conservative,
data-derived threshold rather than an arbitrary round number.

Root customer messages (conversations that open with an inbound
customer tweet, not a proactive brand message): **28,221** of 28,280
conversations (59 open with a brand message instead — noted in Phase 2,
not further investigated this phase since they're structurally
excluded from a "customer message" candidate pool by definition).

---

## Step 2 — The `conv_id=83694` mega-thread, root-caused

Phase 2 flagged `conv_id=83694` (62 messages) as a broadcast-tweet
artifact without identifying *why* the reply-chain reconstruction
merged so many unrelated customers into it. Direct inspection this
phase:

```
tweet_id=83694, author_id=115888, inbound=True, text="Zero ads. All
music. Get 3 months Premium for ₱9."
```

`author_id=115888` posted this. Sampling other root messages from
`115888` across the dataset (OBSERVED, 3 examples shown):

```
"Unli skips. Unli fun. 3 months of Premium for ₱9."
"3 months of Premium is just RM2. Play music offline wherever you go."
"Unli skips. Unli fun. 3 months of Premium for ₱9."
```

This is promotional copy, repeated near-verbatim across many tweets —
not customer complaints. `115888` is almost certainly the main
`@Spotify` account (its numeric ID is what many *real* customers
`@`-mention throughout the corpus, consistent with Phase 1's finding
that non-support accounts appear as anonymized numeric IDs in this
dataset). Because `115888` is not in the 108 known *support* handles
identified in Phase 1 (only actual `*Support`/`*Cares`/etc. accounts
were), the dataset's `inbound` field mislabels its tweets as customer-
originated (`inbound=True`), and the reply-chain reconstruction
correctly-but-misleadingly treats each of its promotional broadcasts as
a "conversation root" that many independent customers' replies then
attach to — exactly the mega-thread pattern.

---

## Step 3 — Systematic search for the same pattern (MEASURED, new finding)

Phase 2's 150-message manual sample was too small to surface this
pattern (expected hits: 373/28,221 × 150 ≈ 2 messages). This phase
inspected the full root-message pool's author frequency distribution
instead:

| author_id | Root messages | Content identity (OBSERVED) |
|---|---|---|
| 115888 | 331 | Main `@Spotify` account (promo copy) |
| 125633 | 22 | `@SpotifyArtists`("Spotify for Artists") announcements |
| 117153 | 14 | Spotify status/incident account ("Everything should be back to normal now", "We're investigating some payment issues") |
| 287348 | 11 | **Genuine individual customer** (angry, recurring complainer — kept) |
| ...16 more accounts with 5-10 root messages each | 5–10 each | Manually spot-checked; genuine individual customers (some highly engaged repeat complainers, e.g. about the explicit-content filter feature request) |
| 116130 | 6 | Spotify music-promo account ("Check out the new album from...") |
| 348450 | 5 | Genuine customer, but all 5 root messages are bare "DM! Urgent!" follow-ups with no visible issue — caught separately by the DM-follow-up exclusion rule, not the brand-family rule |

Method: listed all 24 `author_id`s with ≥5 root messages (500 messages
total, 1.8% of the pool) and read 3 sample messages from each
(OBSERVED). A stark frequency gap separates the four brand-family
accounts (331/22/14/6) from the next-highest genuine customer (11) —
consistent with "one very vocal individual" vs. "an automated/official
posting account." Content confirmed the classification in every case;
this was not a frequency-threshold-only decision.

**Decision**: hard-exclude root messages from `{115888, 125633, 117153,
116130}` (373 messages total) as a mechanical, auditable rule based on
verified content — not a classifier, not an automatic intent label,
just a "this speaker is not a customer" provenance filter. All other
high-frequency authors (including `287348` and the sixteen 5-10-count
accounts) are kept as legitimate customers, only soft-flagged
(`flag_high_frequency_author`) for annotator awareness.

This is the concrete resolution to requirement 5 (`conv_id=83694`
handling) — see `docs/GOLDEN_SET.md`'s "Handling the mega-thread
artifact" section for the full explanation of how this generalizes
beyond the one known example.

---

## Step 4 — Building the eligible candidate pool (MEASURED)

Starting from 28,221 root customer messages:

| Filter | Removed | Cumulative remaining |
|---|---|---|
| Start | — | 28,221 |
| Brand-family account (115888/125633/117153/116130) | 373 | 27,848 |
| Fragment (≤2 chars after stripping @mentions/URLs) | 138 | 27,710 |
| Bare DM-follow-up, no visible issue (regex, ≤8 words) | 60 | 27,653 (some overlap possible in principle; measured sequentially, no double-count observed) |
| **Diversity dedup**: max 1 root message per `author_id` (see below) | 1,730 | **25,923** |

### Diversity dedup detail

26,085 unique authors exist across the 28,221-message root pool (i.e.
most customers tweet once, but a long tail tweets repeatedly). After
the hard exclusions above, capping each `author_id` to exactly one
retained root message (chosen via a seeded random pick among that
author's eligible messages, not "first" or "last", to avoid systematic
recency/order bias) removes 1,730 messages. This directly supports
requirement 5's spirit — generalizing the "don't let one
correlated source dominate multiple evaluation slots" principle from
the conversation-thread axis (mega-threads) to the customer-identity
axis (repeat tweeters) — and produces a **final sampling frame of
25,923 unique-author, non-fragment, non-brand-family, non-bare-DM-
followup root customer messages.**

### Regex patterns used (fragment / DM-followup / brand-family — hard filters)

```python
BRAND_FAMILY_ACCOUNTS = {"115888", "125633", "117153", "116130"}

# fragment: len(strip_mentions_and_urls(text)) < 3

DM_FOLLOWUP = re.compile(
    r"^(please\s+)?(check|read|see|reply to|respond to)?\s*(your |ur |my )?dm'?s?\b.*$"
    r"|^dm'?d?\b.*$|^urgent\b.*dm.*$",
    re.IGNORECASE,
)
# excluded only if the stripped message also has <= 8 words total
```

### Soft flags (kept, not excluded — surfaced to annotator)

| Flag | Count in eligible pool (25,923) | Method |
|---|---|---|
| `flag_possible_praise_only` | 170 | Regex: starts with thanks/thank you/ty/thx/love this/great job |
| `flag_non_english_suspected` | 105 | ASCII-ratio heuristic (<90% ASCII), same method as Phase 1/2 — a lower bound, not language ID |
| `flag_mega_thread_suspect` | 91 | `conv_size >= 15` (p99.5 threshold) |
| `flag_high_frequency_author` | 121 | Author has ≥5 root messages in the (pre-dedup) eligible pool |

These are intentionally **not** hard-excluded — praise-only and
non-English detection via regex/heuristic risk false positives (e.g.
"Thanks for nothing, still broken" starts with "Thanks" but is a real
complaint), so the human annotator makes the final call using the
`excluded` + `exclusion_reason` fields, with the flag as a hint only in
the audit-trail file (never shown in the blind annotation file).

---

## Step 5 — Sampling (MEASURED, seed 12345)

### Group A — natural-distribution random sample

`frame.sample(n=120, random_state=12345)` on the full 25,923-row
eligible frame. No stratification, no filtering beyond Step 4's
exclusions — this is what makes it representative of natural
SpotifyCares customer-message traffic.

### Group B — deliberate rare-intent oversampling

For each of four intents Phase 2 flagged as naturally thin (Account
Access & Login ~6%, Account Security ~4%, General Complaint ~5%,
Country/Market Availability ~1%), built a regex candidate pool over the
**remaining** frame (Group A's 120 rows removed first, so no
duplication across groups), then drew up to 20 per bucket
(`random_state=12345`), removing drawn rows before moving to the next
bucket so no example is double-drawn:

| Intent hint | Regex pattern (abbreviated) | Candidate pool size (MEASURED) | Drawn |
|---|---|---|---|
| `account_security` | `hack(ed)?\|compromised\|suspicious (activity\|login)\|unauthori[sz]ed\|someone (else )?(logged\|is using\|hijacked) my account\|stolen account\|hijack(ed)?` | 445 | 20 |
| `account_access_login` | `log ?in\|login\|sign ?in\|sign ?up\|register\|password\|can't (get\|access) (my\|into) account\|locked out\|reset my password\|verify my account\|username` | 1,803 | 20 |
| `country_market_availability` | `available in\|launch in\|coming to\|when will spotify (be\|come)\|not available in my country\|expand to\|come to (india\|egypt\|pakistan\|bangladesh\|russia)` | 244 | 20 |
| `general_complaint` | `worst (customer service\|support)\|terrible (customer service\|support)\|horrible (service\|support)\|useless (support\|app\|service)\|poor customer service\|no response\|nobody (replies\|responds)\|ignored my (dm\|email)\|switch(ing)? to (apple music\|tidal\|youtube music\|deezer)\|customer service is (bad\|terrible\|poor\|awful)\|awful (service\|support\|experience)` | 77 | 20 |

Note on the `general_complaint` bucket: its candidate pool (77) is the
smallest and its regex the broadest/vaguest of the four — this is
expected to have the lowest precision against the human-judged
`General Complaint / Service Dissatisfaction` taxonomy intent (vague
venting is inherently harder to pattern-match than a formulaic ask like
"is Spotify available in my country"). This is called out explicitly
in `docs/GOLDEN_SET.md` as a HYPOTHESIS to watch during labeling, not
hidden.

All four regex patterns are **heuristic sampling filters only**. No
example's `primary_intent` is pre-filled from `target_intent_hint` —
that field exists purely as an audit trail explaining *why* a Group B
example was selected, and is excluded from the blind annotation file
entirely so it cannot influence the human judgment (satisfies
requirement 10 — no fabricated labels — and the "do not automatically
assign final intent labels" constraint).

### Final assembly and checks (MEASURED)

- Group A (120) + Group B (80) = **200** exactly.
- Verified programmatically: `conv_id` unique across all 200 (no
  conversation contributes more than one example); `author_id` unique
  across all 200 (no customer contributes more than one example); none
  of the 4 brand-family accounts appear.
- `conv_id=83694` does not appear in the final 200 (its root message
  was already hard-excluded at the pool-construction stage, so it was
  never eligible to be drawn).
- 0 of the final 200 carry `flag_mega_thread_suspect=true` — a
  plausible outcome of random sampling given the flag's ~0.35%
  incidence in the eligible pool (expected value across 200 draws
  ≈ 0.7), not a targeting decision.
- `example_id`s assigned as `GOLD-0001`...`GOLD-0200` after sorting by
  `(sampling_group, conv_id)` for a stable, reviewable file order in
  the metadata file; the separate shuffled blind file randomizes
  presentation order for actual annotation.

---

## Files produced

- `data/golden/golden_set_candidates.jsonl` — 200 rows, full metadata + empty annotation fields.
- `data/golden/golden_set_annotation_blind.jsonl` — 200 rows, annotation-only fields, same order as above.
- `data/golden/golden_set_annotation_blind_shuffled.jsonl` — same 200 rows, shuffled (seed 12345), intended for actual labeling.

None of these are training data, none contain a filled `primary_intent`
yet, and none touch or duplicate the raw dataset — they are derived,
reproducible artifacts (rebuildable from `data/raw/twitter/twcs.csv`
plus this document's method, per CLAUDE.md's reproducibility rule).

---

## Explicitly out of scope for this phase (per instructions)

- No actual human labeling was performed (all `primary_intent` fields
  are `null`).
- No classifier, embeddings, RAG, or support-agent code was written.
- Banking77 was not downloaded or referenced.
- `data/raw/twitter/twcs.csv` was not modified, and was not even
  re-read (see "Why the raw CSV wasn't touched" above).
- The brand's historical response text was never used to influence
  sampling or would-be labeling — only `customer_message` (the
  inbound tweet) was used for every filtering, flagging, and sampling
  decision in this phase, consistent with requirement 7 (labeling must
  use only the customer message) and the general "don't let the
  brand's response leak into intent labeling" principle already
  established in Phase 2.
