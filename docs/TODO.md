# Project TODO / Phase Tracker

## Phase 0 — Environment Reconnaissance — DONE

Completed. Findings and recommendations in `docs/ENVIRONMENT.md`.

Summary: Python 3.12.6 available (no `.venv` yet), RTX 3060 Laptop GPU
(~6GB VRAM) with working CUDA, Ollama already installed with
`gemma2:9b-instruct-q4_0` pulled locally, several packages already
present globally (pandas, torch+cuda, sentence-transformers, fastapi,
pytest, etc.) but polars/duckdb/faiss are not installed anywhere yet.
Repo is not yet a git repository.

## Phase 1 — Dataset Reconnaissance & Brand Selection — DONE

Completed. Findings in `docs/DATA.md` and `research/dataset_reconnaissance.md`.
Brand decision and scoring in `research/brand_selection.md`.

Summary: `data/raw/twitter/twcs.csv` (2,811,774 rows, ~493MB) inspected
via chunked/streaming pandas without loading the whole file
unnecessarily. Reconstructed 798,197 conversations via reply-chain
grouping. Evaluated 14 brand candidates against a 10-criterion scoring
framework. **Selected brand: SpotifyCares** (43,265 tweets, 28,280
conversations, 94.0% conversation-closure rate, 30.8% DM-redirect rate,
~99.4% English, coherent single-product topic space suited to 6–12
intents). AppleSupport and Delta/AmericanAir documented as fallbacks.

## Phase 2 — Intent Discovery & Candidate Taxonomy — DONE

Completed. Findings in `docs/INTENTS.md` (taxonomy + quality check) and
`research/intent_discovery.md` (method, evidence, draft labeling guide).

Summary: sampled 210 real SpotifyCares conversations/messages (60
random + 15 long threads + a 150-message root-message sample) and ran
a full-corpus (28,221 root messages) regex keyword pass as a sanity
check. Manual reading gave much better coverage than the regex (which
undercounts intents like Content Availability where customers name a
specific song/artist instead of a generic problem word). **Proposed
taxonomy: 8 intents + OTHER/UNKNOWN** — Account Access & Login (~6%),
Account Security (~4%), Premium Subscription & Billing (~14%), App &
Playback Technical Issues (~19%), Content Availability & Catalog
Accuracy (~18%), Feature Request & Product Feedback (~18%), General
Complaint / Service Dissatisfaction (~5%), Country/Market Availability
Inquiry (~1%), OTHER/UNKNOWN (~13%). Banking77 was not inspected
directly (still not downloaded — out of scope); a note on its known
general structure is recorded as HYPOTHESIS only, not adopted. A
concrete "mega-thread" reply-chain artifact was found and documented
(`conv_id=83694`, a 62-message broadcast-reply thread misidentified as
one conversation) — must be handled before retrieval-corpus
construction. Taxonomy is a draft pending validation against real
golden-set labels, per CLAUDE.md.

## Phase 4 — Project Environment Setup — DONE

Completed. Full version table in `docs/TECH_STACK.md`.

Summary: created a project-local `.venv` at `E:\hiver-support-agent\.venv`
(Python 3.12.6, pip upgraded to 26.2.1, isolated from the global Python
install confirmed via `sys.prefix`). Installed only the requested
minimum data-engineering/evaluation set: pandas 3.0.5, polars 1.44.2,
duckdb 1.5.5, pyarrow 25.0.1, scikit-learn 1.9.1, python-dotenv 1.2.3,
pytest 9.1.1, matplotlib 3.11.2, datasets 5.0.1 — all installed
cleanly with no dependency conflicts. Verified all 8 import correctly
from the venv interpreter and ran a live DuckDB query as a functional
check. Confirmed LangChain/LangGraph/FAISS/FastAPI/uvicorn/Streamlit/
torch/transformers/sentence-transformers are **not** present in
`.venv` (still global-only from Phase 0, correctly excluded here).
Pip cache redirected to `E:\hiver-support-agent\.pip-cache` since `C:`
has very little free space (~9GB) — everything project-related now
lives entirely under `E:\hiver-support-agent`. No classifier, RAG,
embeddings, or model downloads were built/performed; `data/raw/twitter/twcs.csv`
was not touched; Banking77 was not downloaded.

