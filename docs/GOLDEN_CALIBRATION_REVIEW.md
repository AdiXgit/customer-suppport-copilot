# Golden Set Calibration Batch — Review

## Status

Review of the completed 25-example human-labeled calibration batch
(`data/golden/golden_calibration_annotations.jsonl`) against
`docs/INTENTS.md` and `docs/GOLDEN_ANNOTATION.md`. This is a **review
only** — no annotation values were changed, no example was relabeled,
and the annotation file was not modified.

---

## 1. Schema validity

**Valid.** All 25 records contain exactly the 10 expected fields
(`example_id`, `customer_message`, `primary_intent`, `secondary_issue`,
`ambiguous`, `non_english`, `excluded`, `exclusion_reason`,
`annotator_notes`, `label_timestamp`), matching the annotation script's
output schema. No missing or unexpected keys. `example_id`s are all
unique and all match the original 25-example calibration batch (no
substitutions). `customer_message` text was spot-checked against the
original blind batch file and is preserved verbatim.

## 2. All 25 examples completed

**Confirmed — 25/25.** Every record has a non-null `primary_intent`
and `excluded: false`. No record is missing a label, and none needed
the exclusion path.

## 3. Valid taxonomy labels

**Valid.** All 25 `primary_intent` values exactly match one of the 9
canonical strings from the annotation script's menu (the same 9
defined in `docs/INTENTS.md`): no typos, no free-text variants, no use
of a label outside the taxonomy. `OTHER / UNKNOWN` was not used by any
example in this batch.

