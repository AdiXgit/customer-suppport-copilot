# SpotifyCares Intent Taxonomy — Final Labeling Contract

## Status

**FINALIZED (Phase 6D)**, for the intent-classification labeling
policy only. This is the canonical, concise reference for how to
assign a primary intent to a SpotifyCares customer message. Full
definitions, evidence, and rationale live in `docs/INTENTS.md`
(taxonomy) and `docs/GOLDEN_ANNOTATION.md` (practical labeling
instructions); this document distills both into one contract.

**IMPORTANT — this contract has NOT been applied retroactively.** The
existing 200-example golden set (`data/golden/golden_set_annotations.jsonl`)
was labeled under an earlier, less precise version of the Account
Access & Login vs. App & Playback Technical Issues tie-break rule. Per
`docs/TAXONOMY_CONFLICT_REVIEW.md`, at least one example (GOLD-0126)
would flip under this finalized contract, and two more (GOLD-0065,
GOLD-0052) would need re-examination. **The golden set has NOT been
relabeled.** Applying this contract to the existing 200 examples is a
separate, not-yet-scheduled task.

---

## The 9 intents

1. **Account Access & Login** — can't log in, register, or reset a
   password; no third party implicated, no technical malfunction
   evidenced.
2. **Account Security** — account reported hacked, compromised, or
   used without authorization.
3. **Premium Subscription & Billing** — anything about paying for,
   changing, or being charged for Premium, including family/student
   plans, promo pricing, payment methods, and billing disputes.
4. **App & Playback Technical Issues** — the app/site/device is
   malfunctioning: crashes, freezes, playback errors, sync/data-loss
   bugs, or a technical login/access failure (see tie-break below).
5. **Content Availability & Catalog Accuracy** — a specific song,
   album, artist, or podcast is missing, removed, region-restricted, or
   mislabeled.
6. **Feature Request & Product Feedback** — wants a capability that
   doesn't exist, wants existing behavior changed, or gives product
   feedback with an extractable, specific ask.
7. **General Complaint / Service Dissatisfaction** — frustration or
   dissatisfaction with no specific, actionable, fixable request.
8. **Country/Market Availability Inquiry** — whether the Spotify
   service itself (not specific content) is/will be available in a
   country.
9. **OTHER / UNKNOWN** — a genuine, interpretable request that still
   doesn't fit any of the 8 above. Reserve for cases where nothing
   else applies — most non-fitting messages should be excluded
   instead (see below), not forced into this bucket.

Full Definition / Include / Exclude / representative examples for each
are in `docs/INTENTS.md`.

---

## Primary labeling rule

1. Read only the customer's message. Never consult the brand's
   historical reply, sampling metadata, or any other source.
2. Decide first whether the message is a genuine, interpretable
   support request at all (see "Exclusion rule" below). If not,
   exclude it rather than forcing a label.
3. If it is, find the single best-matching intent using each
   candidate intent's Definition/Include/Exclude in `docs/INTENTS.md`
   — not just the one-line name.
4. If two intents both plausibly apply, use the specific tie-break
   rules below, in order. If a case isn't covered by any tie-break
   rule, use the general principle: **the primary label is the main,
   first-stated, most concrete/actionable issue** in the message.

---

## Account Access & Login vs. App & Playback Technical Issues — the finalized tie-break

The one tie-break this phase specifically resolved (see
`docs/TAXONOMY_CONFLICT_REVIEW.md` for the full investigation that
produced it). For any message reporting trouble logging in,
registering, or resetting a password, check in order:

| # | Does the message contain... | → |
|---|---|---|
| 1 | A verbatim **developer-facing technical identifier** (HTTP status code, internal token/parameter name, exception-style string) | **App & Playback Technical Issues** |
| 2 | A description of a **broken/non-functional UI element or app behavior itself**, not just a rejection outcome | **App & Playback Technical Issues** |
| 3 | Described **troubleshooting behavior** the customer already tried (reinstall, clear cache, restart, different browser) | **App & Playback Technical Issues** |
| — | **None of the above** — only a plain-language credential rejection or a bare "can't log in" | **Account Access & Login** |

Stop at the first criterion that matches. A referenced-but-unshown
error ("error message below," link only, no text) does **not** satisfy
criterion 1.

**Account Access & Login** = access/credential problem, no evidence of
a product/UI/technical fault. **App & Playback Technical Issues** =
requires actual evidence of malfunction per criteria 1–3 above, not
merely a login-shaped symptom.

