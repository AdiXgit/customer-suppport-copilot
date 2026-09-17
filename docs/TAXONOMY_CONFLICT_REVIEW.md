# Taxonomy Conflict Investigation: Account Access & Login vs. App & Playback Technical Issues

## Status

Investigation only. No labels changed, no files modified except this
one. `docs/INTENTS.md`, `docs/GOLDEN_ANNOTATION.md`, and
`data/golden/golden_set_annotations.jsonl` were read but not edited.
No external sources were used — every finding below is derived from
reading the four listed files.

---

## The conflict, restated precisely

`docs/INTENTS.md`'s **Account Access & Login** section lists this as
its own representative example:

> "I was logged out of my account and when I try to log in it doesn't
> work... 'The CSRF token is invalid'"

But the tie-break rule given for the annotation task that produced
`data/golden/golden_set_annotations.jsonl` states:

> "Technical/UI/app malfunction causing inability to log in → App &
> Playback Technical Issues"

A CSRF-token error is, on its face, exactly a "technical malfunction
causing inability to log in." So the two documents disagree on where
this exact pattern belongs: `docs/INTENTS.md`'s own example says
Account Access & Login; the tie-break rule used to build the golden
set says App & Playback Technical Issues. Every CSRF-token-shaped
message in the golden set was labeled App & Playback Technical Issues
per the tie-break rule (as instructed at the time), which means those
labels now contradict `docs/INTENTS.md`'s stated example.

---

## Method

Read every record in `data/golden/golden_set_annotations.jsonl` whose
`primary_intent` or `secondary_issue` is Account Access & Login or App
& Playback Technical Issues, and whose `customer_message` describes a
login, sign-in, password-reset, or account-access outcome. From that
set, separated:

- **Genuinely affected examples**: the message describes an access/
  login outcome *and* contains some technical-malfunction signal
  (an error code/token name, a described broken UI element, or
  described troubleshooting behavior) — these are where the two rules
  actually pull in different directions.
- **Clean comparators**: the message describes an access/login problem
  with **no** technical-malfunction signal at all (e.g., "forgot my
  password," "won't let me log in," no error text, no troubleshooting
  described) — these aren't in tension; both `docs/INTENTS.md` and the
  tie-break rule agree they're Account Access & Login, and they're
  listed here only to show what "no conflict" looks like by contrast.

---

## Affected examples

### 1. GOLD-0010

**customer_message**: `"@117168 your forgot password form is broken\n\nThe CSRF token is invalid. Please try to resubmit the form."`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: null (ambiguous=true)

**Relevant taxonomy rule/representative example**: `docs/INTENTS.md`
Account Access & Login lists "I was logged out... 'The CSRF token is
invalid'" as its own representative example — near-identical wording.

**Why the two rules conflict**: The message explicitly says the form
"is broken" and quotes a technical error string (CSRF token). The
task's tie-break rule reads this as a technical malfunction →
Technical. `docs/INTENTS.md`'s own example reads the same wording as
Account Access & Login.

**Which interpretation is better supported**: The tie-break rule's
literal wording ("technical malfunction causing inability to log in")
does describe this message accurately — a CSRF-token error is
unambiguously a system/technical fault, not a forgotten credential.
`docs/INTENTS.md`'s representative example looks more like it was
chosen to illustrate "a password-reset failure" generically, without
the author having deliberately weighed the malfunction-vs-credential
distinction. The tie-break rule is the more specific and more recently
deliberated instruction; the taxonomy doc's example looks like an
oversight rather than a considered position.

**Genuinely ambiguous?** Yes, and already flagged as such in the
annotation (`ambiguous: true`) — not because the message itself is
unclear, but because two authoritative documents disagree on how to
classify it.

---

### 2. GOLD-0124

**customer_message**: `"@SpotifyCares hi, I've been logged out of my premium account on both my iPhone & laptop. Trying to log back in but says my info is incorrect & when I try to reset password it says \"CSFR token invalid.\" Pls help I'm stressed !!!!!!!!"`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: null (ambiguous=true)

**Relevant taxonomy rule/representative example**: Same as GOLD-0010 —
same CSRF-token pattern, same direct conflict with `docs/INTENTS.md`'s
Account Access & Login representative example.

**Why the two rules conflict**: Identical reasoning to GOLD-0010.

**Which interpretation is better supported**: Same as GOLD-0010 — the
tie-break rule's technical-malfunction criterion is the better-reasoned
fit for a quoted system error string.

