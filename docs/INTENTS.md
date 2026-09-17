# SpotifyCares Intent Taxonomy (Candidate, Phase 3)

## Status

DRAFT — derived from dataset evidence, not yet validated against a
labeled golden set. This is a candidate taxonomy for sign-off before
any classifier is built.

Labels used: **MEASURED** (computed over the full corpus or a
regex-tagged subset), **OBSERVED** (read directly off a manual sample),
**HYPOTHESIS** (plausible, not yet validated).

This document is the taxonomy itself, its tie-break rules, the quality
check, and the final recommendation.

Frequencies below come from **manual categorization of a random sample
of 150 root customer messages** (one per SpotifyCares conversation,
`random_state=99`) — this is OBSERVED, not a full-corpus MEASURED
count. A cheap regex-keyword pass over the full corpus (28,221 root
messages) was also run and is reported per-intent as a MEASURED lower
bound where relevant, but the regex substantially undercounts several
intents (see "Why frequencies differ from the regex pass" below) —
treat the 150-sample percentages as the better estimate, and the
regex numbers as a sanity-check floor.

---

## Why frequencies differ from the regex pass

An initial pass tagged root messages using literal keyword regexes
(`login`, `charged`, `crash`, `missing`, etc.) and got **32.1%
coverage** (9,073 / 28,221 root messages matched at least one bucket).
Manually reading a 150-message random sample showed the real coverage
is much higher — the regex just doesn't know that "Where's Reputation
on Spotify?" or "put TWICE's new album on here" is a Content
Availability request, because there's no keyword like "missing" or
"removed" in it; people name the artist/album instead. **HYPOTHESIS**:
this undercounting is specific to intents where customers name a
concrete entity (song/artist/country) rather than describing a problem
category — Content Availability is the intent most affected. The
manual sample is used as the primary frequency estimate for this
reason.

---

## Candidate Taxonomy (8 intents + OTHER/UNKNOWN)

### 1. Account Access & Login

**Definition**: Customer cannot log in, register, or manage basic
account access/identity (password reset, linked email/Facebook change,
username issues) — where there is no indication of a third party
having compromised the account.