## Phase 5 — Golden Evaluation Set Design — DONE

Completed. Design + rationale in `docs/GOLDEN_SET.md`; full method and
evidence in `research/golden_set_sampling.md`.

Summary: designed and executed a reproducible sampling pipeline
(seed 12345) over the existing SpotifyCares conversation subset (no
re-read of the 493MB raw CSV needed — reused the Phase 1/2 artifact) to
produce a **200-example unlabeled golden-set candidate file**:
`data/golden/golden_set_candidates.jsonl` (full audit metadata) plus
`data/golden/golden_set_annotation_blind_shuffled.jsonl` (the file to
actually hand to a human annotator — customer message + empty label
fields only). Composition: **Group A** (120, natural-distribution
random sample) + **Group B** (80 = 20 × 4, deliberate oversampling of
the four intents Phase 2 flagged as thin: Account Access & Login,
Account Security, General Complaint, Country/Market Availability) via
regex candidate pools that are sampling filters only, never treated as
ground truth. Excluded 568 root messages before sampling (373 from
4 newly-identified "brand-family" accounts wrongly labeled as
customers — see below — plus 138 fragments and 60 bare DM-follow-ups),
then capped 1 example per `author_id` (removing 1,730 more) to prevent
any single repeat-tweeter from occupying multiple slots. **No human
labeling was performed** — every `primary_intent` is `null`, per
instructions not to fabricate labels.

**New data-quality finding**: discovered 4 recurring `author_id`s
(115888, 125633, 117153, 116130 — 373 root messages combined) that are
official Spotify marketing/status accounts, not real customers,
mislabeled `inbound=True` because they aren't in the 108 known
*support* handles from Phase 1. This is the root cause of the Phase 2
`conv_id=83694` mega-thread artifact (its root tweet turned out to be
authored by account 115888) — excluding these 4 accounts prevents that
whole class of artifact, not just the one known instance, and
`conv_id=83694` is confirmed absent from the final 200.

## Phase 6A–6D — Golden Set Calibration, Full Labeling & Taxonomy Finalization — DONE

Completed (superseding the earlier placeholder "Phase 6 — Data
Processing" entry that used to be here; that work is now Phase 7A
below). Summary across the four sub-phases:

- **6A**: built `scripts/annotate_calibration.py` (interactive human
  annotation tool) and a 25-example calibration batch; found and fixed
  a persistence bug (nav-command interception swallowing "no" answers).
- **6B/6C**: human-labeled the 25-example calibration batch, reviewed
  it (`docs/GOLDEN_CALIBRATION_REVIEW.md`), then labeled the remaining
  175 candidates and merged all 200 into
  `data/golden/golden_set_annotations.jsonl` — **the golden set is now
  fully labeled** (200/200, `docs/GOLDEN_SET_ANNOTATION_REVIEW.md`).
- **6D**: investigated and finalized the Account Access & Login vs. App
  & Playback Technical Issues tie-break rule
  (`docs/TAXONOMY_CONFLICT_REVIEW.md` →
  `docs/TAXONOMY_CONTRACT_FINAL.md`), updating `docs/INTENTS.md` and
  `docs/GOLDEN_ANNOTATION.md`. **Not yet reapplied to the existing 200
  labels** — 1 known flip (GOLD-0126) and 2 cases needing
  re-examination (GOLD-0065, GOLD-0052) remain open, per
  `docs/TAXONOMY_CONTRACT_FINAL.md`.

## Phase 7A — Historical Conversation Reconstruction — DONE

Completed. Full report in `docs/PHASE_7A_RECONSTRUCTION.md`.