**Genuinely ambiguous?** Yes (already flagged).

---

### 3. GOLD-0002

**customer_message**: `"@SpotifyCares spotify at first said no internet connection even though I have one. I cleared cache, uninstalled, reinstalled. Now I can't log in. Changed Facebook password, nothing works. Help!"`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: null (ambiguous=false)

**Relevant taxonomy rule/representative example**: No single
representative example matches this exactly, but the underlying
tension is the same one: `docs/INTENTS.md` would plausibly read the
end state ("can't log in... changed password, nothing works") as
Account Access & Login, while the tie-break rule reads the described
troubleshooting (cache clear, uninstall/reinstall, a false "no
internet" error) as evidence of a technical malfunction.

**Why the two rules conflict**: The message names no specific error
code, but it does describe multiple rounds of technical troubleshooting
undertaken by the customer — behavior that, elsewhere in this same
golden set (see GOLD-0065 below), was treated as evidence *for*
Account Access, not Technical. This is an internal inconsistency, not
just a doc-vs-rule conflict.

**Which interpretation is better supported**: Technical, given the
false "no internet connection" error (itself a malfunction) preceding
everything else — but this was **not marked ambiguous** at labeling
time, despite being at least as boundary-shaped as GOLD-0065, which
was.

**Genuinely ambiguous?** Should probably have been flagged ambiguous;
it wasn't. Flagging here as a finding of this investigation.

---

### 4. GOLD-0065

**customer_message**: `"@SpotifyCares Hey guys. Can't connect Facebook with my Spotify account. Tried on two devices, reinstalled app, can't do it. Help :)"`

**Current primary_intent**: Account Access & Login
**Current secondary_issue**: App & Playback Technical Issues (ambiguous=true)

**Relevant taxonomy rule/representative example**: None directly, but
this is the mirror image of GOLD-0002 — reinstalling the app across
two devices is the same troubleshooting-behavior signal, yet this one
was labeled Account Access & Login (Technical only as secondary),
while GOLD-0002 was labeled Technical primary with no secondary at all.

**Why the two rules conflict**: The tie-break rule's "no described
malfunction" criterion for Account Access was applied here because no
specific error/code is named — but "reinstalled the app on two
devices" is exactly the kind of technical-remedy behavior that, in
GOLD-0002, was read as pointing toward Technical.

**Which interpretation is better supported**: Neither cleanly — this
is genuine boundary territory, correctly flagged `ambiguous: true`.
But its inconsistency with GOLD-0002's treatment (same signal, opposite
primary label) is itself evidence that the current tie-break rule is
underspecified about *what counts as* "a described technical
malfunction."

**Genuinely ambiguous?** Yes — already flagged, and correctly so.

---

### 5. GOLD-0069

**customer_message**: `"@115888 Im getting error 404 trying to login, I can login on the website but not through the app on my Iphone. Please help💚"`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: null (ambiguous=false)

**Relevant taxonomy rule/representative example**: No direct
representative example in either section, but shares the CSRF cases'
pattern — a quoted technical error code (404) causing a login failure.

**Why the two rules conflict**: Same tension as the CSRF cases in
miniature: a numeric HTTP-style error code vs. a login-outcome framing.

**Which interpretation is better supported**: Technical — an HTTP
error code is about as clean a "technical malfunction" signal as
exists in this dataset, and unlike GOLD-0002/GOLD-0065 there's no
ambiguity about whether troubleshooting behavior counts; the code
itself is the evidence.

**Genuinely ambiguous?** No — this one is comparatively clear, and was
correctly left unflagged.

---

### 6. GOLD-0123

**customer_message**: `"@115888 @116130 my account is no so secure that I can’t get into it - when I log in with Facebook it says error 404 and when I log in with the code Facebook sends me it says login failed 😣"`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: null (ambiguous=false)

**Relevant taxonomy rule/representative example**: Same 404-code
pattern as GOLD-0069.

**Why the two rules conflict**: Same reasoning as GOLD-0069 — a quoted
error code.

**Which interpretation is better supported**: Technical, for the same
reason as GOLD-0069.

**Genuinely ambiguous?** No.

---

### 7. GOLD-0121

**customer_message**: `"@spotifycares tried using my app this morning says I need to log in. Tried logging in, said PW invalid. Tried resetting PW, said username invalid"`

**Current primary_intent**: Account Access & Login
**Current secondary_issue**: null (ambiguous=false)