**Include**: login failures, password reset errors (e.g. "CSRF token
invalid"), can't register a new account, Facebook-linked email is
stale, artist-account login issues.

**Exclude**: login failures explicitly described as caused by someone
else accessing the account (→ Account Security); billing/subscription
verification errors that happen to occur during checkout (→ Premium &
Billing) unless the customer frames it purely as a login problem.

**Representative examples** (OBSERVED):
- "I was logged out of my account and when I try to log in it doesn't work — it says my password is invalid, and resetting says my username is invalid"
- "my Spotify acct is linked to my FB, and I recently changed the email on my FB but it hasn't updated for Spotify"
- "yo whats up with this? cant log in to my spotify for artist page"

**FINALIZED (Phase 6D)**: an earlier draft of this list included a CSRF-
token-error example here. Per the finalized tie-break rule below, a
verbatim technical error identifier like "CSRF token is invalid" belongs
to **App & Playback Technical Issues**, not here — see that intent's
representative examples instead, and see "Tie-Break: Account Access &
Login vs. App & Playback Technical Issues" below for the full rule.

**Approximate frequency**: ~6% of root messages (OBSERVED, 9/150 sample).

**Typical historical resolution**: brand asks for account email/username
via DM ~most of the time — this intent has one of the higher DM-redirect
rates observed qualitatively, since resolving it requires looking up a
specific account. Visible-in-thread resolution is rare beyond
"try resetting your password" / "try logging out and back in."

**Escalation tendency**: HIGH — almost always needs an account-specific
lookup that can't be done from public tweet text alone.

**Potentially confused with**: Account Security (distinguishing signal:
explicit mention of "hacked," "someone else," "stolen," "unauthorized");
App & Playback Technical Issues when the login failure involves an
error code, a broken UI element, or troubleshooting behavior — see the
finalized tie-break rule below.

---

### 2. Account Security (Unauthorized Access)

**Definition**: Customer reports their account was compromised,
hacked, or is being used without authorization.

**Include**: "my account got hacked," email/password changed by someone
else, unrecognized listening activity/library changes, discovering a
stranger's playlists/likes on their account.

**Exclude**: forgotten own password with no claim of third-party
involvement (→ Account Access & Login).

**Representative examples** (OBSERVED):
- "I just got my account stolen. I can login with FB, but they changed the e-mail and cannot change my password."
- "Someone has hacked into my spotify account, changed the email address and password. I am unable to log in."
- "half of the stuff on it is not mine" (implicit account compromise)

**Approximate frequency**: ~4% of root messages (OBSERVED, 6/150 sample).

**Typical historical resolution**: near-universally redirected to DM
immediately — no visible resolution content in the public dataset
(consistent with this being a security-sensitive, PII-requiring
process). One sampled conversation showed a genuine happy ending
("Got my Spotify account back today... Thank you") but the actual
recovery steps happened off-platform.

**Escalation tendency**: VERY HIGH — this should essentially always
escalate; a security-sensitive account-recovery flow is not something
a support bot should attempt to auto-resolve.

**Potentially confused with**: Account Access & Login (see above);
Premium & Billing when the complaint is about someone else's paid
usage on the account.

---

### 3. Premium Subscription & Billing

**Definition**: Anything about paying for, changing, or being charged
for Spotify Premium — including family/student plan administration,
promo/discount eligibility and pricing, payment method problems, and
billing disputes.

**Include**: incorrect charge amount, double-charged, can't update
payment card, student/family plan verification and eligibility,
promo-code pricing confusion, wanting to cancel/change billing date,
gift-card redemption issues, "charged but shows as free."

**Exclude**: pure login problems with no billing angle (→ Account
Access); "my account is compromised and being billed for someone
else's usage" leans Account Security if hacking is claimed, otherwise
stays here.

**Representative examples** (OBSERVED):
- "i'm getting charged $9.99 2x a month when i have one account and the student discount"
- "Hello, I'm trying to set up the Spotify+Hulu for Students account but... 'CSRF token is invalid'"
- "my child have taken a preminium abo whit out permission how can i cancel it"
- "I was logged into a co-workers account, updated my payment info accidentally am now paying for their [subscription]"

**Approximate frequency**: ~14% of root messages (OBSERVED, 21/150
sample). MEASURED regex lower bound (broad keyword set: charged,
billing, payment, refund, subscription, discount, etc.): 12.3% of all
28,221 root messages (3,460 matched) — reasonably close to the manual
estimate, since billing complaints tend to use identifiable vocabulary
("charged," "billing," "payment").

**Typical historical resolution**: mixed. General policy questions
("what happens when the promo expires?") get a visible, complete
answer. Account-specific disputes (wrong charge amount, can't update
card) almost always get redirected to DM for the account
email/username.

**Escalation tendency**: MEDIUM-HIGH — policy questions can be
AUTO_HANDLED with a canned/grounded answer; anything involving a
specific charge, refund, or account eligibility needs a human/account
lookup.

**Potentially confused with**: Account Access & Login (student/family
verification issues can look like login errors); Account Security
(unauthorized charges could imply account compromise).

---

### 4. App & Playback Technical Issues

**Definition**: The app, website, or a specific device/OS integration
is malfunctioning — crashes, freezes, playback errors, sync bugs, or a
device/platform not being properly supported yet (e.g. new phone
screen sizes, smart-home integrations).

**Include**: app crashing/freezing/buffering, songs skipping or
failing to play due to a bug (not licensing), web player errors, sync
issues across devices, "my downloaded songs disappeared," Bluetooth/
smart-speaker/game-console integration problems, "not optimized for
iPhone X," missing UI elements/buttons that should be present.

**Exclude**: a song/album is unavailable due to licensing/region
restriction with no error message involved (→ Content Availability);
a feature that has never existed and is being requested (→ Feature
Request), even if framed as "your app doesn't do X."

**Representative examples** (OBSERVED):
- "my Spotify keeps skipping randomly through songs, every song"
- "For the second time in as many weeks, my entire library has been mysteriously removed. Redownloading all 2000+ songs, again."
- "Spotify audio does not pause when headphones adapter is unplugged... Works correctly for other apps"
- "still no support for iPhone X???" (repeated across many samples)
- "I was logged out of my account and when I try to log in it doesn't work... 'The CSRF token is invalid'" (login failure with a verbatim technical error identifier — see the finalized tie-break rule below)
- "the login buttons don't work" (a broken/non-functional UI element, even though the symptom is being unable to log in)

**Approximate frequency**: ~19% of root messages (OBSERVED, 29/150
sample — the largest single intent found, once device/platform
compatibility complaints are folded in here rather than kept separate;
see quality-check notes below). MEASURED regex lower bound (crash,
freeze, bug, buffering, "not working," etc.): 3.6% of all root messages
(1,013 matched) — this heavily undercounts because many technical
complaints don't use any of those literal words (e.g. "keeps
skipping," "mysteriously removed").

**Typical historical resolution**: this is the intent with the
**best visible resolution quality** — brand consistently asks for
device/OS/app-version, then gives a concrete troubleshooting sequence
(log out → restart device → log back in; reinstall; check another
network) directly in the thread. Escalates to DM only when
troubleshooting doesn't resolve it or requires account-specific
diagnostics.

**Escalation tendency**: LOW-MEDIUM — most cases can be AUTO_HANDLED
with grounded troubleshooting steps retrieved from historical
resolutions; escalate if the customer reports the standard steps
already failed.

**Potentially confused with**: Content Availability (a song "not
playing" is ambiguous between an app bug and a licensing restriction —
distinguishing signal: does the customer name a specific missing
song/artist, or describe an error/crash affecting playback broadly?);
Account Access & Login when the malfunction manifests as a login/
reset failure — see the finalized tie-break rule below.

---

### 5. Content Availability & Catalog Accuracy

**Definition**: A specific song, album, artist, or podcast is missing,
removed, region-restricted, or incorrectly catalogued (wrong artist
attribution, mislabeled title, missing metadata).

**Include**: "why isn't X on Spotify," "please add X," an album/song
that used to be there and disappeared, region-locked content, wrong
artist/album tagging, duplicate or incorrectly attributed tracks.

**Exclude**: an entire country not having Spotify at all (→
Country/Market Availability Inquiry — a different resolution pattern);
a song failing to play due to a technical error rather than
non-existence in the catalog (→ App & Playback Technical Issues).

**Representative examples** (OBSERVED):
- "Why is Taylor Swifts album not on @Spotify"
- "why did you remove 'Up Your Alley' from Joan Jett and The Blackhearts... could you give me an answer or put it back"
- "this song CLEARLY exists but I keep getting these [unavailable errors]. I'd love to listen to this in HQ"
- "Samuel's EYE CANDY album is categorized under the wrong artist" (metadata correction — small sub-case folded into this intent, see quality-check notes)

**Approximate frequency**: ~18% of root messages (OBSERVED, 27/150
sample, includes the rare metadata-correction sub-case). MEASURED
regex lower bound (missing/removed/licensing/"isn't on spotify"):
3.2% (889/28,221) — this is the intent most undercounted by keyword
matching, because customers almost always name the specific
song/artist rather than using a generic "missing" word.

**Typical historical resolution**: usually visibly resolved in-thread
with one of two canned-but-genuine answers: (a) "sometimes content
gets temporarily removed because of licensing changes" or (b) a link
to a content-availability help page. Metadata-correction cases get "we'll
get this reported" acknowledgments. Rarely escalates to DM since no
PII/account lookup is needed to answer.

**Escalation tendency**: LOW — this is the best-suited intent for
grounded AUTO_HANDLE, since the brand's real historical answers are
policy explanations that generalize well and don't require
account-specific information.

**Potentially confused with**: App & Playback Technical Issues (see
above); Country/Market Availability Inquiry (whole-country absence vs.
specific-content absence).

---

### 6. Feature Request & Product Feedback

**Definition**: Customer wants a feature that doesn't exist yet, wants
existing behavior changed, is requesting platform/device support that
hasn't launched, or is giving product feedback/criticism without a
specific broken thing to fix.

**Include**: UI/UX suggestions, requests for filters (explicit-content
filter, genre sort), two-factor authentication requests, requests for
unreleased platform support (Apple Watch app), algorithm/curation
feedback ("stop recommending X"), "bring back [removed feature]."

**Exclude**: reporting something that is broken/not working as
designed (→ App & Playback Technical Issues); pure negative sentiment
with no specific suggestion (→ General Complaint).

**Representative examples** (OBSERVED):
- "please please please can you add explicit filters so that I can allow my 7 year old daughter to listen to music"
- "Security is important. We'd like it if you supported two factor auth."
- "for the love of GOD please bring back the Touch Preview feature!"
- "Is an app being developed for #AppleWatchSeries3?"

**Approximate frequency**: ~18% of root messages (OBSERVED, 27/150
sample). MEASURED regex lower bound (explicit "feature request/please
add/suggestion" phrasing): 1.6% (441/28,221) — heavily undercounted,
since most feature requests are phrased as direct asks ("can you add
X") rather than using words like "feature" or "suggestion."

**Typical historical resolution**: consistently visible, low-effort,
templated acknowledgment ("we'll pass this on to the team" / "your
feedback's been noted 📝") — genuinely resolved in the sense of
"closed out," but with no concrete outcome or timeline ever given.

**Escalation tendency**: LOW — the appropriate AUTO_HANDLE response is
almost always the same acknowledgment pattern; there's little reason
to escalate a feature request to a human.

**Potentially confused with**: General Complaint (a request can be
buried inside a rant — distinguishing signal: is there an extractable,
specific, actionable ask, even if delivered angrily?).

---

### 7. General Complaint / Service Dissatisfaction

**Definition**: Customer expresses frustration, anger, or
dissatisfaction with Spotify broadly (or with prior support
interactions) without a specific, actionable, fixable request.

**Include**: "your customer service is terrible," comparisons to
switching to a competitor, venting about the free tier or ads with no
specific ask, generic "fix your app" complaints with no diagnosable
detail.

**Exclude**: complaints that do contain an extractable specific issue
or request (→ classify by the underlying issue instead — e.g. App
Technical, Feature Request, Billing).

**Representative examples** (OBSERVED):
- "I can't even begin to understand how such a company has such poor customer service"
- "no one in India should buy or choose Spotify #annoyed #pissed #CustomerService"
- "The free shit barely works why would I pay for something that's flawed"

**Approximate frequency**: ~5% of root messages (OBSERVED, 8/150
sample) as a *pure* vague-complaint bucket — note this likely
undercounts real sentiment-risk volume, since anger frequently
co-occurs with a specific complaint that got classified into another
intent instead (e.g. an angry Account Security or Billing message).
MEASURED regex lower bound (very narrow "worst/terrible/no
response" phrasing): 0.3% (85/28,221) — regex catches almost none of
this; sentiment is not well captured by keyword matching.

**Typical historical resolution**: generic apology/empathy statement,
sometimes escalates to DM "so we can make this right," sometimes just
absorbs the complaint with no follow-up.

**Escalation tendency**: HIGH — there's no fixable action to
auto-resolve, and a template-only response risks looking dismissive on
a public, potentially high-visibility complaint; better handled (or at
least reviewed) by a human, especially if it includes public
reputational risk (hashtags, "I'm switching to X," etc.).

**Potentially confused with**: Feature Request (see above); any other
intent when the anger is attached to a specific underlying problem
(that underlying problem should usually win the label).

---

### 8. Country/Market Availability Inquiry

**Definition**: Whether Spotify (the service itself, not specific
content) is or will be available in a given country.

**Include**: "when will Spotify launch in [country]," "why isn't
Spotify available where I live."

**Exclude**: a specific song/artist not being available due to
licensing while the service itself operates in that country (→ Content
Availability & Catalog Accuracy).

**Representative examples** (OBSERVED):
- "will Spotify ever come to Bangladesh?"
- "why dont you make spotify available in Egypt"
- "Music for everyone... but russians? When will you make a version for my country?"

**Approximate frequency**: ~1% of root messages (OBSERVED, 2/150
sample). MEASURED regex lower bound: 0.9% (242/28,221) — one of the
few intents where the regex and manual estimate roughly agree, since
this phrasing is fairly formulaic.

**Typical historical resolution**: always visible, always the same
canned answer — "we're launching in new countries as often as
possible, sign up here to be notified." Never needs DM.

**Escalation tendency**: LOW — trivially AUTO_HANDLE-able with a
single canned response; arguably the easiest intent in the whole
taxonomy.

**Potentially confused with**: Content Availability & Catalog Accuracy
(see above).

---

### OTHER / UNKNOWN

**Definition**: Not a genuine, actionable support request to
SpotifyCares — praise/thanks with no ask, off-topic mentions, memes/
jokes, promotional retweets that happen to mention the Spotify handle,
unrelated business/partnership inquiries, or messages too fragmentary
(a bare link, a single emoji, one ambiguous word) to classify.

**Approximate frequency**: ~13% of root messages (OBSERVED, 20/150
sample) — a meaningfully large bucket, not a rounding error.

**Strategy**: Do not force these into one of the 8 support intents.
For classifier training/eval purposes:
- Praise/thanks-only messages and clearly off-topic content should be
  **excluded from the golden set entirely** rather than labeled
  OTHER and scored — they're not representative of "a customer
  message that needs an intent-driven response."
- Genuinely ambiguous but plausibly-a-real-issue messages (e.g. a bare
  link with no text, a one-word "help me") should get an explicit
  OTHER/UNKNOWN label and route to ESCALATE by default (a bot should
  not guess at an intent it can't identify from the text).

---

## Tie-Break: Account Access & Login vs. App & Playback Technical Issues

**Status: FINALIZED (Phase 6D)**. This resolves a conflict found during
golden-set annotation, where an earlier draft of this document's own
representative examples disagreed with the tie-break rule used to build
the 200-example golden set (12 affected examples, 2 discovered internal
inconsistencies in how the earlier, unwritten version of this rule was
applied — see `docs/DECISIONS.md` decisions 5-6 for the summary).
**This does not change the 9-intent taxonomy** — it only makes precise
how to choose between these two specific intents when a message reports
trouble logging in, registering, or resetting a password.

### The rule

For any message reporting an inability to log in, register, or reset a
password, classify as **App & Playback Technical Issues** if and only
if the message contains at least one of these three things — otherwise
classify as **Account Access & Login**:

| # | Criterion | Present → | Example phrasing |
|---|---|---|---|
| 1 | A verbatim **developer-facing technical identifier** — an HTTP status code, an internal token/parameter name, or an exception-style string | App & Playback Technical Issues | "error 404", "the CSRF token is invalid" |
| 2 | A description of a **broken or non-functional UI element or app behavior itself**, distinct from merely being rejected | App & Playback Technical Issues | "the login buttons don't work", "the app crashes when I try to log in" |
| 3 | Described **troubleshooting behavior** the customer undertook in response to the problem | App & Playback Technical Issues | "I reinstalled the app", "cleared my cache", "restarted my phone", "tried a different browser" |
| — | **None of the above** — only a plain-language credential rejection or a bare statement of being unable to log in/reset | Account Access & Login | "it says my password is invalid", "says my email doesn't exist", "says my credentials have been used", "I can't log in" |

If criterion 1's "technical identifier" is referenced but not actually
shown in the message text (e.g. "I get an error message, see the
screenshot" with only a link, no error text in the tweet itself), do
**not** assume criterion 1 is satisfied — you cannot verify a technical
identifier you cannot see. Treat as Account Access & Login if there is
otherwise-sufficient login/access context, or OTHER/UNKNOWN if the
message is too link-dependent to interpret at all (consistent with how
other link-dependent messages are handled elsewhere in this taxonomy).

### Explicit worked cases

- **(a) Bare "can't log in"** — e.g. "I can't log in, please help" with
  no further detail. No criterion met → **Account Access & Login**.
- **(b) Invalid password / invalid username** — e.g. "it says my
  password is invalid" or "resetting says my username is invalid."
  These are ordinary, expected system validation responses, not
  evidence of a malfunction → no criterion met → **Account Access &
  Login**. (This is the correction to a real inconsistency found during
  investigation: an earlier annotation pass treated some validation
  messages as evidence of a bug — it should not.)
- **(c) Email/account-not-found messages** — e.g. "it just told me my
  email doesn't exist" for someone who is a real registered user. Even
  though the system's response is *factually wrong*, that alone is not
  a verifiable technical signal from message text — plain-language
  rejection → no criterion met → **Account Access & Login**. (This is
  the other correction found during investigation, on GOLD-0126.)
- **(d) Broken login UI/buttons** — e.g. "the login buttons don't
  work." Criterion 2 → **App & Playback Technical Issues**.
- **(e) Error codes / technical identifiers** — e.g. "error 404" or
  "the CSRF token is invalid." Criterion 1 → **App & Playback
  Technical Issues**.
- **(f) Reinstall / cache-clear / restart troubleshooting** — e.g. "I
  cleared cache, uninstalled, reinstalled... now I can't log in."
  Criterion 3 → **App & Playback Technical Issues**, even without a
  named error code, because the described remedy behavior is itself
  the technical-malfunction signal.

This table is designed so two independent annotators reading the same
message should reach the same primary label: check the message against
criteria 1–3 in order; the moment one is satisfied, stop and label
Technical; if none apply, label Account Access & Login. There is no
step in this procedure that depends on the annotator's subjective read
of tone, severity, or plausibility — only on what the message
literally contains.

---

## Step 5 — Taxonomy Quality Check

**1. Coverage.** With the OTHER/UNKNOWN bucket included, ~100% of
sampled root messages get *some* label. Excluding OTHER/UNKNOWN, the 8
support intents cover ~87% of root messages (OBSERVED, 130/150). This
is a reasonable coverage level; the remaining 13% is a real,
irreducible category (praise, off-topic mentions, fragments) rather
than a taxonomy gap.

**2. Distinctiveness.** Seven of the eight intents are clearly
separable by a concrete distinguishing signal (see each intent's
"Potentially confused with" field). The weakest distinction is App
Technical vs. Content Availability, both of which can present as "a
song won't play" — each intent's own "Potentially confused with" field
above states the practical distinguishing signal (does the customer name
a specific missing song/artist, or describe an error/crash?); unlike the
Account Access vs. App Technical pair, this one did not need a separate
formal tie-break table during golden-set annotation.

**3. Balance.** Frequencies range from ~1% (Country/Market Inquiry) to
~19% (App Technical). Country/Market Inquiry and Metadata correction
(folded into Content Availability) are genuinely rare. This is
HYPOTHESIS-flagged as a risk: at a 150-250 example golden set, 1%
implies only 2-4 examples of Country/Market Inquiry — thin, but the
intent is also nearly trivial to resolve correctly (single canned
answer), so a thin example count is a lower-risk gap than it would be
for a harder intent. Recommend either accepting the imbalance (most
realistic) or deliberately oversampling rare-but-easy intents in the
golden set so they're at least represented.

**4. Actionability.** All 8 intents map to a distinguishable response
strategy (see each "Typical historical resolution"). None of them is a
vague catch-all that fails to inform what the reply should contain.

**5. Resolution alignment.** Content Availability, Feature Request,
and Country/Market Availability have the strongest alignment between
intent and a genuine, reusable historical resolution pattern. Account
Access, Account Security, and (to a lesser extent) Premium & Billing
have weaker alignment — their "resolution" in the visible dataset is
usually just "please DM us," meaning the retrieval corpus for these
intents will be thin on actual fixes and thick on triage questions.
This is a known limitation to carry into the RAG-corpus-design phase,
not a taxonomy flaw.

**6. Escalation usefulness.** The taxonomy cleanly splits into a
LOW-escalation group (Content Availability, Feature Request,
Country/Market Inquiry — all good AUTO_HANDLE candidates) and a
HIGH-escalation group (Account Security, General Complaint, and much
of Account Access) with App Technical and Premium & Billing sitting in
the middle depending on specifics. This gives the escalation-policy
component real signal to work with, rather than a domain that's either
all-auto or all-escalate.

**7. Ambiguity.** Two confusion pairs stand out: (a) App Technical vs.
Content Availability, and (b) Feature Request vs. General Complaint. Both
are addressed by the distinguishing signal noted in each intent's own
"Potentially confused with" field above. A third pair, Account Access &
Login vs. App & Playback Technical Issues, was found during golden-set
annotation (Phase 6) to be under-specified and inconsistently applied in
an earlier draft — this is now resolved by the finalized, deterministic
tie-break rule above (see `docs/DECISIONS.md` decisions 5-6).

---

## Step 3 note — Banking77 as secondary context

Banking77 (`data/raw/banking77/`) has **not been downloaded** — the
directory exists but is empty (confirmed in Phase 0/1 audits). Per
CLAUDE.md, downloading it was out of scope for this phase, and it was
not downloaded here either. The following is general knowledge about
Banking77's publicly documented structure (HYPOTHESIS — not verified
against the actual dataset file):

Banking77 is known to separate closely-related financial intents very
finely (e.g. distinguishing "card not working," "declined card
payment," "pending card payment," and "card payment not recognised" as
four separate intents rather than one "payment problem" bucket). If
this structural pattern holds, it suggests our Premium & Billing intent
(currently one bucket at ~14%) *could* eventually be split into
finer-grained sub-intents (e.g. "payment method failure" vs. "billing
dispute/wrong charge" vs. "plan eligibility/verification") if labeling
volume supports it later. **This is not being done now** — at current
observed volume, splitting Premium & Billing three ways would produce
several sub-intents below 5%, which the balance check above already
flags as risky. Recorded here only as a documented, deferred
possibility, not adopted into the taxonomy. Banking77 has not been and
will not be used as brand-response, resolution, or escalation evidence
(CLAUDE.md rule).

---

## Recommendation

**Adopt this 8-intent + OTHER/UNKNOWN taxonomy as the working draft**
for golden-set labeling. It is grounded in an OBSERVED read of a random
150-message sample (cross-checked against a MEASURED regex pass on the
full 28,221-message corpus), covers ~87% of real customer messages
with a distinguishable, actionable label, and produces a genuine mix of
AUTO_HANDLE-friendly and ESCALATE-friendly intents rather than skewing
entirely one way.

The two known soft spots — (1) App Technical vs. Content Availability
ambiguity, and (2) thin volume for Country/Market Availability — are
both manageable with explicit tie-breaking rules and are not reasons to
change the taxonomy before seeing real label counts from the golden
set.

**Do not proceed to build the classifier from this document alone.**
Per CLAUDE.md, this taxonomy should be validated against actual labeled
examples (next phase) before being treated as final.
