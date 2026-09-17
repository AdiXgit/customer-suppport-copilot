# Golden Set Annotation Guide

## Status

Calibration phase (Phase 6A). This guide explains how to label the
25-example calibration batch — and, once calibration is reviewed and
any taxonomy issues it surfaces are resolved, the full 200-example
golden set. **No examples have been labeled yet.** This document does
not change the taxonomy in `docs/INTENTS.md`; it only explains how to
apply it consistently.

Files involved:

- `data/golden/golden_calibration_batch_25.jsonl` — the 25 examples to
  label, machine-readable, blank annotation fields. **Fill this one in.**
- `data/golden/golden_calibration_batch_25.md` — the same 25 examples,
  human-readable, for reading/reviewing alongside the JSONL. Not a
  separate source of truth — don't fill in two places.
- `docs/INTENTS.md` — the 8-intent + OTHER/UNKNOWN taxonomy: full
  definitions, include/exclude rules, and examples for each intent.
- `research/intent_discovery.md` — the original draft labeling guide
  (tie-breaking rules, edge cases) this document consolidates and
  restates for calibration use.

---

## 1. How to label one example

For each row in `golden_calibration_batch_25.jsonl`:

1. Read `customer_message` — and **only** `customer_message`. No other
   field in the file, and no information outside the file, should
   inform your label (see §7 on why).
2. Decide: is this a genuine, interpretable customer support request?
   - If no (praise-only, off-topic, promotional, uninterpretable
     fragment) → skip to §5 (exclusion) instead of assigning an intent.
   - If yes, continue to step 3.
3. Open `docs/INTENTS.md` and find the single best-matching intent
   among the 8 defined there. Use each intent's **Definition**,
   **Include**, and **Exclude** fields — don't rely on memory of the
   intent names alone, since several are easy to conflate (see §3).
4. Fill in the record:
   - `primary_intent`: the exact intent name from `docs/INTENTS.md`
     (or `OTHER_UNKNOWN` if it's a genuine request that still doesn't
     fit any of the 8 — this should be rare; most non-fitting messages
     turn out to be exclusions instead, see §5).
   - `secondary_issue`: optional — see §1a.
   - `ambiguous`: see §4.
   - `non_english`: see §6.
   - `excluded` / `exclusion_reason`: see §5.
   - `annotator_notes`: anything worth flagging for later review —
     free text, optional.
5. Move to the next example. Don't go back and revise earlier labels
   based on patterns you notice later in the batch — if you notice
   something that makes you want to revise, write it in
   `annotator_notes` on the current example and flag it for review
   instead, so early labels aren't silently inconsistent with the
   reasoning that produced them.

### 1a. Secondary issue

Some messages raise two distinct problems (e.g. a billing complaint
that also mentions being logged out). Per `research/intent_discovery.md`:
label `primary_intent` as whichever issue is stated first / is the main
point of the message, and note the other one in `secondary_issue` as a
short phrase (not necessarily a formal intent name). Don't invent a
multi-label scheme beyond this one optional field.

---

## 2. Intent definitions to consult

The full definitions live in `docs/INTENTS.md` — this guide doesn't
duplicate them in full, since they're detailed (each has Definition /
Include / Exclude / representative examples / typical resolution /
escalation tendency / confusion pairs). The 9 labels you'll choose from:

1. Account Access & Login
2. Account Security (Unauthorized Access)
3. Premium Subscription & Billing
4. App & Playback Technical Issues
5. Content Availability & Catalog Accuracy
6. Feature Request & Product Feedback
7. General Complaint / Service Dissatisfaction
8. Country/Market Availability Inquiry
9. `OTHER_UNKNOWN` (only when excluded=false but nothing above fits —
   see §5 for why this should be rare)

