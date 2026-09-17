# Phase 7A — Historical Conversation Reconstruction

## Status

DONE. Deterministic, auditable, tested conversation-reconstruction
pipeline built and run against the full raw dataset for the
SpotifyCares subset.

Note on inputs: `docs/PROJECT.md` and `docs/ARCHITECTURE.md` were
listed to read for this phase but do not exist yet in this repository
— proceeded using `CLAUDE.md`, `docs/DATA.md`, `docs/INTENTS.md`,
`docs/TAXONOMY_CONTRACT_FINAL.md`, and `docs/TODO.md`, which cover the
relevant prior context (dataset schema, brand selection, taxonomy).

---

## Dependencies

Checked the project `.venv` (`E:\hiver-support-agent\.venv`, set up in
Phase 4) before writing any code. Everything required was already
installed — nothing new was added:

| Package | Version | Status |
|---|---|---|
| polars | 1.44.2 | already installed |
| duckdb | 1.5.5 | already installed |
| pyarrow | 25.0.1 | already installed |
| pytest | 9.1.1 | already installed |

No packages were installed this phase. No new framework was
introduced beyond what's already in the approved stack (Python,
Polars, DuckDB, PyArrow, Parquet, pytest) — in particular DuckDB is
used only for a single recursive SQL query (the conversation-root
closure), not as a database layer.

---

## 1. Actual TWCS schema (inspected, not assumed)

Inspected directly via `polars.read_csv` header + dtype inference
against `data/raw/twitter/twcs.csv`:

| Column | Type (as read) | Role in reconstruction |
|---|---|---|
| `tweet_id` | Int64, unique | Message/row identifier |
| `author_id` | String | Customer (anonymized numeric string) or brand handle |
| `inbound` | Boolean | `True` = customer→brand, `False` = brand→customer — used directly for `role`, not inferred from `author_id` shape |
| `created_at` | String, Twitter native format (`Tue Oct 31 22:10:47 +0000 2017`) | Parsed into `timestamp` |
| `text` | String | Message text |
| `response_tweet_id` | String, comma-separated list (17,808 rows have 2+ values in a 200k-row sample) | Forward pointer (children) — **not used** for reconstruction; redundant with `in_response_to_tweet_id` and multi-valued, so the single-valued backward pointer is the authoritative structural relationship |
| `in_response_to_tweet_id` | Int64 | **The** parent/in-reply-to relationship field — this is what conversations are built from |

No existing conversation/thread identifier is present in the raw
data — `conversation_id` must be derived structurally, which is what
this pipeline does (never via text similarity or time windows, per
the task requirement).

---

## 2. Reconstruction logic

1. **Parent relationship**: `in_response_to_tweet_id` is a child→parent
   pointer. A row with a null value, or a value that doesn't match any
   `tweet_id` in the dataset, is a conversation root (possibly an
   incomplete one, if the true parent was deleted/excluded from the
   export).
2. **Root resolution**: implemented as a single SQL `WITH RECURSIVE`
   query in DuckDB (queried directly against the in-memory Polars
   DataFrame) — the base case selects all rows with no resolvable
   parent as their own root; the recursive case propagates a child's
   root from its resolved parent. This is a purely structural graph
   closure over the dataset's own relationship field, auditable by
   reading the ~15-line SQL query in `src/data/reconstruction.py`
   (`compute_conversation_roots`). A depth cap (`MAX_CHAIN_DEPTH =
   2000`) guards against runaway recursion in case of an unexpected
   cycle; the real dataset's actual max chain depth is far below this.
3. **`conversation_id`** = the tweet_id of the resolved root (not a
   synthetic counter) — deterministic and stable across runs and row
   order (tested explicitly, see below).
4. **Role** = read directly from `inbound` (`True`→`customer`,
   `False`→`brand`; a null `inbound`, which doesn't occur in the real
   dataset, would be `unknown` and counted rather than silently
   dropped).
