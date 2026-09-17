# Intent Discovery — Method, Evidence, and Draft Labeling Guide

Companion to `docs/INTENTS.md` (the taxonomy itself). This file holds
the method, the raw supporting evidence (samples, bucket counts), and
the draft human-annotator labeling guide (Step 6).

Labels: **MEASURED** (computed), **OBSERVED** (read directly from
sampled data), **HYPOTHESIS** (plausible, unvalidated).

No `.venv`, packages, models, embeddings, or classifier code were
created for this phase. Analysis reused the already-installed global
pandas and the `threads.parquet` conversation-reconstruction artifact
built during Phase 1 dataset reconnaissance (regenerated from
`data/raw/twitter/twcs.csv`, which was not modified).

---

## Method

1. Reconstructed SpotifyCares conversations (28,280 total, from Phase 1
   thread-reconstruction) and isolated the "root" message (chronologically
   first message) of each — 28,221 of these are customer-initiated
   (59 conversations open with a brand message instead, e.g. proactive
   outreach or a chain-reconstruction edge case — OBSERVED, not
   investigated further this phase).
2. **Broad random sampling**: pulled 60 conversations completely at
   random (not filtered by frequency or length) plus 15 conversations
   with 6+ turns specifically, and read them directly — this is what
   surfaced the DM-redirect pattern, canned-response patterns, and the
   general shape of real conversations.
3. **Root-message sampling for theme discovery**: pulled a fresh random
   sample of 150 root customer messages (`random_state=99`) and
   manually categorized each one by hand into a candidate intent. This
   is the primary evidence behind the frequency estimates in
   `docs/INTENTS.md`.
4. **Regex keyword-bucket pass** (MEASURED, full corpus): tagged all
   28,221 root messages against 11 keyword-regex buckets to get a
   cheap, mechanical lower-bound frequency per theme, and to
   sanity-check the manual sample against a machine-checkable number.
5. Deliberately included difficult/ambiguous/low-frequency examples in
   the reading rather than only looking at the most common phrasings —
   e.g. the long 62-message conversation (`conv_id=83694`, a
   promo-pricing thread in the Philippines with heavy code-switching)
   and several off-topic/ambiguous root messages are discussed below.

---

## Regex Bucket Pass (MEASURED, full 28,221 root messages)

| Bucket (regex, non-exclusive) | Matches | % of root messages |
|---|---|---|
| premium_billing_payment | 3,460 | 12.3% |
| account_access_login | 1,870 | 6.6% |
| app_technical_playback | 1,013 | 3.6% |
| offline_downloads | 1,047 | 3.7% |
| content_missing_licensing | 889 | 3.2% |
| device_connectivity | 480 | 1.7% |
| feature_request_feedback | 441 | 1.6% |
| account_security_hacked | 440 | 1.6% |
| country_market_availability | 242 | 0.9% |
| customer_service_complaint | 85 | 0.3% |
| metadata_catalog_correction | 68 | 0.2% |
| **Any bucket matched** | **9,073** | **32.1%** |
| **No bucket matched** | **19,148** | **67.9%** |

This pass is intentionally crude (literal keyword regexes, no
lemmatization or semantic matching) and is reported as a **lower
bound**, not a ground-truth frequency. It systematically undercounts
any intent where customers name a specific entity (a song, artist,
country) instead of describing a problem category in generic words —
see `docs/INTENTS.md`'s "Why frequencies differ from the regex pass"
section. It is most reliable for Premium & Billing and Country/Market
Availability, where customer phrasing is more formulaic, and least
reliable for Content Availability and Feature Request.

---

## Manual 150-Sample Categorization (OBSERVED, primary evidence)

Full method: random sample of 150 root customer messages
(`random_state=99`), each read and assigned one primary category by
hand. Raw counts (before folding sub-cases into the final 8-intent
taxonomy):

| Raw category (before folding) | Count | % |
|---|---|---|
| Feature Request / Product Feedback | 27 | 18.0% |
| Content Availability (missing/licensing/region) | 26 | 17.3% |
| Premium / Billing / Payment | 21 | 14.0% |
| App Technical (bugs, crashes, playback errors) | 19 | 12.7% |
| Other / Off-topic / Meta / Praise / Ambiguous | 20 | 13.3% |
| Device / Platform Compatibility | 10 | 6.7% |
| Account Access & Login | 9 | 6.0% |
| General Complaint / Vague Dissatisfaction | 8 | 5.3% |
| Account Security / Hacked | 6 | 4.0% |
| Country / Market Availability | 2 | 1.3% |
| Metadata / Catalog Correction | 1 | 0.7% |
| **Total** | **149/150** | (1 message ambiguous between two buckets during tallying) |

