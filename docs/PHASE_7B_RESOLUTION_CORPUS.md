# Phase 7B — Historical Resolution-Pair Extraction

## 1. Goal

Build a clean, auditable **historical resolution-candidate corpus**
from the Phase 7A reconstructed SpotifyCares conversations — the
future evidence source for the support agent's retrieval/RAG system.
Every field in this corpus is text taken directly from the historical
dataset. **Nothing is generated, paraphrased, summarized, or invented.**

Terminology used precisely throughout this document and the code:

- **"Historical response"** — a real SpotifyCares (or co-participating
  support account) reply that was actually posted, verbatim.
- **"Resolution candidate"** — a real customer-message → historical-
  response pair, structurally extracted. This is **not** a claim that
  the customer's problem was solved. Whether a given historical
  response actually resolved anything is not knowable from this data
  alone (no follow-up confirmation signal exists for most threads), so
  this corpus never asserts "resolved" — only "here is what was
  actually said in response."

## 2. Input

`data/processed/twitter/spotifycares_conversations.parquet` (Phase
7A's output, read-only — **never modified**, verified by checksum
before and after this phase): 91,889 rows across 28,280 SpotifyCares
conversations, with columns `conversation_id, tweet_id, author_id,
role, timestamp, text, parent_tweet_id, parent_resolved, source_row_id`.

`data/raw/twitter/twcs.csv` was not read or touched in this phase at
all — only the already-reconstructed Phase 7A Parquet was used.

## 3. Extraction methodology

Implemented in `src/data/resolution_extraction.py`, tested in
`tests/test_resolution_extraction.py` (26 tests, synthetic fixtures)
and `tests/test_resolution_smoke.py` (1 test, real Phase 7A data).

No dependency other than the already-approved stack (Polars, PyArrow,
pytest) was used or needed — this phase's logic is table joins/filters
plus Python regex/string checks, not a graph closure, so DuckDB wasn't
needed here (Phase 7A's recursive CTE already did the structural
graph work). No new packages were installed.

## 4. Customer → brand pairing logic

A resolution candidate is generated for **every** row `B` with
`role == "brand"` and a non-null `parent_tweet_id`, where the row
identified by `parent_tweet_id` (call it `C`) has `role == "customer"`.
This is a direct, structural parent/child edge — **not** chronological
adjacency. This distinction matters: a conversation can branch (a
tweet can have multiple replies), so "the next message in time" is
not reliably "the reply to this message." Every candidate's
`customer_message`/`brand_response` pair is connected by the dataset's
own `in_response_to_tweet_id` link (renamed `parent_tweet_id` in Phase
7A), traced back through the reconstructed table.

Consequences of this rule, verified by tests:

- A brand reply whose parent is **another brand message** (e.g. a
  reply split "1: ... " / "2: ...") does not get treated as if the
  first part were a customer message — only genuine customer→brand
  edges become candidates.
- Two customers' independent threads interleaved in time never get
  cross-paired.
- A customer message with **multiple** brand replies (e.g. two agents,
  or a two-part answer both replying directly to the same customer
  tweet) produces multiple separate candidates, each fully valid.
- A brand reply whose parent doesn't resolve (broken chain, or the
  parent was excluded — see §7) produces no candidate at all, rather
  than fabricating one.

## 5. Multi-turn representation

Each candidate's `customer_message` is only the single message the
brand reply was actually addressed to. To avoid reducing a multi-turn
exchange to an isolated pair, every candidate also carries
**`context_messages_json`**: a compact JSON array of every ancestor
message (both customer and brand turns) between the conversation root
and the trigger customer message, in chronological order, each entry
holding `{tweet_id, role, author_id, text, timestamp}`. The count is
mirrored in `number_of_context_messages` for cheap filtering without
parsing JSON.

**Why this representation and not wide per-turn columns**: the number
of preceding turns varies per candidate (0 up to 25 in the real data —
see §10) — a fixed set of `context_turn_1`, `context_turn_2`, ...
columns would either truncate deep conversations or waste space with
mostly-null columns for the 63% of candidates with zero context. A
single JSON column scales with actual conversation depth and doesn't
duplicate the full conversation text across every candidate drawn from
it — each ancestor message's text is stored once per candidate that
needs it as context, not once per raw row.