**Documentation nit (not a data error):** `docs/GOLDEN_ANNOTATION.md`
refers to the taxonomy's second intent as "Account Security
(Unauthorized Access)" and to the catch-all as `OTHER_UNKNOWN`, while
the actual canonical stored strings (and the annotation script's menu)
are `"Account Security"` and `"OTHER / UNKNOWN"`. This batch's
annotations correctly used the canonical short forms, so no example is
affected — but the doc's longer/underscored variants should be aligned
to the canonical strings before the full 200-example pass, to avoid a
future annotator typing a slightly different string by hand.

## 4. Valid boolean fields

**Valid.** `ambiguous`, `non_english`, and `excluded` are all true JSON
booleans (not strings) in every record. Values observed: `ambiguous`
is `false` for all 25; `non_english` is `true` for exactly 1
(GOLD-0051) and `false` for the rest; `excluded` is `false` for all 25.
`exclusion_reason` is `null` in every record, which is consistent
(never set without `excluded: true`, and never missing when it should
be set — since `excluded` is always `false` here).

## 5. Valid secondary_issue values

**Format inconsistency found.** 7 of 25 records have a non-null
`secondary_issue`, but all 7 are bare digit strings —
`"1"`, `"2"`, `"3"`, `"7"`, `"8"` — rather than the short descriptive
phrase specified in `docs/GOLDEN_ANNOTATION.md` §1a ("note the other
one in `secondary_issue` as a short phrase"). These numbers line up
exactly with the 1–9 positions of the primary-intent menu (e.g. `"1"`
= Account Access & Login, `"7"` = General Complaint, `"8"` =
Country/Market Availability), so they are almost certainly intended as
intent-menu shorthand rather than arbitrary or invalid input — decoded
that way, every one of the 7 is a defensible secondary intent for its
message (details in §6). This is a genuine **format** deviation from
the documented instruction, not a corrupted or meaningless value.
Recommend clarifying in the annotation guide (before the full 200-pass)
whether numeric shorthand is acceptable or whether a phrase is
required, so the field is consistent either way.

| example_id | secondary_issue (raw) | Decoded (by menu position) |
|---|---|---|
| GOLD-0018 | `"1"` | Account Access & Login |
| GOLD-0196 | `"7"` | General Complaint / Service Dissatisfaction |
| GOLD-0159 | `"2"` | Account Security |
| GOLD-0179 | `"3"` | Premium Subscription & Billing |
| GOLD-0174 | `"8"` | Country/Market Availability Inquiry |
| GOLD-0017 | `"1"` | Account Access & Login |
| GOLD-0140 | `"1"` | Account Access & Login |

## 6. Inconsistencies with the documented taxonomy / tie-break rules

Most of the batch applies `docs/INTENTS.md` and the
`docs/GOLDEN_ANNOTATION.md` §3 tie-break rules correctly and
defensibly — including several textbook applications (e.g. GOLD-0056
and GOLD-0199 for Apple Watch platform requests almost verbatim match
the Feature Request representative examples; GOLD-0174 correctly
applies the Content-Availability-vs-Country/Market tie-break rule by
keeping a region-specific song complaint under Content Availability
rather than Country/Market). Two things stood out:

1. **GOLD-0179 secondary_issue is weakly grounded.** The message
   ("...waaaay better than other paid services. Please come to India,
   I'd love to pay for your services.") contains praise and a
   Country/Market request, but no stated billing problem — "I'd love
   to pay" expresses willingness, not a payment issue. Tagging
   secondary_issue as Billing (`"3"`) doesn't map to anything in
   `docs/INTENTS.md`'s Premium & Billing **Include** list. This isn't
   necessarily wrong (a generous reading is "expresses purchase
   intent, which is billing-adjacent"), but it's the one secondary tag
   in the batch that doesn't clearly follow the "short phrase
   describing a genuine second issue" instruction.
2. **Uneven use of `secondary_issue` on similarly-shaped messages.**
   Several other messages have the same "specific ask + complaint/
   comparison aside" shape that got a secondary tag elsewhere in the
   batch (e.g. GOLD-0196, GOLD-0159) but did not receive one:
   GOLD-0199 ("...timetable for an Apple Watch app? **Considering
   switching to Apple Music** if there is no news.") contains a
   competitor-switching comparison — which `docs/INTENTS.md` lists
   verbatim under General Complaint's **Include** bullet — with no
   `secondary_issue` recorded; GOLD-0107 ("payment failed... **I think
   actually spotify not working**") has a plausible secondary App
   Technical reading with no tag. Not incorrect (the field is
   optional, and primary labels for both are defensible per §6 of this
   review's own analysis), but the two treatments aren't applied with
   the same threshold.

No example was found where the **primary** intent contradicts
`docs/INTENTS.md`'s Include/Exclude rules or the documented
tie-breakers — every primary label traces to a specific rule or
representative example in one of the two documents.

## 7. Genuinely ambiguous examples

The annotator marked `ambiguous: false` for all 25 examples. Reviewing
against the taxonomy, two examples look like defensible candidates for
`ambiguous: true` that weren't flagged that way:

- **GOLD-0159** — "credit card hacked called you and reported Oct 23
  still charging my card need support..." — labeled Premium & Billing
  (secondary: Account Security). The word "hacked" is the taxonomy's
  own stated signal for Account Security elsewhere in the guide, but
  here it describes the *credit card* being hacked/defrauded rather
  than the *Spotify account* being compromised (Account Security's
  definition is specifically "account was compromised"), and the
  customer's actual ask is about the ongoing charge. Neither
  `docs/INTENTS.md` nor the §3 tie-break rules directly address
  "hacked card, not hacked account" — a reasonable annotator could
  defend either Billing or Account Security as primary. This looks
  like real taxonomy-boundary ambiguity, not an annotation error.
- **GOLD-0140** — "...super cool that you can play videos on the
  background of the login screen, but the login buttons don't work." —
  labeled App & Playback Technical Issues (secondary: Account Access &
  Login). This is a UI/button malfunction (fits App Technical's
  "missing UI elements/buttons that should be present" Include
  bullet) whose *effect* is that the customer cannot log in (fits
  Account Access & Login's core definition). No documented tie-break
  rule distinguishes "a technical bug whose symptom is being locked
  out" from "a login problem." Also a defensible boundary case either
  way.

Both examples already have a recorded `secondary_issue` that points at
the other plausible label, so the annotator's underlying judgment is
visible in the data even without `ambiguous: true` — but per
`docs/GOLDEN_ANNOTATION.md` §4 ("Set `ambiguous: true` when you can
defend two different primary-intent choices... and neither the
tie-breaking rules... settle it"), these two arguably qualify. This is
useful calibration signal: the taxonomy may benefit from an explicit
tie-break rule for "account-adjacent fraud that isn't account
compromise" and for "a technical bug whose only symptom is inability
to log in," before the full 200-example pass.

No other example in the batch showed comparable boundary ambiguity;
the remaining 23 primary labels are each traceable to an unambiguous
Include bullet or an explicit tie-break rule.

---

## Reported statistics

### Primary-intent distribution (25 total)

| Intent | Count |
|---|---|
| Premium Subscription & Billing | 7 |
| Account Security | 5 |
| App & Playback Technical Issues | 4 |
| Feature Request & Product Feedback | 4 |
| Content Availability & Catalog Accuracy | 3 |
| General Complaint / Service Dissatisfaction | 1 |
| Country/Market Availability Inquiry | 1 |
| Account Access & Login | 0 |
| OTHER / UNKNOWN | 0 |
| **Total** | **25** |

Note: this calibration batch is a mix of Group A (natural-distribution
random) and Group B (deliberately oversampled Account Access & Login,
Account Security, General Complaint, Country/Market Availability)
examples per `docs/GOLDEN_SET.md` — so this small distribution should
**not** be read as an estimate of natural SpotifyCares traffic
proportions. Notably, Account Access & Login has zero examples in this
particular 25-example slice despite being one of the four intents
Group B specifically oversampled — worth watching once the full
Group B allocation (20 candidates) is labeled, rather than concluding
anything from this batch alone.

### Other fields

| Field | Count (of 25) |
|---|---|
| `ambiguous = true` | 0 |
| `non_english = true` | 1 (GOLD-0051, Turkish) |
| `excluded = true` | 0 |
| `secondary_issue` non-null | 7 |

---

## Summary for calibration follow-up

- No schema, boolean-validity, or taxonomy-label errors — the batch is
  mechanically clean and ready to inform process decisions.
- The `secondary_issue` field needs a clarified format (phrase vs.
  menu-number shorthand) before the full 200-example pass — currently
  usable (it decodes unambiguously against the menu) but inconsistent
  with the written instruction.
- Two examples (GOLD-0159, GOLD-0140) surface real taxonomy boundary
  gaps — not "someone else's account hacked" but "my card was
  hacked/defrauded," and "a UI bug that manifests as being logged
  out." Consider adding explicit tie-break guidance for these before
  scaling up, rather than leaving each annotator to guess.
- Zero use of `ambiguous` or `annotator_notes` across all 25 examples
  is worth noting given the calibration guide's explicit request to
  "over-document uncertainty" — either this batch was genuinely
  unambiguous throughout except for the two boundary cases above, or
  those fields were under-used relative to what calibration is meant
  to surface. Not a defect, just a process observation for the next
  round.

No taxonomy changes and no annotation edits were made as part of this
review.