Summary: built a deterministic, tested conversation-reconstruction
pipeline (`src/data/reconstruction.py`, 24 passing tests in `tests/`)
that reconstructs conversations purely from the TWCS dataset's own
`in_response_to_tweet_id` structural pointer (via a DuckDB recursive
CTE), restricted to SpotifyCares-qualifying conversations. Ran against
the full 2.8M-row raw CSV in ~31s, producing
`data/processed/twitter/spotifycares_conversations.parquet` (91,889
rows, 28,280 conversations) — figures match Phase 1's independently
computed numbers exactly. Zero rows dropped for data-quality reasons in
the SpotifyCares subset (no duplicates, no missing required fields, no
invalid timestamps). The known mega-thread/brand-family-account
artifacts (Phase 2/5) are intentionally **not** filtered out here —
this phase reconstructs faithfully from structure; a retrieval-corpus
consumer must still apply the Phase 5 exclusion list. Raw CSV and
golden-set files confirmed untouched (checksummed before/after).

## Phase 7B — Historical Resolution-Pair Extraction — DONE

Completed. Full report in `docs/PHASE_7B_RESOLUTION_CORPUS.md`.

Summary: built `src/data/resolution_extraction.py` (51/51 tests pass
across Phase 7A+7B suites) to pair customer messages with the actual
SpotifyCares/support replies posted to them, using only the Phase 7A
`parent_tweet_id` structural link (never chronological adjacency or
text similarity). Applied the Phase 5 exclusions at this stage —
mega-thread `conv 83694` (would have produced 30 candidates, now 0),
the 4 brand-family accounts (0 candidates ever had one as a direct
parent — the mega-thread was their only real contamination vector,
confirming they're complementary exclusions), fragments (537
candidates avoided), and bare DM-follow-ups (78 avoided) — 1,338
messages / 645 would-be candidates excluded in total, all itemized in
`data/processed/twitter/spotifycares_resolution_exclusions.json`, none
silently dropped. Produced **42,528 resolution candidates**
(`data/processed/twitter/spotifycares_resolution_candidates.parquet`):
48.0% substantive_response, 30.7% dm_redirect, 20.8%
clarification_question, 0.5% acknowledgement (deterministic/structural
classification only — no LLM). Multi-turn context preserved via a
compact per-candidate JSON ancestor-chain column (36.9% of candidates
have nonzero context, max depth 25). `intent` field present but
deliberately left null for every row — joining golden-set labels was
considered and rejected to keep the golden set firewalled from any
corpus destined for retrieval. Phase 7A output, raw CSV, and all three
golden-set files confirmed untouched (checksummed before/after).

## Phase 7C — Historical Resolution Corpus Quality Filtering — DONE

