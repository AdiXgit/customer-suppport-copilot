# Decision Log

Non-obvious engineering and methodology decisions made over the course of
this project, with the reasoning behind each. No decision here is new —
this is a distilled record of choices actually made during development.

1. **Brand: SpotifyCares**, chosen over 4 other finalists (AmazonHelp,
   AppleSupport, Delta, AmericanAir) scored 1-5 on 10 criteria (volume,
   conversation quality, issue diversity, visible-resolution rate, data
   cleanliness, intent-classification suitability, RAG suitability,
   escalation-analysis suitability, evaluation feasibility).
   SpotifyCares scored highest (45/50) against Delta (40) and
   AmericanAir (39), winning mainly on topical coherence (one product ->
   a clean ~9-intent taxonomy) and the best visible (non-DM-hidden)
   historical-resolution rate of any strong candidate. See `docs/DATA.md`
   for the underlying dataset measurements this scoring was based on.

2. **Intent taxonomy derived from the brand's own data, not copied from
   Banking77.** Banking77 was explicitly scoped to intent-taxonomy-design
   inspiration only, never as resolution/brand-response evidence, per
   CLAUDE.md. See `docs/INTENTS.md`'s "Step 3 note" section — Banking77
   was never even downloaded in this project.

3. **9-intent taxonomy (8 support intents + OTHER/UNKNOWN)**, not a
   flatter or finer-grained scheme, chosen after a manual 150-message
   sample showed ~87% coverage with clean per-intent resolution patterns.
   See `docs/INTENTS.md` Step 5 (Taxonomy Quality Check).

4. **OTHER/UNKNOWN examples are excluded from the golden set rather than
   labeled and scored**, except for genuinely ambiguous-but-plausible
   cases, which route to ESCALATE by default. Rationale: forcing a bot to
   guess an intent it structurally can't identify from text alone is worse
   than declining to guess. See `docs/INTENTS.md`'s OTHER/UNKNOWN section.

5. **A deterministic tie-break rule for Account Access & Login vs. App &
   Playback Technical Issues**, added only after golden-set annotation
   surfaced real inconsistency in an earlier, unwritten version of the
   rule (2 discovered errors across 12 affected examples). The full,
   finalized rule (with a decision table and worked examples) lives in
   `docs/INTENTS.md`'s "Tie-Break" section.

6. **The taxonomy tie-break fix was NOT applied retroactively** to the
   already-labeled 200-example golden set — the golden set was labeled
   under an earlier, less precise version of the rule, and re-labeling it
   after the fact would have meant silently changing evaluation ground
   truth. The 12 examples this affects are a known, accepted limitation
   rather than a corrected error.

7. **Golden-set labeling is a mixed-provenance process, disclosed as
   such**: 25 of 200 examples were labeled by a genuine human annotator
   (the calibration batch); the remaining 175 were labeled by Claude
   reading each message directly against the taxonomy contract, not by an
   independent human and not via a separate LLM API call. See the
   "Evaluation methodology" section of `README.md`. This project does not
   claim "200 independently human-labelled examples."

8. **LLMClient abstraction with only `LocalLLMClient` (Ollama) actually
   implemented**; `GroqLLMClient` was scoped in CLAUDE.md but never built,
   since a local model was sufficient for the evaluation and no API key
   was ever required. See `src/generation/llm_client.py`.

9. **A single bounded retry (not a retry loop) for Ollama cold-start
   flakiness**, added after the same `llama runner process has
   terminated` transient failure was observed across four separate
   phases (7D, 7E, 9, 10). Explicitly scoped as absorbing a known,
   recorded flake, not a debugging effort — two consecutive failures
   still raise immediately. See `src/generation/llm_client.py`'s
   module docstring.

10. **Evidence-sufficiency and escalation thresholds are reasoned, not
    calibrated against labeled data**, and were deliberately NOT retuned
    after seeing evaluation results (`evaluation/evidence_validation.py`'s
    docstring, `data/evaluation/evidence_threshold_validation.json`), per
    CLAUDE.md's "do not optimize against the test set" rule. The
    evaluation surfaced a measurable over-escalation pattern as a result
    (see `data/evaluation/evaluation_summary.json`, failure mode #2) —
    left unfixed intentionally, to report as a finding rather than
    quietly patch before scoring.

11. **The 50-example "human calibration" set is an LLM proxy (Claude),
    not a genuine human reviewer**, disclosed explicitly via an
    `annotator_type` field on every record rather than silently
    substituted. This was a live decision made mid-project when no human
    annotator was available — see `docs/FINAL_REPORT.md`'s Limitations
    section (10) for what this does and doesn't establish.

12. **`escalation_metrics()` was extended to accept boolean/None inputs
    in addition to the original 'yes'/'no'/'uncertain' strings**, instead
    of migrating the whole codebase to one schema, to keep the original
    Phase 10 template design working for any future genuine-human relabel
    while matching Phase 11's boolean field spec. See
    `evaluation/metrics.py`'s `escalation_metrics` docstring.

13. **Golden evaluation data is never used as retrieval/RAG evidence.**
    Enforced by construction (the retrieval index is built only from
    `data/processed/twitter/spotifycares_intent_corpus.parquet`, not from
    golden-set files — see `scripts/build_retrieval_index.py`'s header)
    and verified by a dedicated `SpyAgent`-based unit test
    (`tests/test_evaluation_runner.py`) that asserts golden fields never
    appear in the actual runtime arguments passed to the agent.

14. **The raw 493MB Twitter CSV is excluded from version control**, with
    processed Parquet derivatives (each a few MB) kept instead. This
    breaks strict "processed data reproducible from raw data" reproducibility
    for someone without the original Kaggle download, but keeping a
    half-gigabyte file out of a public repo was judged the higher
    priority — see `.gitignore` and Section "How to reproduce" in
    `README.md`.

15. **The FAISS index and raw embedding vectors (`.index` / `.npy`,
    ~122MB combined) are excluded from version control** in favor of the
    smaller `spotifycares_metadata.parquet` (~5.5MB, kept), since the
    index is mechanically regenerable from already-committed processed
    data via `scripts/build_retrieval_index.py` and isn't itself a claim
    or a result that needs to be preserved verbatim.