Worked example (matches the task's own illustration, reproduced
directly against the pairing logic): given the chain

```
Customer: "I can't access Premium."
Brand:    "Can you tell us which account you're using?"
Customer: "aditya@example.com"
Brand:    "Please DM us so we can investigate."
```

this produces **two** candidates: one for the first customer→brand
edge (`number_of_context_messages: 0`), and one for the second
(`customer_message: "aditya@example.com"`,
`number_of_context_messages: 2`, with the JSON context array holding
the first customer message and the first brand reply in order) — the
final candidate is fully interpretable as part of a multi-turn
interaction without duplicating the whole conversation into every row.

## 6. Response categorization

Conservative, structural, deterministic — **no LLM, no semantic
classification**. Priority order (first match wins):

| Category | Rule |
|---|---|
| `dm_redirect` | Text matches `\bdm\b`, "direct message", or "private message" (same regex used for Phase 1's brand-level DM-redirect-rate analysis) |
| `acknowledgement` | ≤8 words, no `?`, not a DM redirect |
| `clarification_question` | Contains `?` |
| `substantive_response` | Everything else — longer, non-question, non-DM text |

**`generic_template_count` is `null`, intentionally not implemented.**
Distinguishing genuinely generic/templated wording from substantive-
but-formulaic wording (many real SpotifyCares answers *are* templated
phrasing carrying real information, e.g. "sometimes content gets
temporarily removed because of licensing changes") requires semantic
judgment this phase's deterministic rules cannot reliably make. Per
this phase's explicit instruction to stay conservative rather than
guess, this category was left unimplemented and documented here rather
than approximated with a rule likely to mislabel real evidence as
noise (or vice versa).

**`substantive_response` is a structural label, not a quality or
success claim.** It means only "longer than 8 words, not a question,
not a DM ask" — manual inspection (§11) shows this bucket contains both
genuinely informative answers and some fragments of multi-part replies
that happen to be non-question, non-DM text. Any downstream use of
this corpus for retrieval should treat `substantive_response` as a
useful pre-filter, not a resolved/quality guarantee.

## 7. Exclusion rules

Applied at this stage only — **Phase 7A's Parquet is never modified**.
All four rules are carried forward from prior phases' documented
findings, re-applied here at the resolution-candidate level (not
deleting rows, only excluding candidates from generation, fully
reported):

| Reason | Rule | Source |
|---|---|---|
| `mega_thread` | Whole conversation excluded from candidate generation | `docs/GOLDEN_SET_ANNOTATION_REVIEW.md` / `docs/TAXONOMY_CONFLICT_REVIEW.md` finding; conversation `83694` |
| `brand_family_account` | Any candidate whose customer trigger is authored by `115888`, `125633`, `117153`, or `116130` | `docs/GOLDEN_SET.md` §"New finding" — these are Spotify marketing/status accounts misfiled as customers, not real support interactions |
| `fragment` | Customer trigger message has no real content after stripping @mentions/URLs (<3 chars) | `docs/GOLDEN_SET.md` sampling exclusion rule |
| `dm_followup_no_issue` | Customer trigger is a bare "check your DM"-style message (≤8 words) with no visible original issue | `docs/GOLDEN_SET.md` sampling exclusion rule |

Full, itemized results (never silently dropped) are in
`data/processed/twitter/spotifycares_resolution_exclusions.json`,
one entry per exclusion reason (and per author, for the brand-family
rule), each with `conversation_id`/`author_id` (where applicable),
`affected_message_count`, `affected_candidate_count`, and up to 50
affected tweet_ids for direct auditability. Summary counts are:

| Exclusion reason | Messages affected | Candidates that would otherwise have been generated |
|---|---|---|
| `mega_thread` (conv 83694) | 62 | 30 |
| `brand_family_account` — `115888` | 331 | 0 |
| `brand_family_account` — `116130` | 7 | 0 |
| `brand_family_account` — `117153` | 14 | 0 |
| `brand_family_account` — `125633` | 28 | 0 |
| `fragment` | 774 | 537 |
| `dm_followup_no_issue` | 122 | 78 |
| **Total** | **1,338** | **645** |

**Notable finding**: all four brand-family accounts show
**0 affected candidates**, despite hundreds of affected messages. This
confirms the earlier hypothesis (Phase 5/7A): these accounts' messages
are broadcast/marketing tweets that *other real customers* reply to —
SpotifyCares never directly replies back to the brand-family account
itself, so no candidate ever had one of these accounts as its direct
parent. The exclusion rule is correct and necessary defense-in-depth
(it does protect against a hypothetical future case), but in this
dataset the actual contamination risk from these accounts flows
entirely through the mega-thread mechanism (§8), not through direct
pairing. `excluded_conversations` in the quality report counts only
**wholesale** conversation exclusions (the mega-thread, `1` in this
run) — the brand-family/fragment/dm-followup rules operate at the
individual-candidate level within conversations that otherwise remain
valid, so they don't add to that count.

**Known limitation in the `dm_followup_no_issue` regex** (carried
forward, not fixed in this phase): the pattern doesn't catch every
real-world phrasing — e.g. "respond my DMs omg" (a genuine bare
DM-follow-up, previously found and manually excluded during Phase 6C
golden-set labeling) is not matched by the current regex. This was
verified directly (`is_bare_dm_followup("respond my DMs omg") ==
False`) and is a known, pre-existing gap in this heuristic, not
something introduced or silently fixed in this phase.

## 8. Mega-thread handling (conversation 83694)

Explicitly inspected directly against the Phase 7A output:

- **62 messages** total in this reconstructed "conversation."
- **30 distinct participating accounts**: `SpotifyCares` (30 messages)
  plus **29 different individual customer accounts** (each with 1–2
  messages).
- **Root message**: `tweet_id=83694`, authored by `115888` (one of the
  four brand-family accounts), a promotional tweet: a 3-months-Premium
  discount broadcast — not a genuine customer complaint.
- **Why it's problematic**: the reply-chain reconstruction correctly
  (structurally) groups every reply to that one broadcast tweet into a
  single connected component, because they all trace back to the same
  root by the dataset's own `in_response_to_tweet_id` field. But this
  is ~29 independent, unrelated customers each asking their own
  question about a promo — not one coherent back-and-forth support
  interaction. Treating it as one "conversation" would let unrelated
  customers' messages appear as each other's "context," and would let
  a `SpotifyCares` reply to *customer A* get miscounted as relevant
  history for *customer B*'s problem.
- **Would-be candidate count**: pairing logic run without this
  exclusion would have generated **30 resolution candidates** from this
  one artifact (matching the 30 `SpotifyCares` messages, each replying
  to a different individual customer within the merged thread).
- **How excluded**: the entire `conversation_id == 83694` is removed
  from the working set before any pairing happens (§7) — **zero**
  candidates from this conversation appear in the final corpus,
  verified directly by both a unit test (`test_mega_thread_conversation_fully_excluded`)
  and the real-data smoke test.

No semantic claim is made about the content of any message in this
conversation beyond what's structurally observable (many distinct
authors, one shared broadcast root) — the exclusion is based entirely
on the participant-count/root-authorship pattern already documented in
prior phases, not on reading and judging individual message content.

## 9. Output schema

`data/processed/twitter/spotifycares_resolution_candidates.parquet`:

| Column | Type | Description |
|---|---|---|
| `resolution_id` | String | Deterministic: `RES-{conversation_id}-{brand_tweet_id}` |
| `conversation_id` | Int64 | From Phase 7A |
| `customer_tweet_id` | Int64 | The message the brand reply was addressed to |
| `customer_author_id` | String | |
| `customer_message` | String | Verbatim historical text |
| `customer_timestamp` | Datetime (UTC) | |
| `brand_tweet_id` | Int64 | |
| `brand_author_id` | String | Usually `SpotifyCares`; occasionally a co-participating support account |
| `brand_response` | String | Verbatim historical text |
| `brand_timestamp` | Datetime (UTC) | |
| `parent_tweet_id` | Int64 | The brand reply's own parent pointer (== `customer_tweet_id` by construction; kept for direct auditability) |
| `response_type` | String | One of `dm_redirect` / `acknowledgement` / `clarification_question` / `substantive_response` (§6) |
| `number_of_context_messages` | Int64 | Count of ancestor turns preceding the customer trigger message |
| `context_messages_json` | String (JSON) | Ancestor turns, root-first, `{tweet_id, role, author_id, text, timestamp}` each |
| `intent` | String, nullable | **Always null in this phase** — see below |
| `customer_source_row_id` | UInt32, nullable | Phase 7A row-index audit trail |
| `brand_source_row_id` | UInt32, nullable | Phase 7A row-index audit trail |

Sorted deterministically by `(conversation_id, brand_timestamp,
brand_tweet_id)`.

**Why `intent` is always null**: a deterministic intent label *is*
technically available for the small number of candidates whose
`customer_tweet_id` happens to match one of the 200 golden-set
examples (a simple join, no LLM). This was deliberately **not** done.
The golden set exists to evaluate the eventual system; if its labels
were joined into a corpus destined to become retrieval evidence for
that same system, a future retrieval/RAG build on top of this corpus
would risk leaking golden-set information into the evidence the system
retrieves from — exactly the golden/retrieval separation
`docs/GOLDEN_SET.md` and `CLAUDE.md` require. Keeping `intent` null
here (with the column present for future, carefully-scoped population)
was judged safer than a convenient but risky join.

## 10. Full-corpus statistics (MEASURED, full run)

| Metric | Value |
|---|---|
| Source rows (Phase 7A input) | 91,889 |
| Conversations inspected | 28,280 |
| **Resolution candidates produced** | **42,528** |
| `substantive_response` | 20,409 (48.0%) |
| `dm_redirect` | 13,059 (30.7%) |
| `clarification_question` | 8,861 (20.8%) |
| `acknowledgement` | 199 (0.5%) |
| `generic_template` | not implemented (null) — §6 |
| Conversations with no brand response at all | 0 |
| Excluded conversations (wholesale) | 1 (the mega-thread) |
| Excluded messages (total, all reasons) | 1,338 |
| Excluded candidate pairs (total, all reasons) | 645 |
| Duplicate resolution IDs found | 0 |
| Missing required fields | 0 for all of `conversation_id, tweet_id, author_id, role, timestamp, text` |
| Candidates with multi-turn context (>0 prior messages) | 15,705 (36.9%) |
| Max context depth observed | 25 prior messages |

`conversations_with_no_brand_response: 0` means every SpotifyCares
conversation in this dataset received at least one brand reply — this
matches Phase 1's dataset-selection finding that SpotifyCares has a
94.0% conversation-closure rate; it does not mean every customer
message got an individual reply.

## 11. Representative historical examples

All verbatim from the corpus (`@`-mentions/links left as-is, exactly
as extracted — no paraphrasing).

**Multi-turn, substantive** (`RES-1875-1873`, 7 prior context
messages):
```
Customer: [device/OS details from earlier turns omitted here; see JSON]
...
Customer: 1.0.65.320.gac7a8e02
Brand:    Thanks! It's not ideal, but a clean reinstall of the app
          should help out: https://t.co/EqisDMwZAT. Let us know how
          it plays out /KB
```
(`response_type: substantive_response`, `number_of_context_messages: 7`)

**DM redirect** (`response_type: dm_redirect`):
```
Customer: @SpotifyCares doesn't work and i even tried deleting the app
Brand:    @115887 Could you send us a DM with your account's email
          address? We'll take a look backstage /CH
          https://t.co/ldFdZRiNAt
```

**Clarification question** (`response_type: clarification_question`):
```
Customer: i'm pissed my @115888 shuffle and repeat button just don't
          fucking work and i'm getting frustrated
Brand:    @115887 Hey! What device, operating system, and Spotify
          version are you using? We'll see what we can suggest /CB
```

**Acknowledgement** (`response_type: acknowledgement`) — illustrates
the length-heuristic's limits (this is the tail end of a longer
resolved thread, not a full standalone answer):
```
Customer: @SpotifyCares They're back now. I was on my phone's 4g
          earlier. I don't know what happened but when I connected to
          my wifi it returned. Thank you thou
Brand:    @116890 2: with anything else. https://t.co/m4HWSbgHVZ ...
```
This is a real, verbatim artifact of a brand reply split across two
tweets ("1: ... 2: ..."); only the second half was linked as this
candidate's direct response, which is why it reads as a fragment. This
is documented as a known limitation (§12), not corrected by inference.

