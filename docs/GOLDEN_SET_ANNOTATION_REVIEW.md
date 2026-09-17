# Golden Set — Full 200-Example Annotation Review

## Status

All 200 golden-set candidates are now annotated:
- 25 examples labeled by the human annotator in the calibration batch
  (`data/golden/golden_calibration_annotations.jsonl`) — preserved
  **exactly as-is**, unmodified.
- 175 remaining examples newly annotated for this phase, reading each
  `customer_message` directly and applying `docs/INTENTS.md` plus the
  tie-break rules specified for this task. No sampling metadata, brand
  response, or external LLM/API call was used to produce any label.

Combined output: `data/golden/golden_set_annotations.jsonl` (200
records). `data/golden/golden_set_candidates.jsonl` was read only, not
modified.

---

## Validation results

All checks below were run programmatically against the final 200-row
file:

| Check | Result |
|---|---|
| Exactly 200 unique examples | PASS |
| Exactly the original 25 calibration IDs preserved | PASS |
| Exactly 175 new annotations added | PASS |
| No duplicate example IDs | PASS |
| Every ID exists in `golden_set_candidates.jsonl` | PASS |
| Every `primary_intent` is canonical (or `null` only when `excluded=true`) | PASS |
| Every non-null `secondary_issue` in the **175 new** records is canonical | PASS |
| `ambiguous` / `non_english` / `excluded` are real JSON booleans | PASS |
| `excluded=true` always has an `exclusion_reason` (and vice versa) | PASS |
| No sampling metadata (`sampling_group`, `target_intent_hint`, author/flags) in output | PASS |
| `customer_message` preserved exactly (matches candidates file) for all 200 | PASS |
| The original 25 records are field-for-field unchanged | PASS |

**One known, deliberately-not-fixed exception**: 7 of the original 25
calibration records have non-canonical `secondary_issue` values (bare
digit strings like `"1"`, `"7"` — intent-menu shorthand rather than a
canonical string), already documented as a finding in
`docs/GOLDEN_CALIBRATION_REVIEW.md`. Per this task's explicit
instruction not to modify the original 25 records, these were left
untouched rather than "fixed." All 175 new records use full canonical
strings as instructed.

---

## Primary-intent distribution (200 total)

| Intent | Count |
|---|---|
| App & Playback Technical Issues | 37 |
| Premium Subscription & Billing | 32 |
| Feature Request & Product Feedback | 30 |
| Content Availability & Catalog Accuracy | 29 |
| Account Security | 23 |
| Account Access & Login | 16 |
| Country/Market Availability Inquiry | 13 |
| OTHER / UNKNOWN | 7 |
| General Complaint / Service Dissatisfaction | 4 |
| (excluded — no primary_intent) | 9 |
| **Total** | **200** |

Note: this reflects the golden set's designed composition (Group A
natural-distribution random sample + Group B deliberate oversampling
of Account Access & Login, Account Security, Country/Market
Availability, and General Complaint — see `docs/GOLDEN_SET.md`), not
natural SpotifyCares traffic proportions. Account Security and
Country/Market Availability look larger here than their ~4%/~1%
natural rates (`docs/INTENTS.md`) specifically because Group B
oversampled them; General Complaint looks smaller than its Group-B
target (4 here vs. 20 candidates drawn) because many "General
Complaint" *candidates* turned out, on actual reading, to contain an
extractable concrete ask and were relabeled to Feature Request, App
Technical, etc. per the tie-break rules — see "Recurring taxonomy
ambiguities" below.

## Other reported statistics

| Field | Count (of 200) |
|---|---|
| `ambiguous = true` | 23 (all in the new 175; the original 25 had 0, per `docs/GOLDEN_CALIBRATION_REVIEW.md`) |
| `non_english = true` | 2 (1 from the original 25 — Turkish; 1 new — Indonesian, GOLD-0042) |
| `excluded = true` | 9 (all in the new 175) |
| `secondary_issue` non-null | 36 (7 from the original 25 — numeric shorthand; 29 from the new 175 — canonical strings) |

### Exclusion reasons (9 total, all new)

| Reason | Count |
|---|---|
| `dm_followup_no_issue` | 3 |
| `fragment` | 3 |
| `off_topic` | 2 |
| `praise_only` | 1 |

---

## 20 hardest new examples and their rationales

Selected from the 23 `ambiguous=true` new examples, dropping 3 that
were near-duplicates of another example already on this list (two more
"vague, no-detail account help" messages functionally identical to
GOLD-0012, and one more CSRF-token-error message functionally
identical to GOLD-0010).