**Folding decisions made to reach the final 8-intent taxonomy** (see
`docs/INTENTS.md`):
- **Device / Platform Compatibility (10 items) folded into App
  Technical Issues.** Reading the actual messages, most of these are
  either (a) a bug/UX complaint about an already-supported device
  (repeated "not optimized for iPhone X" complaints — the app exists
  and works, just poorly on that screen size) or (b) closely adjacent
  to a technical integration problem (Google Home playback issues).
  Only one item (an Apple Watch app request) is a pure "doesn't exist
  yet" feature request; keeping a separate low-volume intent for that
  distinction wasn't judged worth the added category. **HYPOTHESIS**:
  if golden-set labeling shows device/platform requests cluster
  distinctly from bug reports, this fold should be revisited.
- **Metadata / Catalog Correction (1 item, <1%) folded into Content
  Availability & Catalog Accuracy.** Too rare to stand alone right now;
  the resolution pattern ("we'll report this to the right team") is
  similar enough to the licensing-explanation pattern to share an
  intent without much loss of actionability.

This gives the 8 intents reported in `docs/INTENTS.md`:
App Technical (19%), Feature Request (18%), Content Availability
(18%), Premium & Billing (14%), Other/Unknown (13%), Account Access
(6%), General Complaint (5%), Account Security (4%), Country/Market
Availability (1%).

---

## Difficult / Ambiguous Examples Worth Recording

These are specific messages from the 150-sample that were genuinely
hard to categorize, kept here as reference cases for the labeling
guide's tie-breaking rules:

1. **"Spotify is saying every song I try to play is 'not available',
   possibly after an update."** — Ambiguous between App Technical
   (triggered by "an update," suggests a regression/bug) and Content
   Availability (the symptom itself is "not available"). Categorized
   as App Technical because the trigger condition (a recent update
   affecting *every* song) points to a bug rather than licensing
   (licensing restrictions are near-universally song/artist-specific,
   not blanket).
2. **"why does spotify pause my music everytime i try to go to another
   app?"** — Could look like a Feature Request (behavior change) but
   is actually reporting broken behavior relative to normal expected
   function → App Technical.
3. **"For the second time in as many weeks, my entire library has been
   mysteriously removed. Redownloading all 2000+ songs, again."** —
   Looks like Content Availability ("removed") but is actually a
   data-loss/sync bug affecting the customer's own downloaded library,
   not catalog content → App Technical.
4. **"Get Nas & Damian Marley's - Distant Relatives back @Spotify"** —
   Short, imperative, no explicit question — still Content
   Availability; imperative phrasing shouldn't be confused with Feature
   Request (the request is about specific existing content, not new
   product capability).
5. **The 62-message `conv_id=83694` promo-pricing thread** (Philippines,
   heavy Tagalog/English code-switching, "9 PHP for 3 months" offer) —
   a single promotional tweet the brand posted, replied to by dozens of
   different customers with billing/payment-method questions
   (mobile-load payment eligibility, why the deducted price differs).
   This is **not one real back-and-forth conversation** — it's a
   broadcast tweet with many independent single-turn replies from
   different customers, incorrectly merged into one 62-message
   "conversation" by the reply-chain reconstruction algorithm. This is
   the concrete evidence for the "mega-thread artifact" hypothesis
   flagged in `docs/DATA.md` §2 — a real example, not just a
   suspected outlier. All of the individual customer messages in it
   are legitimately Premium & Billing (payment method eligibility), so
   the intent label is unaffected, but this **must** be handled before
   building the retrieval corpus (each customer's single-turn question
   should not be treated as part of one shared 62-turn resolution).
6. **Business/partnership inquiries** ("Do you all have an educational
   out reach? I have a project I would like my students to do...",
   "what kind of promotion for ur current members??") — not support
   requests at all; correctly routed to OTHER/UNKNOWN.