**Relevant taxonomy rule/representative example**: None directly, but
this is the clearest case of the *inconsistency* in how "error
messages" were treated across the batch: this message reports two
distinct rejection messages ("PW invalid," "username invalid") — text
that is structurally similar to GOLD-0069/GOLD-0123's quoted error
codes, yet was treated as an *ordinary validation response* rather than
a *technical malfunction* and labeled Account Access & Login.

**Why the two rules conflict**: If "the system told me something went
wrong" is enough to trigger the Technical tie-break (as it was for
error 404 and CSRF-token cases), this message should also be Technical.
If it isn't enough (because "password invalid" is a normal, expected
system response rather than evidence of a bug), then GOLD-0069's
"error 404" and GOLD-0123's "login failed" are arguably *also* just
normal system responses and shouldn't have been called technical
malfunctions either.

**Which interpretation is better supported**: Account Access & Login,
by the distinction this investigation proposes below (an HTTP status
code or an internal token name is a *developer-facing* technical
identifier; "password invalid" and "username invalid" are
*user-facing* plain-language messages, not evidence of a bug). But
that distinction was not written down anywhere before this message was
labeled — it was applied intuitively and inconsistently.

**Genuinely ambiguous?** Arguably yes; not flagged at labeling time.
Flagging here.

---

### 8. GOLD-0126

**customer_message**: `"@SpotifyCares Uh spotify, why did you just log me out then tell me my email doesn't exist when I try to reset my password?"`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: Account Access & Login (ambiguous=true)

**Relevant taxonomy rule/representative example**: Shares the same
"system tells the customer something false/wrong" shape as GOLD-0121,
but was resolved the opposite way.

**Why the two rules conflict**: The annotation reasoning called "told
me my email doesn't exist" (for a real, registered user) "an
objectively incorrect system response," treating the wrongness itself
as evidence of malfunction. But this is plain-language, user-facing
text — no error code, no token name, no described troubleshooting
behavior — structurally identical to GOLD-0121's "username invalid,"
which was labeled Account Access & Login instead.

**Which interpretation is better supported**: Account Access & Login,
by the same reasoning as GOLD-0121 — under a consistent
developer-facing-identifier-only standard, this message doesn't
qualify as Technical. The original call leaned Technical mainly
because the response was *factually wrong* for this user, which is a
different (and much harder to verify from message text alone) standard
than "does the message name a technical malfunction."

**Genuinely ambiguous?** Yes — already flagged, and this investigation
finds the current primary/secondary assignment should likely be
reversed under a clarified rule (see proposal below).

---

### 9. GOLD-0134

**customer_message**: `"@SpotifyCares I remember signing up for a student account with Spotify. Tried to redo sign up says credentials have been used"`

**Current primary_intent**: Account Access & Login
**Current secondary_issue**: Premium Subscription & Billing (ambiguous=true)

**Relevant taxonomy rule/representative example**: Same "system error
message" pattern again, this time correctly landing on Account Access
& Login under the plain-language-vs-technical-identifier distinction —
"credentials have been used" is a user-facing rejection message, not a
code or token name.

**Why the two rules conflict**: Included here as a **consistent**
application (contrast case) that helps validate the proposed rule
below — it shows the plain-language/technical-identifier distinction
was applied correctly at least once, even though it wasn't written
down as an explicit rule.

**Which interpretation is better supported**: Account Access & Login,
as labeled — this one doesn't actually need to change.

**Genuinely ambiguous?** The `ambiguous: true` flag here is about the
Access-vs-Billing boundary (student plan context), not the
Access-vs-Technical boundary — it's only tangentially related to this
investigation's specific conflict.

---

### 10. GOLD-0139

**customer_message**: `"got a new #googlehomemini and I need help linking @115888 account...My google mail is not the one with the premium spotify account, but the login isn't letting me choice a different mail :/ can't belive I'm the only one with that issue..."`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: Account Access & Login (ambiguous=true)

**Relevant taxonomy rule/representative example**: `docs/INTENTS.md`'s
App Technical include list names "smart-speaker integration problems"
explicitly — this is literally that.

**Why the two rules conflict**: The message describes the
device-linking *interface itself* not offering a needed option (choose
a different Google account) — a described UI/functional limitation,
not a credential rejection. That pushes toward Technical under
`docs/INTENTS.md`'s own include list. But the practical effect for the
customer is "I can't get into the right account," which is the Account
Access & Login definition's core framing.

