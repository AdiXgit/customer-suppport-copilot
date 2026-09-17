# SpotifyCares Golden Evaluation Set — Design (Phase 5)

## Status

DESIGN COMPLETE, **NOT YET LABELED**. This phase produced the sampling
pipeline and a 200-example candidate file ready for human annotation.
No human labeling has been performed — every `primary_intent` field in
the output file is `null`. This is an evaluation dataset (for measuring
the eventual system), not classifier training data.

Labels used throughout: **MEASURED** (computed from data), **OBSERVED**
(manually inspected), **HYPOTHESIS** (proposed, not yet validated).

This document covers what was produced, the schema, and how to use it.

---

## What was produced

| File | Purpose |
|---|---|
| `data/golden/golden_set_candidates.jsonl` | Full 200-example file with all sampling metadata (group, flags, provenance) + empty annotation fields. The audit trail. |
| `data/golden/golden_set_annotation_blind.jsonl` | Same 200 examples, stripped to only what a human annotator should see: `example_id`, `customer_message`, and the empty fields they fill in. No sampling-group or flag info, so labeling isn't anchored by *why* an example was selected. |
| `data/golden/golden_set_annotation_blind_shuffled.jsonl` | Same as above, row order shuffled (seed 12345) so Group A and Group B examples aren't presented in visible blocks. **Use this file for actual annotation.** |

After labeling, join the annotated blind file back to
`golden_set_candidates.jsonl` on `example_id` to recover full metadata
for analysis. The eventual fully-labeled file should be saved as
`data/golden/golden_set.jsonl` (per the storage convention in
CLAUDE.md) — not produced yet, since no labeling has happened.

No `.venv` changes, no classifier, no embeddings, no RAG, and no model
training were performed. Sampling reused the already-installed
project `.venv` (pandas, pyarrow — set up in Phase 4) and the
SpotifyCares-only conversation subset already materialized during
Phase 1/2 (itself built via a single chunked read of the 493MB raw CSV;
the raw CSV did not need to be re-scanned for this phase).
`data/raw/twitter/twcs.csv` was not modified. Banking77 was not
downloaded or used.

---

## Sample size and composition

**Target: 200 examples. Delivered: exactly 200.**

| Group | Size | Purpose |
|---|---|---|
| **A — natural-distribution random sample** | 120 | Unbiased random draw from the cleaned candidate pool. Reflects the real, messy proportions of intents as they actually occur (dominated by App Technical, Feature Request, Content Availability per Phase 2 findings) — this is the group to use for any "how does the system perform on realistic traffic" metric. |
| **B — deliberate rare-intent oversampling** | 80 (20 × 4 intents) | Regex-filtered candidate pools for the four intents Phase 2 flagged as naturally thin (Account Access & Login, Account Security, Country/Market Availability, General Complaint) — 20 candidates drawn per intent so each has enough examples for a meaningful per-intent metric, which a pure random 200-sample would not provide (Country/Market Availability alone would yield ~2 examples at its ~1% natural rate). |

**This distinction is preserved in the data**, not just in this
document: every example carries a `sampling_group` field
(`A_random` or `B_oversample_<intent>`). Any reported "headline"
accuracy/metric must be computed **from Group A alone** to represent
natural-distribution performance; Group B exists to get enough signal
on rare intents and must be reported **separately**, never blended into
the headline number without saying so. (This is also flagged as a
required "what's misleading about the headline number" caveat for the
eventual evaluation report, per CLAUDE.md.)

The regex buckets used to build Group B's candidate pools are heuristic
filters for *sampling* only. They are explicitly **not** treated as
ground truth: every Group B example still gets an independent human
`primary_intent` judgment, and the human is free to disagree with (or
exclude) the regex's implied intent.

---

## Expected examples per intent (HYPOTHESIS — pre-labeling estimate)

Based on Phase 2's OBSERVED 150-message manual sample percentages
applied to Group A (120), plus Group B's candidate pools (up to 20
each, before human confirmation):

| Intent | From Group A (est.) | From Group B (candidates) | Expected total (rough) |
|---|---|---|---|
| App & Playback Technical | ~23 | — | ~23 |
| Feature Request & Product Feedback | ~22 | — | ~22 |
| Content Availability & Catalog Accuracy | ~22 | — | ~22 |
| Premium Subscription & Billing | ~17 | — | ~17 |
| Account Access & Login | ~7 | +20 candidates | ~15–25 (precision-dependent) |
| General Complaint / Dissatisfaction | ~6 | +20 candidates | ~12–20 (regex is the vaguest here — lower precision expected) |
| Account Security | ~5 | +20 candidates | ~15–20 |
| Country/Market Availability | ~1 | +20 candidates | ~15–20 (formulaic phrasing → regex expected to be fairly precise) |
| OTHER/UNKNOWN / excluded | ~16 (from Group A only) | — | some fraction excluded at labeling time |