---

## Multi-issue rule

When a message raises more than one genuine issue: `primary_intent` =
the main/first-stated issue; `secondary_issue` = the other genuine
issue, given as the full canonical intent string (never a number,
never a paraphrase). Use `secondary_issue: null` when there is no
genuine second issue — do not invent one to fill the field.

---

## Ambiguity rule

Set `ambiguous: true` when two primary-intent choices remain genuinely
defensible **after** applying the documented tie-break rules — i.e.
you made a real judgment call, not just followed a rule. Still supply
your best `primary_intent`; `ambiguous` is a review flag, not a
substitute for a label. Do not mark ambiguous just because a message is
angry, garbled, or multi-sentence — only when the intent classification
itself is unsettled.

---

## OTHER / UNKNOWN rule

Use `OTHER / UNKNOWN` (with `excluded: false`) only for a genuine,
interpretable request that still doesn't fit any of the 8 named
intents. If the message isn't a genuine support request at all
(praise-only, off-topic, promotional, a bare fragment, a DM-follow-up
with no visible original issue), set `excluded: true` with a specific
`exclusion_reason` instead — do not label it OTHER/UNKNOWN.

## Exclusion rule

`excluded: true` requires a non-null `exclusion_reason`. Standard
reasons: `praise_only`, `off_topic`, `fragment`, `dm_followup_no_issue`,
`unstated_dispute`, `non_english_uninterpretable`.

## Non-English rule

1. If the message is understandable (even imperfectly) → label its
   intent normally, set `non_english: true`.
2. If genuinely uninterpretable without translation → `excluded: true`,
   `exclusion_reason: non_english_uninterpretable`, `non_english: true`.
3. Never machine-translate as part of labeling; if translation would be
   required to label confidently and can't be done reliably, that's
   case 2.

---

## 8 short examples of borderline cases

1. **"it says my password is invalid"** → **Account Access & Login**
   (plain-language rejection, no technical identifier — criteria 1–3
   all fail).
2. **"the CSRF token is invalid"** → **App & Playback Technical
   Issues** (criterion 1: verbatim technical identifier).
3. **"the login buttons don't work"** → **App & Playback Technical
   Issues** (criterion 2: broken UI element).
4. **"I cleared cache, uninstalled, reinstalled — now I can't log
   in"** → **App & Playback Technical Issues** (criterion 3:
   troubleshooting behavior), even with no named error code.
5. **"why isn't [song] on Spotify"** vs. **"[song] won't play,
   getting an error"** → the first is Content Availability (named
   content, no bug language); the second is App & Playback Technical
   Issues (bug/error language, no specific missing-content claim).
6. **"please add a shuffle-order feature or I'm switching to Tidal"**
   → **Feature Request & Product Feedback** primary (concrete,
   extractable ask), **General Complaint / Service Dissatisfaction**
   secondary (competitor-switch threat) — not the reverse, because
   there's a specific actionable ask to act on.
7. **"just lost a customer, switching to Apple Music"** with no
   further detail → **General Complaint / Service Dissatisfaction**
   only (no named grievance to extract, nothing actionable).
8. **"why isn't Spotify available in Egypt"** vs. **"why isn't
   [album] available in Egypt"** → the first is Country/Market
   Availability Inquiry (whole service); the second is Content
   Availability & Catalog Accuracy (specific content), even though
   both mention a country.

---

## Golden-set status (repeated for emphasis)

The 200-example golden set at `data/golden/golden_set_annotations.jsonl`
was labeled under an earlier, unwritten version of the Account Access
vs. Technical distinction. **It has not been relabeled against this
finalized contract.** Known discrepancies, per
`docs/TAXONOMY_CONFLICT_REVIEW.md`:

- **GOLD-0126** would flip from App & Playback Technical Issues to
  Account Access & Login under this contract (criterion check: no
  criteria 1–3 met, only a plain-language "email doesn't exist"
  rejection).
- **GOLD-0065** and **GOLD-0052** would need re-examination (GOLD-0065
  has criterion 3 present — reinstalling on two devices — arguing for
  Technical primary rather than its current Access primary; GOLD-0052's
  referenced error is unshown/image-only, so it likely shouldn't have
  been called Technical with confidence).

Re-applying this contract to the existing 200 examples — and deciding
whether to correct these specific discrepancies — is a separate task,
not performed here.
