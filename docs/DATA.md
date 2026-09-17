# Dataset — Customer Support on Twitter

## Status

Phase 1 (dataset reconnaissance) complete. This document reports
dataset structure, quality, and content findings.

Labels used throughout:

- **MEASURED** — computed directly from the raw dataset.
- **OBSERVED** — qualitative pattern seen while sampling actual rows/conversations.
- **HYPOTHESIS** — plausible but not yet statistically validated.

Analysis was done with chunked/streaming pandas reads (already installed
globally) against `data/raw/twitter/twcs.csv` directly. The raw file was
never modified. No `.venv`, packages, or models were installed for this
phase. Full analysis scripts live in the scratchpad and are not part of
the repo; the numbers below are the recorded outputs.

---

## 1. File-Level Facts (MEASURED)

| Property | Value |
| --- | --- |
| File | `data/raw/twitter/twcs.csv` |
| File size | 516,508,641 bytes (~493 MB) |
| Total rows | 2,811,774 |
| Columns | `tweet_id, author_id, inbound, created_at, text, response_tweet_id, in_response_to_tweet_id` |
| Duplicate `tweet_id` values | 0 (all 2,811,774 tweet_ids are unique) |
| `tweet_id` type | integer, unique primary key |
| `author_id` type | string — numeric-looking pseudonymous IDs for customers, real brand handles (e.g. `AmazonHelp`) for support accounts |
| `inbound` type | boolean-as-string (`"True"` / `"False"`); `True` = customer → brand, `False` = brand → customer |
| `created_at` type | string, Twitter native format, e.g. `Tue Oct 31 22:10:47 +0000 2017` |
| `text` type | string, raw tweet text (may contain @mentions, URLs, emoji, non-English text) |
| `response_tweet_id` | string, comma-separated list of tweet_ids that reply to this tweet; null for 1,040,629 rows (37.0%) |
| `in_response_to_tweet_id` | string, single tweet_id this tweet replies to; null for 794,335 rows (28.2%) |

### Missing values (MEASURED)

| Column | Null count | Null % |
| --- | --- | --- |
| tweet_id | 0 | 0% |
| author_id | 0 | 0% |
| inbound | 0 | 0% |
| created_at | 0 | 0% |
| text | 0 | 0% |
| response_tweet_id | 1,040,629 | 37.0% |
| in_response_to_tweet_id | 794,335 | 28.2% |