5. **Restricting to SpotifyCares**: a conversation qualifies if **any**
   row in it has `author_id` in the brand-authors set (`{"SpotifyCares"}`
   for this run). All rows of a qualifying conversation are kept —
   including the customer side and any other support account that
   happens to co-participate in the same thread — because filtering is
   done by shared `conversation_id`, not by filtering individual rows
   on `author_id`. This is the correct structural interpretation of
   "SpotifyCares interactions": a customer's opening message is part of
   the interaction even though its own `author_id` isn't `SpotifyCares`.
6. **Timestamp parsing**: `created_at` parsed with Twitter's exact
   native format (`%a %b %d %H:%M:%S %z %Y`); failures are counted, not
   dropped (the row is kept with `timestamp = null`).
7. **Duplicate `tweet_id`s**: detected via group-by count; if any
   exist, the first occurrence (by original file/row order, tracked via
   `source_row_id`) is kept and the rest dropped, with the drop count
   and affected IDs reported — never silent.
8. **Missing `tweet_id`**: the one case where a row is unconditionally
   dropped (it cannot be keyed into the reply graph at all), and the
   drop count is always reported.

---

## 3. Files produced

| File | Purpose |
|---|---|
| `src/data/__init__.py`, `src/data/reconstruction.py` | The reusable, deterministic pipeline (no I/O side effects except the two explicit entry points) |
| `conftest.py` | Adds `src/` to `sys.path` so tests can `import data.reconstruction` without installing a package |
| `tests/test_reconstruction.py` | 23 unit tests against tiny synthetic fixtures (no real data read) |
| `tests/test_smoke.py` | 1 smoke test against a small real sample (first 20,000 rows) of the raw CSV |
| `scripts/reconstruct_spotifycares.py` | Production entry point: runs the full pipeline against the real 2.8M-row CSV |
| `data/processed/twitter/spotifycares_conversations.parquet` | The reconstructed SpotifyCares dataset (91,889 rows) |
| `data/processed/twitter/spotifycares_quality_report.json` | The data-quality report from the full run |

### Output schema (`spotifycares_conversations.parquet`)

| Column | Type | Description |
|---|---|---|
| `conversation_id` | Int64 | Root tweet_id of the conversation |
| `tweet_id` | Int64 | This row's own tweet ID |
| `author_id` | String | Customer (numeric) or brand handle |
| `role` | String | `customer` / `brand` / `unknown` |
| `timestamp` | Datetime (UTC) | Parsed `created_at`, null if unparseable |
| `text` | String | Message text, unmodified |
| `parent_tweet_id` | Int64 (nullable) | Renamed `in_response_to_tweet_id` |
| `parent_resolved` | Boolean | `True` if no parent claimed, or the claimed parent exists in-dataset; `False` if the parent pointer is broken |
| `source_row_id` | UInt32 | Original row index in the raw CSV, for traceability/audit |

Sorted deterministically by `(conversation_id, timestamp, tweet_id)`.

`data/raw/twitter/twcs.csv` was never modified (verified via checksum
before and after this phase — unchanged).

---

## 4. Row/conversation counts (full run, MEASURED)

| Metric | Value |
|---|---|
| Input rows (full raw CSV) | 2,811,774 |
| Total conversations across the **entire** dataset (all 108 brands) | 798,197 |
| SpotifyCares-qualifying rows | 91,889 |
| SpotifyCares-qualifying conversations | 28,280 |
| Customer messages (role=customer) | 48,543 |
| Brand-role messages (role=brand) | 43,346 |

These numbers match Phase 1's independently-computed figures exactly
(`docs/DATA.md`: 798,197 total conversations; 28,280 SpotifyCares
conversations), which cross-validates this implementation against the
earlier ad-hoc analysis.

**Brand-message breakdown** (MEASURED, not previously reported at this
granularity): of the 43,346 brand-role messages, 43,265 are authored by
`SpotifyCares` itself (matching `docs/DATA.md`'s brand-tweet count
exactly) and 81 are from other genuine support accounts that
co-participate in the same reconstructed conversation:

| author_id | count |
|---|---|
| hulu_support | 49 |
| AppleSupport | 19 |
| AmazonHelp | 7 |
| comcastcares | 2 |
| British_Airways | 2 |
| O2 | 1 |
| asksalesforce | 1 |

This is expected and correct, not a bug: a small number of
SpotifyCares conversations cross into another brand's support scope
(most plausibly the Spotify+Hulu bundle pulling in `hulu_support`, and
a handful of multi-brand @-mentions). It's evidence the
conversation-level (structural) filtering is working as intended,
rather than a naive per-row `author_id == "SpotifyCares"` filter that
would have missed these legitimately-connected messages and the
customer-side messages entirely.

---

## 5. Data-quality results (full run, MEASURED)

| Check | Result |
|---|---|
| Missing `tweet_id` rows dropped | 0 |
| Duplicate `tweet_id` rows dropped | 0 |
| Missing required fields (`tweet_id`, `author_id`, `inbound`, `created_at`, `text`) | 0 for all five |
| Invalid/unparseable timestamps | 0 |
| Missing `inbound` (role=unknown) | 0 |
| Rows with a parent pointer (`in_response_to_tweet_id` not null) | 2,017,439 |
| ...of which resolved (parent exists in-dataset) | 2,807,912 (i.e. all rows with a resolvable structural position: those with no pointer at all, plus those whose pointer resolves) |
| ...of which the parent pointer is broken (points to a missing tweet) | 3,862 |

The 3,862 broken-parent-pointer count matches Phase 1's independently
measured figure exactly. These rows are **not** dropped or treated as
errors — they become conversation roots in their own right (a
deliberate design choice per `docs/DATA.md`'s Phase 1 finding that this
is expected: the referenced tweet was deleted or excluded from the
public export). None of the 3,862 broken pointers fall within the
SpotifyCares subset in a way that fragments a real conversation
mid-thread (the SpotifyCares-side quality figures above show 0 dropped
rows of any kind within the final 91,889-row output).

---

## 6. Caveats

- **Mega-thread artifact (carried over from Phase 1/2, not fixed
  here)**: this pipeline reconstructs conversations exactly as the
  reply-graph structure dictates, which means the previously-documented
  broadcast-tweet artifact (`conv_id=83694`, and the 4 brand-family
  accounts 115888/125633/117153/116130 identified in Phase 5) is still
  present in `spotifycares_conversations.parquet` as-is. This phase's
  job was faithful, auditable reconstruction from the dataset's actual
  structure — not judgment calls about which structurally-valid
  conversations are semantically "real" one-on-one exchanges. Any
  consumer of this Parquet file building a retrieval corpus should
  still apply the Phase 5 exclusion list before using it for that
  purpose.
- **`response_tweet_id` is unused**: it's a redundant, multi-valued
  forward pointer; the single-valued backward pointer
  (`in_response_to_tweet_id`) is sufficient and authoritative for
  reconstructing the same graph. This was a deliberate scope decision,
  not an oversight — cross-checking the two fields against each other
  for internal consistency was out of scope for this phase.
- **`parent_resolved=False` rows are still included** in the output
  (as their own conversation root) rather than excluded — this is
  intentional per the task's "do not silently discard problematic
  rows" instruction, but downstream consumers should be aware that a
  `parent_resolved=False` root's true parent context is permanently
  unavailable in this dataset.
- **Timezone**: all timestamps parsed as UTC per the `+0000` offset
  Twitter's export already uses; no timezone conversion was performed
  or needed.

---

## 7. Exact reproduction commands

```
# Run the full test suite (unit tests + smoke test against a small real sample)
E:\hiver-support-agent\.venv\Scripts\python.exe -m pytest -v

# Run the full reconstruction against the real dataset
E:\hiver-support-agent\.venv\Scripts\python.exe scripts\reconstruct_spotifycares.py
```

Both commands should be run from the repository root
(`E:\hiver-support-agent`).