Completed. Full details appended as an addendum to
`docs/PHASE_7B_RESOLUTION_CORPUS.md` (no new phase-specific file
created, per this phase's own instruction). 76/76 tests pass across
Phases 7A+7B+7C.

Summary: built `src/data/corpus_filtering.py` to quality-filter the
42,528 Phase 7B candidates into
`data/processed/twitter/spotifycares_resolution_corpus.parquet`
(**41,092 rows, 96.6% retention**). Investigated the corpus first
(lengths, duplicates, response-type mix) before filtering, per
instructions — found duplicates are almost entirely legitimate
separate customers using common phrases, not pipeline artifacts (0
duplicate resolution IDs). **Generalized the mega-thread detector**
beyond the single hardcoded `conv 83694`: validated a two-signal rule
(high customer-diversity ratio AND a broadcast-shaped root) against 11
manually-inspected conversations, including a confirmed false positive
(`conv 2211025`, an organic feature-request pile-on) that the final
two-signal rule correctly excludes from flagging — result: **49
conversations** flagged (up from 1), 1,240 candidates removed.
**Most significant finding**: a deterministic golden-set leakage check
found 194 resolution candidates (188 unique tweets, 94% of the golden
set) were already present in the Phase 7B corpus, since both were
built from the same conversation universe — all 194 excluded as
`golden_set_overlap`. Also excluded 2 candidates with unusable
(emoji/link-only) brand responses. Added non-destructive quality flags
(`low_info_customer_message`: 2,258; `cross_brand_response`: 75) rather
than excluding short responses, DM redirects, or cross-brand replies,
per the explicit "do not over-filter" instruction. Phase 7A, Phase 7B,
raw CSV, and all golden-set files confirmed untouched (checksum/
timestamp verified before and after).

## Phase 7D — Intent Assignment for Historical Resolution Corpus — DONE

Completed. 114/114 tests pass across Phases 7A–7D. No new
phase-specific doc created, per this phase's own instruction — details
recorded here only.

Summary: built `src/intent/deterministic_classifier.py`, a regex/
keyword rule engine applying the finalized 9-intent taxonomy
(`docs/TAXONOMY_CONTRACT_FINAL.md`) to the Phase 7C corpus, with the
finalized Account-Access-vs-Technical tie-break and the other
documented tie-breaks (Technical vs. Content, Feature vs. Complaint,
Country/Market vs. Content) implemented as an explicit rule-priority
order. **Not fit, tuned, or validated against the golden set at any
point** (grep-verified: no golden-set reference in the classifier or
its tests). Output:
`data/processed/twitter/spotifycares_intent_corpus.parquet` (41,092
rows, same as Phase 7C — no rows added/removed, only 7 new columns).

**Deterministic coverage: 31.5%** (12,929 labeled / 28,163 OTHER/
UNKNOWN). This is intentionally low — the rules require explicit,
high-precision textual evidence (named entities, specific keywords,
technical identifiers), per the explicit instruction not to optimize
for coverage. Manual audit (40 seeded OTHER examples + 6 seeded
examples per labeled intent) found one real bug (smart/curly
apostrophes weren't matched by any regex, silently suppressing many
true matches — fixed via a normalization pass) and confirmed no
systematic confusion in the specific pairs called out for scrutiny
(billing/security, login-UI/access, missing-songs/technical, feature/
complaint, country/content) — precision looked good in every sampled
bucket.

**Model-assisted labeling was attempted, not adopted.** Piloted the
local Ollama `gemma2:9b-instruct-q4_0` model per instructions, but it
failed reproducibly at the infrastructure level (`Error: 500 Internal
Server Error: llama runner process has terminated`) on two separate
attempts, including a trivial non-classification prompt — this is an
environment/runtime failure, not a taxonomy or prompting problem. Per
the "stop and report" instruction for anything beyond the working
local setup, no hosted-model fallback was attempted without approval.
The corpus ships with the deterministic-only result; the 68.5% OTHER/
UNKNOWN bucket is unlabeled pending a decision (see below).

**Decision needed before Phase 7E**: either (a) debug/fix the local
Ollama runtime and re-attempt the small-audited-sample pilot described
in this phase's instructions, or (b) approve a hosted-model
alternative, or (c) accept the 31.5%-labeled corpus as sufficient and
move on. None of these was decided in this phase.

## Phase 7E — Residual OTHER/UNKNOWN Investigation — DONE

Completed. No new phase-specific doc created, per this phase's own
instruction — details recorded here only. Production classifier
(`src/intent/deterministic_classifier.py`) and the authoritative
`spotifycares_intent_corpus.parquet` were **not modified** this phase
(checksum/mtime-verified before and after: intent corpus and quality
report both still 2026-09-16 09:39:10, resolution corpus still 09:17:32,
all 6 golden-set file checksums unchanged from Phase 7D).

Drew a seeded sample (seed=42, n=2,000 of 28,163) from the OTHER/
UNKNOWN bucket and bucketed it with *loose, exploratory* keyword
heuristics (`scripts/analyze_other_bucket.py`, deliberately separate
from and broader than the production regexes) into 13 categories →
`data/processed/twitter/spotifycares_other_analysis.json`. Result:
**79.5% ("A_genuinely_other") showed no signal for any of the 8
substantive intents at all** — mostly short reactive replies, vague
acknowledgements, or genuinely ambiguous text. Recoverable-looking
candidates were small and, on manual audit, mostly lower-precision
than they first appeared — e.g. the loose "D_billing" bucket (6.1% of
sample) was mostly false positives: bare mentions of "premium" in
messages that were actually about connectivity, ads, or account-type
confusion, not billing actions. The loose "C_security" bucket (0.2%)
was 0/4 genuine on audit (generic "someone else" phrasing, not
compromise language) — confirms the production classifier's stricter
compromise-verb requirement is well-calibrated, not overly strict.

Audited genuine vocabulary gaps in 4 already-existing production rule
categories and built an isolated experimental variant
(`scripts/experimental_other_recovery.py`, imports but does not alter
the production classifier) to measure them against the full 28,163-row
OTHER bucket:

1. **Technical**: missing vocabulary — "glitch(y/ing)", bare "error"
   (production required "error message" literally), "deactivat(ed/ing)",
   "stuck ... loading", and "still/constantly skipping" (production only
   matched "keeps? skipping"). → 351 recovered, audit sample (n=15)
   ~87% precision (2 borderline: "deactivating my account" is
   arguably Access, not Technical).
2. **Content**: "`<song/album/track>` ... is not available" mid-sentence,
   without requiring the literal "on/available on/in spotify" suffix the
   production pattern demands. → 56 recovered, audit sample (n=15)
   100% precision.
3. **Country/Market**: the production whole-service alternation lists
   "the app"/"this app" but not "your app"/"your service" — a common
   second-person phrasing ("why is your app not available in India").
   → 8 recovered, audit sample (n=8, full set) 100% precision.
4. **Feature**: the production wish-pattern requires the literal words
   "you"/"spotify"; this dataset anonymizes the brand handle as a
   numeric `@mention` (e.g. `@115888`), so "I wish @115888 had..." was
   systematically missed. → 2 recovered, both correct on audit (tiny n).

**Total experimental recovery: 417 rows (1.48% of the OTHER bucket,
1.01% of the full 41,092-row corpus)** — a real but modest,
high-precision gain, written only to
`data/processed/twitter/spotifycares_other_recovery_experiment.json`
(experimental, not applied to production).

**Model-assisted experiment**: attempted per instructions. Local Ollama
failed identically to Phase 7D — reproduced via both the CLI
(`ollama run gemma2:9b-instruct-q4_0`) and the raw HTTP API
(`POST /api/generate`), and on a second model (`cow/gemma2_tools:9b`)
too, all returning the same `llama runner process has terminated`
error. This rules out a CLI-specific bug and points to a systemic local
runtime/driver issue. Per instructions, did not spend further time
debugging infrastructure and did not fall back to a hosted model
without approval — Step 3's LLM-assisted labeling pass was not run.

**Decision: (B)** — a small number of high-precision deterministic
patterns are clearly recoverable (the 4 rules above), each addressing a
genuine vocabulary/phrasing gap in an existing rule category rather
than a new pattern class. Per this phase's explicit "must not silently
alter production" constraint, the 4 rules are **proposed, not
applied** — the production classifier and corpus are unchanged pending
review. The much larger 79.5%-genuinely-OTHER finding suggests the
ceiling on deterministic recovery is low; a meaningful jump above ~33%
overall coverage would require the model-assisted pass Ollama currently
blocks, not more regex tuning.

**Decision needed before Phase 8**: (a) approve applying the 4 proposed
rules to production (est. coverage 31.5% → ~32.5%), (b) fix the local
Ollama runtime (now confirmed to be a systemic driver/runtime issue,
not CLI or model-specific) and retry model-assisted labeling, (c)
approve a hosted-model alternative, or (d) accept the deterministic-only
corpus as final. None of these was decided in this phase.

## Phase 8 — Historical Resolution Retrieval — DONE

Completed. No new phase-specific doc created, per this phase's own
instruction — details recorded here only. Built into the correctly-
spelled `data/retrieval/` (the pre-existing `data/retriveal/` typo
directory was left empty and untouched, not renamed, to avoid touching
anything not part of this phase's explicit file list).

**Dependencies installed** (pre-approved by this phase's own
instructions): `torch` (CPU wheel, via `--index-url
https://download.pytorch.org/whl/cpu`), `sentence-transformers`,
`faiss-cpu`. No LangChain/LangGraph/vector-DB framework installed.

**Retrieval unit**: one row per Phase 7B/7C resolution candidate
(`retrieval_id` == `resolution_id`), carrying customer_message,
brand_response, primary_intent (Phase 7D), response_type, a *compact*
`context_root_message` (just the conversation root's text, not the
full context blob) rather than embedding raw conversations, plus
timestamps and quality flags. Embedding text is the customer_message
alone, except for `low_info_customer_message` rows where the root
message is prepended — this reuses the same root-context-fallback
philosophy as Phase 7D's classifier rather than inventing a new
convention. Full schema and rationale: `src/retrieval/index.py`.

**Embedding model**: `sentence-transformers/all-MiniLM-L6-v2`, 384-dim,
L2-normalized at encode time, CPU only. Embedding throughput ~180
rows/sec; embedding the full 41,092-row corpus took ~229s.

**Index**: `faiss.IndexFlatIP` (exact, no ANN tuning needed at 41k
scale) over the normalized vectors == cosine similarity. Metadata
(`spotifycares_metadata.parquet`) and raw vectors
(`spotifycares_vectors.npy`, needed for intent-filtered brute-force
search) are positionally aligned with the FAISS index 1:1 — verified
by unit test and by a runtime shape check in `Retriever.__init__`.

**Golden-set isolation**: independently re-verified (not trusted from
Phase 7C) via exact `tweet_id` and exact `customer_message` matching
against both `golden_set_candidates.jsonl` and
`golden_set_annotations.jsonl` — **0 matches found**, confirming
Phase 7C's exclusion already fully removed golden overlap before this
phase ever ran. All 41,092 rows were indexed (0 excluded).

**Retrieval quality** (seed=99, n=1,000 sampled queries, leave-one-out
self-exclusion; see `spotifycares_retrieval_evaluation.json`):
Global Recall@1/3/5/10 = 56.2% / 73.8% / 79.4% / 87.3%; same-intent@k
56.2% → 49.5% (decreasing with k, as expected). Intent-filtered
same-intent@k is 1.0 at every k **by construction** (the candidate
pool is pre-restricted to the query's own intent) — this is
tautological, not evidence intent-filtering is "better."

**Manual audit** (40 seeded examples, full transcripts + judgments in
the evaluation JSON): 47.5% good (genuinely similar problem + usable
evidence), 35% partial (topically related but not specific, or
evidence weak/DM-redirect-limited), 12.5% poor (lexical-only match or
context-insufficient query), 5% not-evidence-seeking (bare
acknowledgements correctly matched to other acknowledgements).
Notable failure modes: lexical-similarity-without-problem-similarity;
context-dependent queries where the real problem is in an earlier,
unseen turn (bare version strings, "same on both devices"-style
follow-ups); one clear sentiment/negation-blindness case ("I'll never
leave you for Apple Music" retrieved for "I'm unsubscribing... to
Apple Music"); and — encouragingly — several cases where embedding
similarity recovered genuinely relevant neighbors that Phase 7D's
intentionally low-coverage deterministic classifier had labeled
OTHER/UNKNOWN.

**Global vs. intent-filtered** (Step 8, no winner declared without
evidence): of 13 non-OTHER queries in the manual sample, 7 had
different top-3 results between modes. Intent filtering clearly
**helped** twice (removed cross-intent noise for a Technical query;
surfaced closer Complaint-labeled neighbors). It clearly **hurt** once
in a concrete, important way: a joking/ambiguous use of "hacked" (about
a Discover Weekly playlist, not a real compromise) got confidently
routed to literal account-hijacking cases under intent filtering —
exactly the kind of "confidently wrong" failure a downstream reply
generator must not be handed uncritically. It also lost otherwise-good
OTHER-labeled matches for one Feature Request query. **Recommendation
for Phase 9/10**: default to global retrieval; treat intent-filtering
as an optional narrowing signal only when the deterministic intent is
non-OTHER *and* the caller has some independent confidence in it — not
a blind default.

**Duplicates**: 1,571 exact-duplicate customer-message groups (3,429
rows) exist in the indexed corpus — consistent with Phase 7C's
already-reported duplicate counts. Not deduplicated (real repeated
support patterns, per this phase's explicit instruction not to
aggressively deduplicate without evidence), but flagged so recall
numbers aren't over-read as proof of semantic generalization.

**Files created**: `src/retrieval/{__init__.py,embeddings.py,index.py,retriever.py}`,
`tests/test_retrieval.py` (16 tests), `tests/test_retrieval_smoke.py`
(22 tests), `scripts/build_retrieval_index.py`,
`scripts/evaluate_retrieval.py`,
`data/retrieval/{spotifycares.index,spotifycares_vectors.npy,spotifycares_metadata.parquet,spotifycares_retrieval_quality.json,spotifycares_retrieval_evaluation.json}`.
No source corpus or golden-set file modified (checksum/mtime-verified
before and after: intent corpus still 2026-09-16 09:39:10, resolution
corpus still 09:17:32, all 6 golden checksums unchanged).

**Tests**: 152/152 passing (114 prior + 38 new).

**Decision needed before Phase 9**: none blocking — retrieval is
usable as global-by-default evidence for reply generation, with
intent-filtering available as an optional, non-default narrowing tool.
The larger open decision from Phase 7E (whether to raise deterministic
intent coverage) still stands independently and does not block Phase 9
retrieval usage.

## Phase 9 — Grounded Reply Generation + Escalation Policy — DONE

Completed. No new phase-specific doc created, per this phase's own
instruction — details recorded here only.

**Architecture**: `src/agent.py`'s `SupportAgent.handle()` orchestrates
five independently-testable components: the existing Phase 7D
deterministic classifier (`src/intent/deterministic_classifier.py`,
reused unmodified — no second classifier, no Phase 7E experimental
rules applied), the existing Phase 8 `Retriever` (global by default;
intent-filtering is an explicit opt-in only, never automatic), a new
evidence-sufficiency assessor (`src/evidence.py`), a new LLM
generation layer (`src/generation/`), and a new deterministic
escalation policy (`src/escalation/policy.py`).

**LLM status — changed since Phase 7D/7E**: the local Ollama
`gemma2:9b-instruct-q4_0` runtime, which failed reproducibly in both
prior phases, **is working again** as of this phase (verified via the
raw HTTP API and through `LocalLLMClient` in `src/generation/llm_client.py`).
Per instructions ("if it works now, use it"), it is now the default
generator backend, wrapped behind an `LLMClient` abstract interface so
a hosted provider could be added later without touching
`src/generation/generator.py` or `src/agent.py`. No hosted model was
used.

**Evidence assessment** (`src/evidence.py`): built on a concrete,
non-obvious finding from Phase 8's own manual audit — top-1 similarity
score does NOT reliably separate good retrieval matches from poor ones
on this corpus (audited "poor" matches averaged HIGHER similarity,
0.91, than audited "good" matches, 0.84, because short/generic
messages like bare version strings score spuriously high against each
other). Similarity is therefore used only as a low floor (<0.45), not
the primary signal; the primary signals are structural: fraction of
retrieved responses that are acknowledgements/DM-redirects (weak
evidence), how many distinct intents the top-k span (scattered
evidence), and whether the customer's own message is a bare/low-word-count
follow-up. All thresholds are named constants, not tuned against any
labeled set.

**Escalation policy** (`src/escalation/policy.py`): a fixed,
deterministic priority order — EXPLICIT_HUMAN_REQUEST >
SECURITY_RISK > UNSUPPORTED_ACTION > CONFLICTING_EVIDENCE >
INSUFFICIENT_EVIDENCE > LOW_CONFIDENCE > NONE. Escalation is never the
LLM's own opinion; the one place generated text is consulted at all is
a post-generation regex safety-net that catches a reply claiming an
action the system cannot perform (e.g. "I've issued a refund") and
both escalates AND overrides that reply with the safe fallback before
it can reach the customer. Account Security escalates by default
unless the top retrieved case is itself Account-Security-labeled, a
substantive (non-DM-redirect) response, and highly similar (≥0.75) —
otherwise the system never invents a recovery procedure or claims an
account was secured. OTHER/UNKNOWN intent alone, and low similarity
alone, do NOT force escalation, per instructions.

**Fallback behavior**: a fixed, generic, non-fabricated message ("I'm
sorry you're having trouble with this. This issue may need further
assistance from Spotify Support.") is used whenever `generation_status`
is `llm_unavailable` or `generation_error`; verified to contain no
unsupported-action language via the same regex the escalation policy
uses. The full pipeline is exercised with a forced-unavailable LLM
client in `tests/test_agent_smoke.py` to guarantee it never depends on
a live model to run.

**Real-data smoke test** (Step 12, live Ollama, one representative
message per intent): all 9 canonical intents plus OTHER produced
coherent, grounded, structured JSON replies; Account Security and
"speak to a human" correctly escalated; Billing/Complaint/OTHER
correctly triggered INSUFFICIENT_EVIDENCE when retrieved evidence was
mostly DM-redirects or acknowledgements; Feature/Technical/Content/
Market cases with strong substantive historical evidence correctly did
NOT escalate. One cosmetic limitation observed: the model sometimes
copies a historical response's tracking link or brand agent signature
(e.g. `/MA`, a `t.co` link) near-verbatim rather than fully
paraphrasing — not fabrication (the link/signature is real, sourced
from retrieved evidence) but still a "copied rather than adapted"
pattern the prompt asks it to avoid; left as a known limitation rather
than over-engineering the prompt this phase.

**Files created**: `src/agent.py`, `src/evidence.py`,
`src/generation/{__init__.py,llm_client.py,prompts.py,generator.py}`,
`src/escalation/{__init__.py,policy.py}`, `scripts/run_agent.py`,
`tests/{test_generation.py,test_escalation.py,test_agent.py,test_agent_smoke.py}`
(46 new tests). **Modified**: `docs/TODO.md` only. No source corpus,
retrieval index, or golden-set file touched.

**Dependencies added**: none new — `requests` (already installed) is
used for the Ollama HTTP call; no LangChain/LangGraph/vector-DB/web
framework added.

**Tests**: 196/196 passing (152 prior + 44 new unit/smoke tests for
this phase).

**Golden-set isolation**: golden data was not read, referenced, or
used anywhere in this phase's code or tests (grep-verified) — Phase
8's own leakage checks already cover the retrieval index this phase
reuses unmodified.

**CLI**: `.venv/Scripts/python.exe scripts/run_agent.py --message "..."`
(add `--intent-filter` to opt into intent-filtered retrieval, `--json`
for the full structured result).

**Known limitations carried into Phase 10**: (1) evidence thresholds
are reasoned/documented but not empirically calibrated against any
held-out labeled set (by design — golden set is evaluation-only); (2)
the model occasionally copies a historical link/signature verbatim
instead of fully paraphrasing; (3) Phase 7E's 68.5%-OTHER coverage
question is still open and directly affects how often this agent can
use intent-filtered retrieval at all; (4) Ollama's reliability has now
flipped twice (down in 7D/7E, up in 9) with no root cause identified —
treat it as unreliable infrastructure, not a fixed dependency, and
keep the deterministic fallback path exercised in CI-equivalent tests.

## Later Phases (not yet planned in detail)

- Baselines (majority-class, simple LLM classifier)
- Full evaluation harness (Phase 10: metrics, LLM-as-judge, human calibration)
- Evaluation harness (deterministic metrics + LLM judge + human calibration)
- Decision log (10–15 non-obvious decisions, per CLAUDE.md)
- Decide LocalLLMClient vs GroqLLMClient priority (Phase 0 hardware
  constraints: ~6GB VRAM caps local model size/quantization) before
  the generation/classification phases