Nulls in the two reply-linkage columns are expected: `response_tweet_id`
is null when nobody has (yet) replied to a tweet in the exported data;
`in_response_to_tweet_id` is null for the first message of a
conversation (usually the customer's opening complaint).

### Inbound / author split (MEASURED)

| Metric | Value |
|---|---|
| Customer→brand tweets (`inbound=True`) | 1,537,843 (54.7%) |
| Brand→customer tweets (`inbound=False`) | 1,273,931 (45.3%) |
| Unique authors total | 702,777 |
| Unique customer authors | 702,669 |
| Unique brand/support accounts | 108 |
| Average tweet text length | ~114 characters |

There are exactly 108 distinct brand/support handles in the dataset —
this is the full universe of brand-selection candidates.

---

## 2. Conversation / Thread Structure (MEASURED)

Twitter reply structure is a directed chain via
`in_response_to_tweet_id` (child → parent pointer). We reconstructed
conversations by treating each tweet as a node and grouping into
connected components via the reply-parent chain (root = earliest
ancestor with no resolvable parent).

| Metric | Value |
|---|---|
| Rows with an `in_response_to_tweet_id` pointer | 2,017,439 |
| ...of which the parent tweet exists in-dataset | 2,013,577 |
| ...of which the parent tweet is **missing** (broken chain) | 3,862 (0.19% of pointers) |
| Total reconstructed conversations | 798,197 |
| Conversation size — mean | 3.52 tweets |
| Conversation size — median | 2 tweets |
| Conversation size — max | 1,390 tweets (an outlier mega-thread) |
| Conversations of size 2 (single Q→A) | 435,398 (54.6%) |
| Conversations of size 3+ | 362,799 (45.4%) |
| Conversations of size 4+ (genuine back-and-forth) | 250,787 (31.4%) |

**OBSERVED**: no conversation has size 1 — this dataset appears to have
been pre-filtered by its creators to only include tweets that are part
of an actual reply exchange (no orphan/standalone tweets), which
matches the public description of this Kaggle dataset.

**Data-quality issue (MEASURED)**: 3,862 reply pointers reference a
`tweet_id` that does not exist anywhere in the CSV — these are cases
where the referenced tweet (customer or brand) was deleted or excluded
from the export. Any conversation reconstruction must treat an
unresolvable parent as a chain break rather than an error.

**HYPOTHESIS**: the size-1390 max outlier and other very large
components are likely not real single conversations but an artifact of
brand accounts replying to many different customers using the same
templated root tweet (e.g. a service-outage broadcast that many
customers replied to), which the naive reply-chain grouping would
merge into one giant "conversation." This should be guarded against
(e.g. cap conversation size when building the retrieval corpus, or
split components where a "root" has many independent customer
children with no further follow-up).

---

## 3. Brand Candidates (MEASURED)

Top 20 brand accounts by tweet volume, out of 108 total. Full
methodology and scoring in `research/brand_selection.md`.

| Brand | Total tweets | Conversations | 2-turn | 3-turn | 4+turn | Ends-with-brand-msg % (sampled) | DM-redirect % | Non-English % (est.) |
|---|---|---|---|---|---|---|---|---|
| AmazonHelp | 169,840 | 82,556 | 31,296 | 11,579 | 39,681 | 78.9% | 0.6% | 5.2% |
| AppleSupport | 106,860 | 80,717 | 52,573 | 8,036 | 20,108 | 89.9% | 52.5% | 1.0% |
| Uber_Support | 56,270 | 41,923 | 26,835 | 4,737 | 10,351 | 84.9% | 35.4% | 0.3% |
| SpotifyCares | 43,265 | 28,280 | 17,780 | 2,383 | 8,117 | 94.0% | 30.8% | 0.6% |
| Delta | 42,253 | 26,168 | 15,021 | 3,232 | 7,915 | 89.3% | 16.5% | 0.4% |
| AmericanAir | 36,764 | 26,386 | 14,809 | 3,374 | 8,203 | 80.3% | 16.8% | 0.3% |
| TMobileHelp | 34,317 | 22,820 | 14,193 | 2,229 | 6,398 | 88.7% | 81.8% | 0.4% |
| comcastcares | 33,031 | 24,063 | 15,269 | 3,584 | 5,210 | 90.3% | 71.5% | — |
| British_Airways | 29,361 | 16,452 | 7,622 | 2,899 | 5,931 | 84.2% | 14.0% | 0.2% |
| SouthwestAir | 28,977 | 21,636 | 14,405 | 2,665 | 4,566 | 84.5% | 16.9% | 0.7% |
| Ask_Spectrum | 25,860 | 18,532 | 11,971 | 1,999 | 4,562 | 87.3% | 49.5% | — |
| XboxSupport | 24,557 | 13,455 | 5,059 | 3,068 | 5,328 | 76.1% | 20.9% | — |
| sprintcare | 22,381 | 13,560 | 7,177 | 1,974 | 4,409 | 82.8% | 47.7% | — |
| AskPlayStation | 19,098 | 12,533 | 6,806 | 1,503 | 4,224 | 83.1% | 26.6% | 0.1% |

"Ends-with-brand-msg %" = fraction of sampled conversations (up to 5,000
per brand) whose chronologically last message is from the brand — a
rough proxy for "the thread reached some kind of closure" rather than
trailing off on an unanswered customer message.

"DM-redirect %" = fraction of the brand's own tweets containing
`dm` / `direct message` / `private message` — a proxy for how often the
*visible* resolution is actually "please DM us," which hides the real
resolution content from the public dataset.

"Non-English %" is a crude ASCII-based heuristic (fraction of customer
messages in that brand's conversations with <90% ASCII characters) —
it under-counts European-language text using mostly-Latin characters,
so treat it as a lower bound, not exact language ID.

Full brand analysis (all measured candidates, methodology, and
example conversations) is in `research/dataset_reconnaissance.md`.
Brand scoring and the final recommendation are in
`research/brand_selection.md`.

---

## 4. Conversation Reconstruction Method (for future implementation)

To reconstruct a customer-support conversation for the eventual
pipeline:

1. Treat each row as a node keyed by `tweet_id`.
2. Follow `in_response_to_tweet_id` backward to find the parent; if the
   parent tweet_id doesn't exist in the dataset, that node is a
   (possibly incomplete) conversation root.
3. Group nodes into connected components by their resolved root —
   this is a conversation.
4. Order messages within a conversation by `created_at` (parsed with
   Twitter's native format `%a %b %d %H:%M:%S %z %Y`).
5. Guard against the "mega-thread" artifact (Section 2): a component
   should probably be split if a single root has many customer
   children that never continue past 2 messages (broadcast-reply
   pattern) rather than one deep back-and-forth.
6. `inbound` distinguishes speaker role (customer vs. brand) directly —
   no need to infer it from `author_id` shape, though in practice
   customer `author_id`s are anonymized numeric strings and brand
   `author_id`s are the 108 known handles.

This is a plan for the eventual data-processing step, not yet
implemented — no processed/retrieval data has been created in this
phase.

---

## 5. Known Data-Quality Issues Going Forward (OBSERVED / HYPOTHESIS)

- **DM redirects hide real resolutions.** For several brands (notably
  TMobileHelp 81.8%, comcastcares 71.5%, AppleSupport 52.5%), a large
  fraction of brand replies simply ask the customer to move to DM for
  account-specific help. Those conversations look like a "resolution"
  in the reply-chain sense but contain no actual resolution text in the
  public dataset — a RAG/retrieval corpus built from these would be
  full of near-empty "evidence." (MEASURED redirect %, HYPOTHESIS that
  it correlates with retrieval-corpus quality — validated qualitatively
  by sampling in `research/dataset_reconnaissance.md`.)
- **Multilingual content** exists, especially for globally-operated
  brands like AmazonHelp (French, Spanish, Japanese observed directly
  in sampled conversations). An English-only pipeline will need a
  language filter or explicit scoping decision. (OBSERVED directly in
  samples; MEASURED as a lower-bound percentage via ASCII heuristic.)
- **Broken reply chains**: 3,862 reply pointers reference tweets absent
  from the export (deleted/excluded). Conversation reconstruction must
  tolerate this rather than assuming every pointer resolves.
- **Templated/boilerplate brand replies**: many brand responses are
  short, formulaic ("We'd like to look into this, please DM your
  confirmation number") rather than containing a concrete resolution —
  this affects how much genuine "historical resolution evidence" exists
  per intent, independent of raw tweet/conversation counts. (OBSERVED)
- **Signature codes**: many brand replies end with an agent signature
  token (e.g. `*HVI`, `/TB`, `^SB`) — cosmetic, but worth stripping
  during text normalization.
- **Mega-thread outliers**: components as large as 1,390 tweets exist
  and are very likely a broadcast/many-replies artifact, not a single
  real conversation (see Section 2 hypothesis).