**Which interpretation is better supported**: Technical — this is one
of the few cases in this set with clear direct textual support in
`docs/INTENTS.md` itself (the smart-speaker-integration include
bullet), not just an inferred malfunction.

**Genuinely ambiguous?** Yes, reasonably — the taxonomy doc supports
Technical strongly, but the customer's own framing centers on account
access.

---

### 11. GOLD-0140

**customer_message**: `"@115888 Dear Spotify - super cool that you can play videos on the background of the login screen, but the login buttons don’t work. \niPhone 7+"`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: `"1"` (numeric shorthand from the original 25-example calibration batch, decoded as Account Access & Login per `docs/GOLDEN_CALIBRATION_REVIEW.md`)

**Relevant taxonomy rule/representative example**: `docs/INTENTS.md`'s
App Technical include list names "missing UI elements/buttons that
should be present" — a non-functional login button matches this
almost exactly.

**Why the two rules conflict**: This is the original example that
surfaced this whole investigation (flagged in
`docs/GOLDEN_CALIBRATION_REVIEW.md`). A broken button is a UI
malfunction by `docs/INTENTS.md`'s own Technical include list, but its
effect is specifically "I can't log in," which is Account Access &
Login's core definition.

**Which interpretation is better supported**: Technical — of all the
examples in this investigation, this one has the strongest direct
textual support in `docs/INTENTS.md` for the Technical reading (the
"missing UI elements/buttons" bullet), stronger than the support the
same document gives Account Access & Login via its CSRF-token example
(GOLD-0010/0124's pattern).

**Genuinely ambiguous?** Yes — this was the original calibration
finding, not marked `ambiguous: true` at the time (the original 25
weren't touched), but functionally identical in shape to GOLD-0139.

---

### 12. GOLD-0052

**customer_message**: `"@SpotifyCares I've had hulu+spotify active for awhile but I cannot get hulu to log in because of the error message below. What do I do? https://t.co/BBBZEZBwcG"`

**Current primary_intent**: App & Playback Technical Issues
**Current secondary_issue**: Premium Subscription & Billing (ambiguous=true)

**Relevant taxonomy rule/representative example**: None directly.

**Why the two rules conflict**: The message references "the error
message below" but the error's actual content is only in an unfollowed
image — the text itself contains no quoted technical identifier at
all. Under the plain-language-vs-technical-identifier distinction this
investigation proposes, this message doesn't actually contain
verifiable evidence of a technical malfunction — it *claims* one
exists, but the claim's content isn't visible in text.

**Which interpretation is better supported**: This is a genuinely
different problem from the others in this list — it's less an
Access-vs-Technical conflict and more a case (like GOLD-0003, GOLD-0040
elsewhere in the golden set) of a message whose substantive content is
locked in an unseen image. Under a stricter, text-only version of the
tie-break rule, this arguably shouldn't have been called Technical at
all with confidence.

**Genuinely ambiguous?** Yes (already flagged), for a related but
distinct reason than the rest of this list.

---

## Clean comparators (not in conflict, for contrast)

These Account Access & Login examples contain **no** technical-
malfunction signal (no error code, no described broken UI, no
troubleshooting behavior) and are not part of the conflict — both
`docs/INTENTS.md` and the tie-break rule agree on them:

- GOLD-0037 — "logged out... idk how to get back in" (no error/malfunction described)
- GOLD-0044 — "keeps telling me there is something wrong" (vague, no code/detail)
- GOLD-0083 — "won't let me log in via Facebook" (no error/malfunction described)
- GOLD-0090 — "can't access my spotify premium" (no error/malfunction described)
- GOLD-0108 — "cannot remember my password" (pure forgotten-credential case)
- GOLD-0125 — "your site says I need [Facebook] to log in" (a stated business-logic requirement, not a malfunction)
- GOLD-0127 — "password problems... tried the reset, no joy" (no error/malfunction described)
- GOLD-0130 — "can't login, nor change my password" (no error/malfunction described)
- GOLD-0132 — "not linked to my email and I can not figure out my password" (pure forgotten-credential case)
- GOLD-0133 — "my login is all kinds of messed up" (vague, no detail)
- GOLD-0137 — "can't login or contact support in any other way" (no error/malfunction described)
- GOLD-0138 — "struggling to get into my account" (no error/malfunction described)

These are useful negative evidence: the tie-break rule works cleanly
whenever there is genuinely no technical signal in the message. The
conflict only arises for the 12 examples above, where some kind of
error text, broken UI, or troubleshooting behavior is also present.

---

## Summary of findings

1. **The core conflict is real and recurring**: 4 examples (GOLD-0010,
   GOLD-0124, GOLD-0139, GOLD-0140) directly pit a `docs/INTENTS.md`
   representative example or include bullet against the task's
   tie-break rule, in both directions (CSRF-token cases favor Access
   per the doc; broken-button/smart-speaker cases favor Technical per
   the same doc's own include list).
2. **The tie-break rule as originally applied was inconsistent, not
   just under-specified.** GOLD-0002 (reinstall troubleshooting →
   Technical) and GOLD-0065 (reinstall troubleshooting → Access, with
   Technical only secondary) show the identical evidentiary signal
   treated two different ways. GOLD-0121 (plain-language "PW invalid" →
   Access) and GOLD-0126 (plain-language "email doesn't exist" →
   Technical) show the same thing for rejection-message wording.
3. **A clean, checkable distinction exists in the data and was
   followed correctly some of the time**: messages naming a
   developer-facing technical identifier (an HTTP status code like
   "error 404," an internal token/field name like "CSRF token") or
   describing a broken UI element (a non-functional button) or
   describing troubleshooting behavior (reinstalling, clearing cache)
   consistently *feel* more like Technical; messages containing only a
   plain-language rejection ("password invalid," "email doesn't
   exist," "credentials have been used") consistently *feel* more like
   Access. This distinction was applied about 8 of 12 times without
   being written down, and its two misses (GOLD-0002 vs. GOLD-0065;
   GOLD-0121 vs. GOLD-0126) are exactly where the labels look
   inconsistent with each other.

---

## Proposed tie-break rule

This does **not** change the 9-intent taxonomy — it only replaces the
vague "technical/UI/app malfunction" criterion with a checkable
definition, to be added to `docs/INTENTS.md` and/or
`docs/GOLDEN_ANNOTATION.md` (not done in this investigation, per
instructions):

> **Account Access & Login vs. App & Playback Technical Issues, for
> any message reporting an inability to log in, register, or reset a
> password:**
>
> Classify as **App & Playback Technical Issues** only if the message
> contains at least one of:
> 1. a verbatim developer-facing technical identifier — an HTTP status
>    code, an internal token/parameter name, or an exception-style
>    string (e.g. "error 404," "CSRF token is invalid");
> 2. a description of a broken or non-functional UI element or app
>    behavior itself, distinct from a rejection outcome (e.g. "the
>    login buttons don't work," "the app crashes when I try to log
>    in");
> 3. described troubleshooting behavior the customer undertook in
>    response to the problem (reinstalling the app, clearing cache/
>    cookies, restarting the device, trying a different browser) —
>    evidence the customer suspects or attempted to fix a technical
>    fault, not just a wrong credential.
>
> If none of the above is present — the message only reports a
> plain-language credential rejection ("password invalid," "email
> doesn't exist," "credentials have been used," "username invalid") or
> a bare, undetailed statement of being unable to log in/reset — classify
> as **Account Access & Login**.
>
> If the malfunction is specifically an unseen/unquoted error (e.g.
> "error message below" with only a link, no text detail), do not
> assume criterion 1 is satisfied — treat as OTHER/UNKNOWN or Account
> Access & Login depending on how much other text context exists,
> consistent with this project's existing treatment of link-dependent
> messages elsewhere in the golden set.

**Effect on the 12 affected examples if adopted** (not applied in this
investigation — reported for reference only):
- Unchanged: GOLD-0010, GOLD-0124 (criterion 1), GOLD-0069, GOLD-0123
  (criterion 1), GOLD-0002 (criterion 3), GOLD-0139, GOLD-0140
  (criterion 2), GOLD-0121, GOLD-0134 (no criteria met → Access,
  already labeled Access).
- Would flip: GOLD-0126 (no criteria met in text → should become
  Account Access & Login, currently Technical).
- Would need re-examination: GOLD-0065 (criterion 3 is present —
  reinstalling on two devices — which would argue for Technical
  primary, currently Access primary with Technical secondary) and
  GOLD-0052 (the referenced error is unquoted/image-only, so per the
  rule's final clause this should likely move toward Account Access &
  Login or OTHER/UNKNOWN rather than Technical).

No relabeling was performed as part of this investigation — this is a
proposal only, consistent with the instruction not to modify the
golden set or the taxonomy documents yet.