These are explicitly **HYPOTHESIS** — the regex candidate pools are not
validated against human judgment yet. Actual per-intent counts will
only be known after labeling. Do not treat this table as a target to
force-fit; if labeling reveals a Group B bucket has much lower true
precision than expected (e.g. General Complaint, whose regex is
broadest and most heuristic), that is useful information about the
taxonomy's OTHER/General-Complaint boundary, not a sampling failure.

---

## Exclusions applied before sampling

Per the OTHER/UNKNOWN strategy in `docs/INTENTS.md` and this phase's own
inspection, the following were removed from the candidate pool **before**
any random draw (all counts MEASURED):

| Exclusion | Count removed | Rule |
|---|---|---|
| Brand-family account misclassified as "customer" | 373 | See "New finding" below |
| Fragment (no content after stripping @mentions/URLs) | 138 | Stripped text < 3 characters |
| Bare DM-follow-up with no visible original issue | 60 | Message is only "check your DM" / "DM sent" / "urgent DM" phrasing, ≤8 words, no other content |
| **Total hard-excluded** | **568** (of 28,221 root messages, 2.0%) | |

Praise-only messages and non-English messages are **not** hard-excluded
mechanically (the risk of a false-positive regex drop was judged higher
than the annotation cost of a human seeing a few of these) — instead
they are soft-flagged (`flag_possible_praise_only`,
`flag_non_english_suspected` in the metadata file) for annotator
awareness, and the annotator makes the final exclude/keep call via the
`excluded` + `exclusion_reason` fields.

### New finding this phase: brand-family accounts posing as "customers"

Inspecting the full 28,221-message root pool (not just Phase 2's
150-message sample) surfaced a data-quality issue Phase 2's smaller
sample didn't catch: four recurring `author_id`s are **not real
customers** but official Spotify-family accounts whose tweets got
labeled `inbound=True` (customer) because they aren't in the 108
known *support* handles from Phase 1 — they're separate
marketing/status accounts:

| author_id | Root messages | Identity (OBSERVED from content) |
|---|---|---|
| 115888 | 331 | Main `@Spotify` account (promotional copy, e.g. "3 months of Premium for ₱9") |
| 125633 | 22 | `@SpotifyArtists` (Spotify for Artists announcements) |
| 117153 | 14 | Spotify status/incident account ("Everything should be back to normal now") |
| 116130 | 6 | Spotify music-promo account ("Check out the new album from...") |

**331 messages from a single "customer" account** is a strong signal
of a broadcast/marketing account, not an individual — genuine
customers overwhelmingly appear once. All four were verified by
reading sampled message content before exclusion. This is also the actual
identity behind `conv_id=83694`'s root message (see below) — the
83694 mega-thread turns out to be a promotional tweet from account
115888, exactly one of these four accounts.

---

## Handling the `conv_id=83694` mega-thread artifact

Per Phase 2's finding, `conv_id=83694` is a 62-message conversation
that is actually one promotional tweet with dozens of independent
customers replying — not a real 62-turn back-and-forth. This phase's
fuller inspection confirms **exactly why**: its root message
(`tweet_id=83694`) is authored by `author_id=115888`, the main
`@Spotify` marketing account identified above.

**How this is handled, concretely:**

1. **Structural protection (applies to every conversation, not just
   this one)**: the candidate pool is built from exactly one message
   per conversation — the root/first message — so no conversation,
   mega-thread or otherwise, can ever contribute more than one example
   to the golden set by construction. `conv_id` is asserted unique
   across the final 200 (verified programmatically).
2. **Direct exclusion**: `conv_id=83694`'s root message is authored by
   `115888`, one of the four brand-family accounts hard-excluded above
   — so it cannot be drawn at all, regardless of the structural
   protection in (1). Confirmed in the output: `conv_id=83694` does
   not appear in the final 200 (checked programmatically).