## 12. Known limitations

- **Response-type classification is structural, not semantic.** Length
  and punctuation are proxies, not ground truth. The
  `acknowledgement` example above shows a genuinely truncated
  multi-part reply being classified by its shorter half.
- **`generic_template` is not implemented** (§6) — a deliberate,
  documented gap rather than a rushed approximation.
- **`dm_followup_no_issue` regex has known coverage gaps** carried
  forward from earlier phases (§7).
- **`substantive_response` ≠ "this solved the customer's problem."**
  It is the largest bucket (48%) precisely because it's the default for
  anything that isn't short, a question, or a DM ask — it includes
  genuinely helpful troubleshooting steps and policy explanations
  alongside some multi-part-reply fragments and templated-but-real
  answers. No success/resolution signal exists in this dataset for most
  threads (no customer follow-up confirming the fix worked), which is
  exactly why this corpus is named "resolution candidates," never
  "resolutions."
- **Brand-side co-participants**: `brand_author_id` is occasionally not
  `SpotifyCares` (e.g. `hulu_support`, `AppleSupport` — see
  `docs/PHASE_7A_RECONSTRUCTION.md` §4) when a SpotifyCares conversation
  legitimately crosses into another brand's support scope (e.g. the
  Spotify+Hulu bundle). This is intentional (structural, not filtered
  by author identity) and documented, not a bug.