Read each intent's **Include** and **Exclude** bullets in
`docs/INTENTS.md` before starting, not just the one-line names above —
the names alone are not enough to label consistently (e.g. "Account
Access" vs. "Account Security" differ only in whether a third party is
implicated, which isn't obvious from the name).

---

## 3. Tie-breaking rules

Restated from `research/intent_discovery.md` (the authoritative source
— consult it directly if a case here doesn't cover your example):

- **App Technical vs. Content Availability** ("this song won't play"):
  - Error message, crash, freeze, a recent update breaking things, or
    the problem affecting many/all songs at once → **App Technical**.
  - One specific song/artist/album named as absent, with no error/bug
    language → **Content Availability**.
  - Genuinely unclear → default to **Content Availability** (the more
    common root cause historically, per Phase 2/3 sampling).
- **Feature Request vs. General Complaint**:
  - A concrete, specific, extractable ask, even if delivered angrily
    → **Feature Request**.
  - Purely evaluative venting with nothing to act on → **General
    Complaint**.
- **Country/Market Availability vs. Content Availability**:
  - "Is Spotify available in my country" → **Country/Market**.
  - "Is [song/artist] available in my country" → **Content
    Availability**.
- **Account Access vs. Account Security**:
  - Customer just forgot their own password / can't register → **Account
    Access & Login**.
  - Customer says or implies a third party accessed the account
    ("hacked," "someone else," "stolen," unexplained activity/
    device/library changes) → **Account Security**.
- **Account Access & Login vs. App & Playback Technical Issues**
  (FINALIZED, Phase 6D — see `docs/INTENTS.md`'s "Tie-Break: Account
  Access & Login vs. App & Playback Technical Issues" for the full
  rationale and `docs/TAXONOMY_CONFLICT_REVIEW.md` for the
  investigation that produced it): **Account Access & Login** is for
  access/credential problems — the customer can't log in, register, or
  reset a password, and nothing in the message points to a product/UI/
  technical fault. **App & Playback Technical Issues** requires actual
  evidence of a malfunction, not just a login-shaped symptom. Check, in
  order:
  1. Does the message quote a **verbatim technical identifier** (an
     HTTP status code, an internal token/parameter name, an
     exception-style string — e.g. "error 404," "CSRF token is
     invalid")? → **Technical**.
  2. Does the message describe a **broken or non-functional UI
     element/app behavior itself** (a button that doesn't work, a
     crash), not just a rejection outcome? → **Technical**.
  3. Does the message describe **troubleshooting behavior** the
     customer already tried (reinstalling, clearing cache, restarting,
     switching browsers)? → **Technical**.
  4. **None of the above** — only a plain-language credential
     rejection ("password invalid," "username invalid," "email
     doesn't exist," "credentials have been used") or a bare "can't
     log in" with no other detail → **Account Access & Login**.
  A referenced-but-unshown error (e.g. "error message below" with only
  a link, no error text in the message itself) does **not** satisfy
  criterion 1 — you cannot classify by a technical identifier you
  cannot see; fall back to Account Access & Login or OTHER/UNKNOWN
  depending on how much other context exists. Apply criteria 1–3 in
  order and stop at the first match; this is meant to be checked
  mechanically, not judged by tone or severity, so two annotators
  reading the same message should land on the same label.
- **Multiple issues in one message**: label by the primary/first-stated
  issue (see §1a for the secondary field).

If you hit a case not covered above or in `research/intent_discovery.md`,
write it in `annotator_notes` rather than guessing silently — these
notes are exactly what calibration review is for.

---

## 4. When to mark `ambiguous`

Set `ambiguous: true` when you can defend two different primary-intent
choices for the same message and neither the tie-breaking rules above
nor `docs/INTENTS.md`'s Include/Exclude bullets settle it — i.e. you
made a judgment call, not just applied a rule. Still fill in your best
`primary_intent` guess; `ambiguous` is a flag for review, not a
substitute for a label. Use `annotator_notes` to briefly say what the
two candidate intents were and why you picked the one you did.

Don't mark `ambiguous` just because a message is angry, poorly worded,
or contains multiple sentences — only when the *intent classification
itself* is genuinely unclear.

---

## 5. When to exclude

Set `excluded: true` (and fill `exclusion_reason`) instead of forcing a
`primary_intent` when the message is not a genuine, labelable support
request. Per the existing exclusion criteria (`research/intent_discovery.md`,
`docs/GOLDEN_SET.md`):

| Situation | exclusion_reason |
|---|---|
| Praise/thanks only, no request | `praise_only` |
| Off-topic (promotional content, business/partnership inquiry, meme/joke, song lyric quote) | `off_topic` |
| Uninterpretable fragment (bare link, single word/emoji, no usable content) | `fragment` |
| DM-follow-up meta-message with no visible original issue ("check your DMs", "sent a DM") | `dm_followup_no_issue` |
| Sarcastic praise/backhanded compliment referencing an unstated dispute | `unstated_dispute` |
| Non-English and genuinely uninterpretable without translation | `non_english_uninterpretable` (also set `non_english: true`, see §6) |

Note: the calibration batch and full golden set already had the most
mechanical junk (obvious fragments, bare DM-follow-ups, and known
brand-marketing accounts misfiled as customers) filtered out before
sampling — see `research/golden_set_sampling.md`. So most examples you
see should NOT need exclusion; if you find yourself excluding more
than a few out of 25, note that in `annotator_notes` on the batch as a
whole, since it may mean the pre-filter needs revisiting (that's
useful calibration signal, not a labeling error on your part).

If a message is a genuine, interpretable request but truly doesn't fit
any of the 8 intents, use `primary_intent: OTHER_UNKNOWN` with
`excluded: false` instead — reserve `excluded: true` for messages that
aren't real labelable requests at all, per the table above.

---

## 6. How to handle non-English messages

1. Set `non_english: true` if the message is not (primarily) in
   English, regardless of whether you can still figure out the intent.
2. If you can still determine the intent (e.g. you recognize enough of
   the language, or the intent is clear from context/cognates/emoji
   even without full translation) — label `primary_intent` normally
   and leave `excluded: false`.
3. If you genuinely cannot interpret it → `excluded: true`,
   `exclusion_reason: non_english_uninterpretable`.
4. Don't machine-translate the message yourself as part of labeling —
   if translation would be needed to label confidently and you can't do
   it reliably, that's case 3, not a reason to guess.

This dataset was measured to be ~99.4% English overall
(`docs/DATA.md`), so non-English examples should be uncommon in the
calibration batch, but the sampling pipeline did not filter them out —
see `research/golden_set_sampling.md`'s `flag_non_english_suspected`
note (that flag exists in the full metadata file but is intentionally
**not** shown to you in the blind calibration/annotation files, so your
`non_english` judgment is independent, not primed by a heuristic).

---

## 7. Why brand responses must not be consulted

The calibration and annotation files contain **only** the customer's
message — never the brand's reply, and never the rest of the
conversation. This is deliberate, for two reasons:

1. **It matches the real inference-time task.** The eventual system
   must classify a customer's intent *before* any response exists —
   showing the brand's historical reply during labeling would let you
   "cheat" by reading the answer, producing labels that don't reflect
   what's actually determinable from the customer's message alone, and
   that would make the golden set unrepresentative of the classifier's
   real operating conditions.
2. **It avoids circularity in evaluation.** If the retrieval/generation
   side of the eventual system is itself built from these brands'
   historical replies, then labeling intents by looking at those same
   replies would let information leak from the resolution side into
   the evaluation labels — inflating apparent quality without the
   system actually having done the work. Keeping intent labels
   response-blind keeps the evaluation honest.

If a brand's reply happens to be visible to you through some other
means (e.g. you recognize the tweet from earlier project work), ignore
it and label from the customer message text alone.

---

## 8. Why this dataset must remain separate from training/development data

Per CLAUDE.md's project rules and `docs/GOLDEN_SET.md`:

- This is an **evaluation** set, meant to measure the eventual system's
  real performance on held-out examples. If any of these 200 examples
  (or their labels) end up inside the retrieval corpus, a few-shot
  prompt, or any training/tuning data used to build the system, the
  evaluation stops being a fair test — the system would effectively be
  "graded on the answer key," and any reported accuracy/quality number
  becomes misleading (this is exactly the kind of caveat CLAUDE.md
  requires under "what is misleading about my headline number").
- This is also why the golden set is stored under `data/golden/`,
  separate from `data/retrieval/`, per the project's data-storage
  convention, and why `docs/GOLDEN_SET.md` explicitly calls out that
  golden-set examples must never leak into the retrieval corpus.
- Practically: once you label the calibration batch (and later the
  full 200), do not use these labeled examples to write few-shot
  prompt examples, fine-tune anything, or hand-tune retrieval/ranking
  logic against them. If a labeled example is used for any of that, it
  must be removed from the evaluation set, not kept in both roles.

---

## Calibration-specific note

This is a **calibration** batch, not the full labeling pass. Its
purpose is to catch taxonomy ambiguities, unclear instructions, or
labeling-guide gaps *before* committing to labeling all 200 — expect
to revise this guide (not the taxonomy itself, per this phase's
instructions) based on what calibration surfaces. Please over-document
uncertainty in `annotator_notes` during calibration rather than
under-document it; the goal right now is to find problems, not to
produce a clean-looking batch.