3. **Generalized beyond this one example**: since `115888` posts
   broadcast-style tweets that different customers reply to (creating
   the same "one promo tweet, many replies, merged into one
   conversation" pattern seen in 83694), excluding all four
   brand-family accounts prevents *every* instance of this pattern from
   contaminating the golden set, not just the one already-known case.
4. **Independence across likely-repeat customers**: separately, a
   global cap of **at most one root message per `author_id`** was
   applied across the whole candidate pool (removing 1,730 messages
   from otherwise-eligible root messages belonging to an author whose
   *other* message was kept instead) — this stops a single highly
   engaged/frequent complainer's account from occupying multiple
   "independent" evaluation slots, which is the same underlying
   correlation concern as the mega-thread issue, generalized to the
   customer-identity axis rather than the conversation-thread axis.
5. **Metadata retained for auditability**: every example carries
   `conv_size` and `flag_mega_thread_suspect` (true when
   `conv_size >= 15`, the measured 99.5th-percentile threshold for
   SpotifyCares conversation length) so future analysis can always
   check whether an example came from an unusually large reconstructed
   thread, even though (per point 1) only its single root message was
   ever used as the example text. In the final 200, 0 examples are
   flagged `mega_thread_suspect` — a plausible outcome, since only
   ~0.35% of the cleaned pool carries that flag.

---

## Annotation schema

JSONL was chosen over CSV: tweet text routinely contains commas,
quotes, newlines, and emoji, all of which are error-prone in CSV
without careful escaping; JSONL keeps each example a self-contained,
unambiguous JSON object and loads directly into pandas
(`pd.read_json(..., lines=True)`) for evaluation code later.

### Fields present in every example (metadata file)

| Field | Type | Filled at | Description |
|---|---|---|---|
| `example_id` | string | sampling time | Stable ID, e.g. `GOLD-0001`, for joining blind-annotated results back to metadata |
| `conversation_id` | int | sampling time | The reconstructed conversation's root tweet_id-derived `conv_id` (Phase 1 method) |
| `tweet_id` | int | sampling time | The specific tweet ID of the customer message (== conversation_id for a true root) |
| `author_id` | string | sampling time | For provenance/dedup auditing only — never shown to the annotator |
| `customer_message` | string | sampling time | **The only labeling input** (requirement: annotators see only this + example_id) |
| `created_at` | string | sampling time | Original tweet timestamp, for provenance |
| `conv_size` | int | sampling time | Number of messages in the reconstructed conversation (mega-thread awareness) |
| `sampling_group` | string | sampling time | `A_random` or `B_oversample_<intent>` — audit-only, hidden from annotator |
| `target_intent_hint` | string/null | sampling time | Which regex bucket pulled this into Group B, if any — audit-only, **not** a label |
| `flag_possible_praise_only` / `flag_non_english_suspected` / `flag_mega_thread_suspect` / `flag_high_frequency_author` | bool | sampling time | Heuristic hints for annotator awareness — audit file only |
| `primary_intent` | string/null | **by human annotator** | Exactly one of the 8 taxonomy intents or `OTHER_UNKNOWN`, per `docs/INTENTS.md` |
| `secondary_issue` | string/null | **by human annotator** | Optional — a second issue mentioned in the same message, if any |
| `ambiguous` | bool | **by human annotator** | True if the annotator found this genuinely hard to call |
| `non_english` | bool | **by human annotator** | Pre-filled as a hint from the ASCII heuristic in the metadata file, but reset to blank in the blind annotation file — annotator judges fresh |
| `excluded` | bool | **by human annotator** | True if this should NOT count as a valid golden example (praise-only, off-topic, uninterpretable, etc., per the labeling guide) |
| `exclusion_reason` | string/null | **by human annotator** | Required if `excluded=true` |
| `annotator_notes` | string/null | **by human annotator** | Free text |
| `annotator_id` | string/null | **by human annotator** | Who labeled it (for future inter-annotator agreement analysis) |
| `label_timestamp` | string/null | **by human annotator** | ISO date labeled |

### Labeling workflow

1. Annotator works from `golden_set_annotation_blind_shuffled.jsonl`
   only — this file has none of the sampling/flag metadata, so the
   annotator cannot infer or be biased by why an example was selected.
2. For each example: read `customer_message` only (never the brand's
   reply, never the rest of the conversation — this phase's requirement
   is that ONLY the customer message is labeling input).
3. Assign exactly one `primary_intent` from the 8-intent +
   OTHER/UNKNOWN taxonomy, using the tie-breaking rules and each
   intent's include/exclude criteria in `docs/INTENTS.md`.
4. Optionally fill `secondary_issue`, `ambiguous`, `non_english`.
5. If the message isn't a genuine labelable support request (per the
   OTHER/UNKNOWN exclusion criteria in `docs/INTENTS.md`), set
   `excluded=true` and give a reason instead of forcing a `primary_intent`.
6. After labeling, join back to `golden_set_candidates.jsonl` on
   `example_id` for analysis (per-group breakdowns, flag correlation,
   etc.).

This phase does **not** perform this labeling — it produces the
ready-to-use file and process only, per the instruction not to fabricate
labels or auto-assign final intents.

---

## Reproducibility

Single global random seed: **12345**, used consistently for every
random operation in the pipeline (author-dedup tie-breaking, Group A
draw, all four Group B bucket draws, and the final shuffle for the
blind-annotation file). Re-running the pipeline against the same
underlying SpotifyCares conversation data will reproduce the identical
200 example_ids and order.