- **Mega-thread exclusion is currently a hardcoded single-conversation
  list** (`MEGA_THREAD_CONVERSATION_IDS = {83694}`), not a general
  broadcast-detection heuristic. Only the one conversation already
  found and documented in prior phases is excluded; a systematic
  detector for this pattern (e.g. "root authored by a brand-family
  account AND breadth above some threshold") was out of scope for this
  phase and would need explicit sign-off before being generalized.

## 13. Reproducibility commands

```
# Run the full test suite (Phase 7A + 7B unit tests, both smoke tests)
E:\hiver-support-agent\.venv\Scripts\python.exe -m pytest -v

# Run the full Phase 7B extraction (requires Phase 7A output to already exist)
E:\hiver-support-agent\.venv\Scripts\python.exe scripts\extract_resolution_candidates.py
```

Both commands should be run from the repository root
(`E:\hiver-support-agent`).

---

## Addendum — Phase 7C: Quality Filtering

Phase 7C quality-filters the 42,528 Phase 7B candidates into the
canonical historical evidence corpus. Implemented in
`src/data/corpus_filtering.py` (24 unit tests in
`tests/test_corpus_filtering.py` + 1 real-data smoke test in
`tests/test_corpus_filtering_smoke.py`). Never modifies this phase's
own Phase 7B output (`spotifycares_resolution_candidates.parquet`),
the Phase 7A output, the raw CSV, or any golden-set file — all
confirmed unchanged by checksum/timestamp before and after.

**Output**: `data/processed/twitter/spotifycares_resolution_corpus.parquet`
(41,092 rows — **96.6% retention** from 42,528 candidates), plus
`data/processed/twitter/spotifycares_corpus_quality.json`.

### Investigation before filtering

Measured (not assumed) across all 42,528 candidates first: length
distributions (customer messages 11–308 chars, brand responses 9–315
chars — no true empty text), context-message depth (median 0, max 25),
response-type mix (unchanged from Phase 7B), exact-duplicate
customer-message groups (1,616 groups / 3,567 rows — almost entirely
common short phrases like "Thanks!" from different real customers, not
pipeline artifacts), exact-duplicate brand-response groups (only 3
groups / 6 rows — brand replies are near-always unique because they
embed the customer's own @mention), and exactly one exact-duplicate
(customer_message, brand_response) *pair* — traced to a genuine
historical event (two different brand tweets, `2084661` and `2084664`,
both replying to the same customer tweet with near-identical wording —
a real double-send, not a bug — both preserved, per this phase's
explicit "preserve genuinely separate interactions" instruction.

### Broadcast-artifact investigation (generalized beyond conv 83694)

`docs/PHASE_7B_RESOLUTION_CORPUS.md` §8 only excluded conversation
83694. Phase 7C investigated whether similar artifacts exist elsewhere
**before** generalizing the rule, per instructions:

1. Computed conversation size for all 28,280 conversations. 24 have
   size ≥ 40; a further 43 have size 20–39 (67 total ≥ 20).
2. For each, computed the ratio of **distinct customer-role authors**
   to total messages. A genuine deep 1:1 conversation has a ratio near
   `1/size` (one person, many messages); a broadcast has a high ratio
   (many different people, each posting once or twice).
3. Manually inspected 11 conversations spanning the ratio spectrum,
   including deliberately-chosen **negative controls**:
   - `1698987` (43 msgs, ratio 0.093) — a genuine multi-party but
     **on-topic** public discussion about NAD-device Spotify Connect
     support — correctly NOT flagged by a ratio+root rule.
   - `1848141` (22 msgs, ratio 0.136) and `1175723` (20 msgs, ratio
     0.15) — legitimate deep single-customer troubleshooting with a
     minor "me too" chime-in — correctly NOT flagged.
   - `2211025` (26 msgs, ratio 0.5) — an organic feature-request
     "+1" pile-on **rooted in a genuine customer's own question**
     (Nintendo Switch app request) — **a true false positive** for a
     ratio-only rule, which is exactly why the adopted rule requires a
     second, independent signal (see below).
   - `67684`, `89471`, `79405`, `293875` — a **previously-undocumented**
     broadcast pattern: root authored by `SpotifyCares` itself (a
     service-status/outage announcement, e.g. "Something's not quite
     right, and we're looking into it"), with dozens of unrelated
     customers replying independently — structurally identical to the
     83694 pattern but not rooted in one of the 4 known brand-family
     accounts.
   - Several `115888`/`117153`-rooted promotional broadcasts
     (`141137`, `1942516`, and the large ones like `189825`, `44307`)
     — same pattern as 83694, confirming it generalizes.

**Adopted rule** (`identify_broadcast_conversations` in
`src/data/corpus_filtering.py`): flag a conversation only when **both**:
(a) `size >= 20` and `unique_customer_authors / size >= 0.20`, **and**
(b) the root message is authored by a known brand-family account
(115888/125633/117153/116130) **or** is itself a brand-authored
broadcast (role=brand, no parent — e.g. SpotifyCares' own outage
announcements). Requiring both signals is what correctly excludes the
`2211025`-style false positive while still catching every manually
verified true positive, including the newly-found SpotifyCares-rooted
outage-thread pattern. **Result: 49 conversations flagged** (up from
the single hardcoded `83694`), covering 2,795 raw messages and 1,240
would-be resolution candidates (of which 83694's were already excluded
in Phase 7B; the other 48 conversations' candidates are newly excluded
here).

**Explicitly not generalized further**: conversations sized 10–19 were
checked too (639 total; 93 have ratio ≥ 0.20) but were **not** included
in the detector — the false-positive risk is meaningfully higher at
that size (median ratio there is only 0.10, but individual small
conversations can easily have 2–3 legitimate participants), and this
range wasn't manually validated. This is a deliberate, conservative
scope boundary, not an oversight — see "Known limitations" below.

### Quality filters adopted

| Category | Rule | Exclude or flag? | Count |
|---|---|---|---|
| D. Known broadcast artifact | Generalized detector above | **Exclude** | 1,240 candidates (49 conversations) |
| A. Unusable text | Brand response has <3 meaningful chars after stripping @mentions/URLs (bare emoji or bare link) | **Exclude** | 2 candidates |
| Golden-set overlap (new category, see below) | `customer_tweet_id` or exact `customer_message` text matches a golden-set example | **Exclude** | 194 candidates |
| E. Low-information response | Customer message ≤3 real words (e.g. "Thanks!") | **Flag** (`low_info_customer_message`), retained | 2,258 candidates flagged |
| G. Suspicious cross-account interaction | `brand_author_id != "SpotifyCares"` (legitimate co-support, e.g. `hulu_support`) | **Flag** (`cross_brand_response`), retained | 75 candidates flagged (of 80 total in Phase 7B; some fell in excluded conversations) |
| B. Duplicate resolution evidence | Duplicate `resolution_id` (pipeline-artifact defense) | **Exclude if found** | 0 found |
| C. Malformed interaction | `brand_timestamp < customer_timestamp` (reply before trigger) | **Exclude if found** | 0 found (checked, none exist) |

**Deliberately NOT implemented as exclusions** (per explicit
instruction not to over-filter, all verified retained in the output):
DM redirects (13,059 before → 12,331 after — reduced only because some
happened to fall inside excluded broadcast/leakage conversations, not
because `dm_redirect` itself was targeted), clarification questions
(8,861→8,712), acknowledgements (199→196), short responses in general,
non-English examples, any particular intent, and multi-turn
conversations. A `response_type` of `dm_redirect` or `acknowledgement`
is metadata, not a quality judgment — all four types remain fully
retrievable in the corpus in comparable proportions to before
filtering (see `response_type_distribution_before/after` in the
quality JSON).

### Golden-set leakage: the most significant finding this phase

A deterministic exact-match check between the 200 golden-set examples
and the 42,528 candidates found **194 candidate rows (188 unique
golden tweet_ids) already present as resolution-candidate triggers** —
i.e. 94% of the golden set's underlying customer tweets already had a
real, structurally-generated resolution candidate in the Phase 7B
corpus, because both were built from the same 28,280-conversation
universe. Verified via two independent methods (exact `tweet_id` join
through `golden_set_candidates.jsonl`, and exact `customer_message`
string match against `golden_set_annotations.jsonl`) — both gave the
same 194 rows. **All 194 are excluded from the corpus** as the
`golden_set_overlap` reason.

An additional check for **normalized** near-duplicates (lowercased,
punctuation/@mentions/URLs stripped) found 8 more candidates — but
manual inspection showed these are short, generic phrases ("I need
help with my account", "Come on") independently typed by different
real customers on different tweets, not the same historical event.
These are **reported but not excluded** — excluding them would violate
the "preserve genuinely separate interactions" principle for no real
leakage benefit (see `spotifycares_corpus_quality.json`'s
`golden_set_leakage` block for the full list).

The 12 golden examples with no matching candidate at all were also
checked — none are `excluded=true` in the golden annotations, so this
is simply because their specific tweet never received a direct
structural reply in the reconstructed data (not a filtering artifact).

**This finding did not exist as a known risk before this phase.**
`docs/GOLDEN_SET.md` established the principle that golden examples
must never leak into retrieval evidence; this phase is the first point
in the pipeline where that principle was checked against real data and
found to require active enforcement, not just documentation.

### Known limitations (Phase 7C)

- The broadcast detector's size floor (20) and ratio threshold (0.20)
  are validated by manual inspection at that boundary, not swept
  exhaustively — conversations sized 10–19 with a high ratio are not
  covered (deliberately, see above).
- `low_info_customer_message` and `cross_brand_response` are flags,
  not filters — any future retrieval build must decide how to weight
  or use them; this phase makes no claim about their retrieval value
  beyond making them visible.
- The golden-set leakage check is exact-match + one normalized-match
  pass, not a fuzzy/semantic dedup (explicitly out of scope — no
  embeddings were used, per instructions). A future embeddings-based
  near-duplicate pass (Phase 7D+ or later) could find additional
  paraphrase-level overlap this phase cannot detect.

### Reproduction

```
E:\hiver-support-agent\.venv\Scripts\python.exe -m pytest -v
E:\hiver-support-agent\.venv\Scripts\python.exe scripts\filter_resolution_corpus.py
```