7. **Non-English content mixed into an otherwise-English corpus** —
   e.g. "tp di website tertera masa premium hanya sampai 7nov17..."
   (Indonesian/Malay) and "bAKIT BAWAL AKO..." (Tagalog, expletive-
   laden). Consistent with Phase 1's finding that SpotifyCares is
   ~99.4% English but not 100% — a small amount of non-English content
   will need a policy decision (filter out vs. keep and rely on the
   LLM's multilingual capability) before golden-set construction.

---

## Draft Labeling Guide (Step 6)

For a human annotator labeling SpotifyCares root customer messages
into the 8-intent + OTHER/UNKNOWN taxonomy from `docs/INTENTS.md`.

### General procedure

1. Read only the **root customer message** (the first message of the
   conversation) — do not look ahead at the brand's reply before
   labeling; the goal is to simulate what an intent classifier would
   see at inference time (a message with no brand response yet).
2. Assign exactly **one** primary intent. If a message plausibly fits
   two intents, apply the tie-breaking rules below before defaulting to
   OTHER/UNKNOWN.
3. If the message is not a genuine support request (praise, off-topic,
   promotional, business inquiry) or is too fragmentary to interpret
   (bare link, single word/emoji with no other context), label
   OTHER/UNKNOWN and flag it for **exclusion from the golden set**
   rather than forcing a support-intent label.

### Inclusion / exclusion quick-reference

| Intent | Include if... | Exclude if... |
|---|---|---|
| Account Access & Login | login/register/password/link-email problem, no claim of third-party involvement | customer says someone else accessed the account → Account Security |
| Account Security | explicit "hacked," "someone else," "stolen," "unauthorized," or unexplained activity implying compromise | customer just forgot their own password → Account Access |
| Premium & Billing | anything about paying, being charged, discount/plan eligibility, payment methods | pure login failure with no billing angle → Account Access |
| App & Playback Technical | app/site/device malfunctioning (crash, freeze, playback error, sync/data-loss bug, poor support for an existing device) | a feature that has never existed is being requested → Feature Request; song is named as unavailable with no error/bug language → Content Availability |
| Content Availability & Catalog Accuracy | specific song/album/artist/podcast missing, removed, region-locked, or mislabeled | whole country lacks the Spotify service itself → Country/Market Availability |
| Feature Request & Product Feedback | a specific, extractable, actionable suggestion for new/changed behavior | pure venting with no actionable ask → General Complaint |
| General Complaint | frustration/anger with no specific fixable ask | anger attached to an extractable specific issue → label the underlying issue instead |
| Country/Market Availability | whether the Spotify service itself is/will be available in a country | a specific song/artist restricted in an otherwise-served country → Content Availability |
| OTHER/UNKNOWN | praise-only, off-topic, promotional, business inquiry, or uninterpretable fragment | any message with an interpretable support ask, however vague — try General Complaint or the closest specific intent first |

### Tie-breaking rules

- **App Technical vs. Content Availability** ("this song won't play"):
  - If the message mentions an error message, crash, freeze, recent
    update breaking things, or affects many/all songs at once →
    **App Technical**.
  - If the message names one specific song/artist/album as absent or
    unavailable with no error/bug language → **Content Availability**.
  - If genuinely unclear from the text alone → default to **Content
    Availability** (it's the more common root cause historically, per
    the brand's own reply patterns observed in Phase 1/3 sampling).
- **Feature Request vs. General Complaint**:
  - If you can extract a concrete, specific thing the customer wants
    changed/added, even if delivered angrily → **Feature Request**.
  - If the complaint is purely evaluative ("your service is terrible")
    with nothing to act on → **General Complaint**.
- **Country/Market Availability vs. Content Availability**:
  - "Is Spotify available in my country" → Country/Market.
  - "Is [song/artist] available in my country" → Content Availability.
- **Multiple issues in one message** (e.g. a billing complaint that
  also mentions being locked out): label by whichever issue is
  **primary/first-stated** and note the secondary issue in an optional
  annotation field, rather than inventing a multi-label scheme at this
  stage.

### Edge cases observed and their resolution

- **DM-follow-up meta-messages** ("check ya dm", "peep ur dms please")
  with no visible original complaint in the sampled root position:
  label OTHER/UNKNOWN and exclude from the golden set — these are
  follow-ups to an issue that isn't visible at the root-message
  position, so there's nothing to classify.
- **Broadcast-thread replies** (see `conv_id=83694` above): label by
  the individual customer's own message content, not by the size or
  shape of the (likely-artifactual) merged conversation.
- **Non-English root messages**: label if the intent is still
  identifiable (e.g. clearly a billing complaint despite different
  language); if genuinely uninterpretable without translation, mark
  OTHER/UNKNOWN and flag separately as "non-English, needs translation
  policy" rather than guessing.
- **Sarcastic praise / backhanded compliments** ("Wow! Thank you...
  I thought I was going to have to catch you guys outside of the
  courthouse when I sue you.") — these read as praise on the surface
  but reference an unresolved underlying dispute. If the underlying
  issue isn't stated in the same message, treat as OTHER/UNKNOWN rather
  than guessing at the original complaint.

---

## Step 3 — Banking77 (secondary context, not inspected directly)

`data/raw/banking77/` is present but **empty** — Banking77 was not
downloaded in Phase 0 or Phase 1, and downloading it is out of scope
for this reconnaissance-only phase. The discussion of Banking77's
taxonomy structure in `docs/INTENTS.md` (under "Step 3 note") is based
on general knowledge of its publicly documented category list, not on
inspecting the actual dataset file, and is explicitly flagged as
HYPOTHESIS there. If Banking77 is downloaded in a future phase for
genuine intent-taxonomy-design inspiration (never as SpotifyCares
resolution/brand evidence, per CLAUDE.md), the specific claim to verify
is whether its fine-grained separation of similar payment-failure
intents is actually reflected in enough real Banking77 examples to
justify splitting our Premium & Billing intent later.

---

## Summary

The 8-intent + OTHER/UNKNOWN taxonomy in `docs/INTENTS.md` is grounded
in reading 210 real conversations/messages (60 random + 15 long +
150 root-message sample) plus a full-corpus regex sanity check. The
main open risks going into golden-set labeling are (1) the App
Technical / Content Availability boundary, for which explicit
tie-breaking rules are now written down above, and (2) the
broadcast-thread/mega-conversation artifact, which must be handled
before any retrieval corpus is built from these conversations (a
concrete example now exists: `conv_id=83694`).