1. **GOLD-0003** — `"Any update on this very common customer request? ... [link]"` → **OTHER / UNKNOWN**. The actual request is only visible in an unfollowed image/link; the text alone gives no basis for any of the 8 intents.
2. **GOLD-0010** — `"your forgot password form is broken / The CSRF token is invalid."` → **App & Playback Technical Issues**. This task's tie-break routes an explicit technical malfunction (broken form, CSRF error) to App Technical — but `docs/INTENTS.md`'s own Account Access & Login section lists this near-identical wording as its representative example. Direct conflict between the taxonomy doc and the tie-break rule given for this task; see "Recurring taxonomy ambiguities" below.
3. **GOLD-0012** — `"having trouble with my account that I can't resolve using the FAQs online"` → **OTHER / UNKNOWN**. Genuine request, zero specifics (not login, not billing, not security named).
4. **GOLD-0027** — `"randomly connect to the webplayer and play some random playlists you've never heard before"` → **App & Playback Technical Issues** (secondary: Account Security). Casual tone suggests a device-sync bug, but `docs/INTENTS.md`'s Account Security include list literally names "unrecognized listening activity" as a compromise signal — this message is exactly that, without the alarm.
5. **GOLD-0040** — `"are u guys going to release a fix for this issue soon? [link]"` → **OTHER / UNKNOWN**. Same problem as GOLD-0003: the actual bug is only in an unseen image.
6. **GOLD-0052** — Hulu login error within the Spotify+Hulu bundle → **App & Playback Technical Issues** (secondary: Premium Subscription & Billing). An explicit error message points to Technical per the tie-break, but the context is squarely a billing-bundle integration.
7. **GOLD-0061** — `"petition to @115888 to add running on dua's musics"` → **Content Availability & Catalog Accuracy**. Genuinely garbled grammar; most plausible reading is a specific-artist content request, but confidence is low.
8. **GOLD-0065** — Can't connect Facebook after reinstalling the app on two devices → **Account Access & Login** (secondary: App & Playback Technical Issues). No named error/bug favors Access per the tie-break, but the reinstall-across-devices troubleshooting looks exactly like a technical-bug response elsewhere in this batch.
9. **GOLD-0081** — `"made a mistake I think we're not speaking about the same amber [link]"` → **OTHER / UNKNOWN**. Likely a metadata/identity mix-up, but too vague and link-dependent to classify with confidence.
10. **GOLD-0087** — Someone created a *new* account under the customer's email without consent → **Feature Request & Product Feedback** (secondary: Account Security). Doesn't cleanly fit Account Security's "account was compromised" definition (no existing account was taken over); the concrete ask ("make registration more rigorous") is a process-capability request, but the underlying trigger is genuinely security-adjacent.
11. **GOLD-0110** — Asking about update timing for an official curated playlist → **Content Availability & Catalog Accuracy**. Soft fit — it's about *when* existing content updates, not missing/incorrect content per se.
12. **GOLD-0119** — Likely an artist-account message: `"why did our related artists section just get wiped?"` → **Content Availability & Catalog Accuracy**. Could equally be read as an App Technical data-loss bug; leaned Catalog given the metadata-like nature of a "related artists" listing.
13. **GOLD-0126** — Logged out, then told "email doesn't exist" during password reset → **App & Playback Technical Issues** (secondary: Account Access & Login). An objectively wrong system response for a real user reads as a bug, but shares the exact shape of several Account Access cases in this batch.
14. **GOLD-0128** — Satirical complaint about a "sexist" signup gender field → **Feature Request & Product Feedback**. Read generously there's an implicit inclusivity ask, but the joking/satirical framing makes genuine intent hard to pin down — could plausibly be General Complaint or off-topic humor instead.
15. **GOLD-0129** — Login blocked by a post-relocation country mismatch, can't change country in Settings → **Account Access & Login** (secondary: Feature Request & Product Feedback). Symptom is a login block (favors Access), but the real underlying need is a settings capability that doesn't exist.
16. **GOLD-0134** — Student-account signup fails with "credentials have been used" → **Account Access & Login** (secondary: Premium Subscription & Billing). Blocking symptom is a signup/credential error, but the context is specifically a student billing plan.
17. **GOLD-0139** — Google Home Mini integration won't let the customer pick a different linked Google account → **App & Playback Technical Issues** (secondary: Account Access & Login). Shaped like the CSRF-token cases resolved toward Technical, but is also plausibly a credential/account-selection issue.
18. **GOLD-0157** — Linked Facebook account was hacked, cascading into inability to access/cancel the Spotify subscription → **Account Security** (secondary: Premium Subscription & Billing). Multi-layered: is it the FB account or the Spotify account that's "compromised" per the taxonomy's definition? Led with the hacking claim per the first-stated-issue rule.
19. **GOLD-0183** — `"Have an issue with my account security... I need a response"` → **Account Security**. The customer explicitly self-labels the category but gives zero supporting detail — labeled by taking their own word for it, flagged for review since nothing corroborates it.
20. **GOLD-0189** — `"you did charge my account 2 days ago so i know that's not the problem"` → **OTHER / UNKNOWN**. Reads as a reply ruling out billing as the cause of some other, unstated problem — the actual issue is never named in this message.

---

## Recurring taxonomy ambiguities

Patterns that came up repeatedly across the 175, not just as one-off
hard cases:

1. **The CSRF-token/broken-form pattern directly contradicts a
   documented representative example.** `docs/INTENTS.md`'s Account
   Access & Login section lists "I was logged out... 'The CSRF token
   is invalid'" as its own representative example — but this task's
   tie-break rule ("technical/UI/app malfunction causing inability to
   log in → App & Playback Technical Issues") routes the same wording
   to Technical instead. This pattern recurred at least 3 times in the
   175 (GOLD-0010, GOLD-0124, and the error-code variants GOLD-0069/
   GOLD-0123). All were labeled App & Playback Technical Issues per
   the explicit tie-break given for this task, but `docs/INTENTS.md`
   should be updated to either change its representative example or
   add this exact distinction, so future annotators aren't following
   two documents that disagree.
2. **"Unrecognized activity" vs. "device/technical glitch."**
   `docs/INTENTS.md`'s Account Security include list names
   "unrecognized listening activity/library changes" as a compromise
   signal, but several messages describe exactly that in a casual,
   non-alarmed tone consistent with an ordinary sync bug (GOLD-0027).
   No tie-break rule distinguishes "worried this might be a hacker" 
   from "huh, weird glitch" when the described symptom is identical.
3. **"Switching to a competitor" as a secondary issue, applied
   inconsistently in the original 25 (per `docs/GOLDEN_CALIBRATION_REVIEW.md`),
   now applied uniformly in the new 175.** Every message in this batch
   that both (a) named a specific existing platform limitation/policy
   and (b) threatened to switch competitors was labeled with the named
   limitation as primary (Feature Request or App Technical, whichever
   fit) and General Complaint as secondary — e.g. GOLD-0182, 0188,
   0190–0195, 0197, 0200. Messages with **no** named limitation at all
   (just an announcement of switching, e.g. GOLD-0198) were labeled
   General Complaint alone. This is a deliberate, consistent policy
   decision for this pass, but it is a judgment call, not something
   `docs/INTENTS.md` states explicitly — worth codifying as an
   explicit rule if this taxonomy is used again.
4. **Card/payment fraud vs. account compromise remains a live
   boundary even with the new explicit tie-break.** The rule "Credit-
   card/payment fraud without evidence the Spotify account itself was
   compromised → Billing" resolved most cases cleanly (e.g. GOLD-0075,
   GOLD-0106, GOLD-0112, GOLD-0149), but GOLD-0157 shows a case the
   rule doesn't fully cover: the *linked Facebook account* (not the
   card, not confirmed to be the Spotify account itself) was hacked,
   which is neither of the rule's two clean categories.
5. **Underspecified "account" messages** (GOLD-0012, GOLD-0029,
   GOLD-0072, and similar) are common enough (3+ in this batch alone)
   that they may deserve their own explicit handling rule rather than
   defaulting to OTHER/UNKNOWN case-by-case — e.g. a documented
   default policy for "names a category word only, no other detail."
6. **Link/image-dependent messages** (GOLD-0003, GOLD-0040, GOLD-0078,
   GOLD-0081, GOLD-0116) where the actual substance is only visible in
   an unfollowed image are common in this dataset (5 in the new 175
   alone). Two different treatments were applied depending on how much
   surrounding text existed: OTHER/UNKNOWN (excluded=false) when there
   was a real sentence of context; excluded/fragment when the text was
   just a bare reaction. This split is defensible but was applied by
   judgment call each time, not by a documented rule.

---

## Examples that should receive human review

Beyond the 20 hardest cases already listed above (all of which are
reasonable candidates for review), these stand out as the highest
priority:

- **GOLD-0010, GOLD-0124** (and the shape shared by GOLD-0069,
  GOLD-0123) — because they directly contradict `docs/INTENTS.md`'s
  own stated representative example, a human should confirm whether
  the taxonomy doc or the tie-break rule is the one that should change,
  rather than leaving both authoritative documents in disagreement.
- **GOLD-0087** — genuine account-security-adjacent fraud (identity
  misuse at signup) that doesn't fit any of the 9 canonical intents
  particularly well; worth deciding whether this should be folded into
  Account Security's definition explicitly.
- **GOLD-0128** — satirical/joke framing makes the actual intent
  genuinely uncertain; a second reader's take would help calibrate
  whether Feature Request was too generous a reading.
- **GOLD-0151** (excluded, `off_topic`) — describes a third party's
  (the customer's brother's) account, told humorously; worth
  double-checking the exclusion call is right rather than, say,
  OTHER/UNKNOWN.
- **GOLD-0042** — the one non-English new example (Indonesian);
  translation confidence is moderate, not high, and a fluent reviewer
  should confirm the App Technical label.
- **The 7 pre-existing non-canonical `secondary_issue` values in the
  original 25** (GOLD-0017, 0018, 0140, 0159, 0174, 0179, 0196) — not
  fixed here per instruction, but still need a decision (accept as
  numeric shorthand permanently, or have the original annotator
  re-enter them as phrases) before this file is treated as final.

---

## Summary

200/200 examples now carry a documented label or an excluded status,
each with a written rationale for the 175 new ones. No annotation used
sampling metadata, brand responses, or an external classifier/LLM —
every label traces to the customer message text plus the documented
taxonomy and tie-break rules. The clearest actionable follow-up is
resolving the CSRF-token-pattern conflict between `docs/INTENTS.md`'s
representative example and this task's tie-break rule, since it
recurred multiple times and currently leaves two authoritative
documents disagreeing with each other.
