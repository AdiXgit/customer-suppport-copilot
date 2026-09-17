"""
Phase 7B: historical resolution-pair extraction from the Phase 7A
reconstructed SpotifyCares conversations.

Builds "resolution candidates" -- a customer message paired with the
SpotifyCares (or co-participating support account) reply that was
actually posted in response to it, using ONLY the dataset's own
structural parent/child relationship (`parent_tweet_id`), never text
similarity, chronological adjacency guessing, or an LLM.

Terminology: this module produces "resolution candidates", never
"resolutions". A resolution candidate is a real historical
customer-message -> brand-response pair; it is NOT a claim that the
customer's problem was actually solved. See docs/PHASE_7B_RESOLUTION_CORPUS.md.

Reads (read-only): data/processed/twitter/spotifycares_conversations.parquet
Never modifies: data/raw/twitter/twcs.csv,
                 data/processed/twitter/spotifycares_conversations.parquet,
                 anything under data/golden/.

No LLM, no embeddings, no semantic similarity is used anywhere in this
module.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import polars as pl

# ---------------------------------------------------------------------
# Known exclusions (carried forward from Phase 5 findings, applied here
# at the resolution-corpus stage per this phase's instructions -- the
# Phase 7A reconstruction itself is left unchanged).
# ---------------------------------------------------------------------

BRAND_FAMILY_ACCOUNTS = {"115888", "125633", "117153", "116130"}
MEGA_THREAD_CONVERSATION_IDS = {83694}

_DM_REDIRECT_RE = re.compile(r"\bdm\b|direct message|private message", re.IGNORECASE)

_DM_FOLLOWUP_RE = re.compile(
    r"^(please\s+)?(check|read|see|reply to|respond to)?\s*(your |ur |my )?dm'?s?\b.*$"
    r"|^dm'?d?\b.*$|^urgent\b.*dm.*$",
    re.IGNORECASE,
)

_MENTION_OR_URL_RE = re.compile(r"https?://\S+|@\w+")


def _strip_mentions_urls(text: str) -> str:
    return re.sub(r"\s+", " ", _MENTION_OR_URL_RE.sub(" ", text or "")).strip()


def is_unusable_fragment(text: str) -> bool:
    """A message with no real content once @mentions/URLs are stripped
    (a bare link, a single mention, an empty reaction) -- reused from
    the Phase 5 golden-set sampling definition."""
    return len(_strip_mentions_urls(text)) < 3


def is_bare_dm_followup(text: str) -> bool:
    """A short message that is only 'check your DM' / 'DM sent' /
    'urgent DM' with no visible original issue -- reused from the
    Phase 5 golden-set sampling definition."""
    stripped = _strip_mentions_urls(text)
    words = stripped.split()
    if not words:
        return False
    return bool(_DM_FOLLOWUP_RE.match(stripped)) and len(words) <= 8


# ---------------------------------------------------------------------
# Response-type classification (deterministic, structural only)
# ---------------------------------------------------------------------

RESPONSE_TYPES = ["dm_redirect", "acknowledgement", "clarification_question", "substantive_response"]


def classify_response_type(text: str) -> str:
    """Conservative, purely structural classification of a brand
    response. Deliberately does NOT attempt to distinguish "generic/
    template" from "substantive" wording, since that distinction
    requires semantic judgment this module does not perform (see
    docs/PHASE_7B_RESOLUTION_CORPUS.md, "Known limitations").

    Priority order (first match wins):
      1. dm_redirect       -- mentions DM/direct message/private message
      2. acknowledgement   -- very short (<=8 words), no '?', no DM language
      3. clarification_question -- contains '?'
      4. substantive_response   -- everything else (a structural
                                    proxy: longer, non-question, non-DM
                                    text -- NOT a claim that it resolved
                                    anything)
    """
    text = text or ""
    if _DM_REDIRECT_RE.search(text):
        return "dm_redirect"
    words = text.split()
    if len(words) <= 8 and "?" not in text:
        return "acknowledgement"
    if "?" in text:
        return "clarification_question"
    return "substantive_response"


# ---------------------------------------------------------------------
# Exclusion report
# ---------------------------------------------------------------------

@dataclass
class ExclusionEntry:
    exclusion_reason: str
    conversation_id: int | None
    author_id: str | None
    affected_message_count: int
    affected_candidate_count: int
    affected_tweet_ids: list = field(default_factory=list)


@dataclass
class ExclusionReport:
    entries: list = field(default_factory=list)

    def total_excluded_conversations(self) -> int:
        conv_ids = {e.conversation_id for e in self.entries if e.conversation_id is not None}
        return len(conv_ids)

    def total_excluded_messages(self) -> int:
        return sum(e.affected_message_count for e in self.entries)

    def total_excluded_candidates(self) -> int:
        return sum(e.affected_candidate_count for e in self.entries)

    def to_dict(self) -> dict:
        return {"entries": [asdict(e) for e in self.entries]}

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------
# Quality report
# ---------------------------------------------------------------------

@dataclass
class ResolutionQualityReport:
    source_row_count: int = 0
    conversations_inspected: int = 0
    candidate_resolution_count: int = 0
    substantive_response_count: int = 0
    dm_redirect_count: int = 0
    clarification_question_count: int = 0
    acknowledgement_count: int = 0
    generic_template_count: int | None = None  # not implemented, see notes
    conversations_with_no_brand_response: int = 0
    excluded_conversations: int = 0
    excluded_messages: int = 0
    excluded_candidate_pairs: int = 0
    mega_thread_conversation_ids: list = field(default_factory=list)
    mega_thread_message_count: int = 0
    mega_thread_would_be_candidate_count: int = 0
    duplicate_resolution_ids_found: int = 0
    missing_required_field_counts: dict = field(default_factory=dict)
    multi_turn_candidate_count: int = 0
    max_context_messages: int = 0
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")


CANDIDATE_COLUMNS = [
    "resolution_id",
    "conversation_id",
    "customer_tweet_id",
    "customer_author_id",
    "customer_message",
    "customer_timestamp",
    "brand_tweet_id",
    "brand_author_id",
    "brand_response",
    "brand_timestamp",
    "parent_tweet_id",
    "response_type",
    "number_of_context_messages",
    "context_messages_json",
    "intent",
    "customer_source_row_id",
    "brand_source_row_id",
]


def apply_exclusions(df: pl.DataFrame) -> tuple[pl.DataFrame, ExclusionReport]:
    """Flags (does not delete) rows/conversations per the known Phase 5
    exclusion rules, returning a working copy annotated with an
    `excluded_as_trigger` boolean (used only to decide which candidates
    NOT to emit) plus a full, auditable ExclusionReport. The Phase 7A
    input `df` itself is never mutated in place (polars is immutable-
    by-default; this returns a new frame)."""
    report = ExclusionReport()

    # --- Mega-thread: exclude the whole conversation from candidate
    # generation, per instructions -- it is not one coherent
    # customer-resolution conversation.
    mega = df.filter(pl.col("conversation_id").is_in(list(MEGA_THREAD_CONVERSATION_IDS)))
    for conv_id in MEGA_THREAD_CONVERSATION_IDS:
        conv_rows = mega.filter(pl.col("conversation_id") == conv_id)
        if conv_rows.height == 0:
            continue
        # would-be candidates: brand rows in this conversation with a
        # resolved parent -- i.e. what we are declining to generate.
        would_be = conv_rows.filter(
            (pl.col("role") == "brand") & pl.col("parent_tweet_id").is_not_null()
        ).height
        report.entries.append(ExclusionEntry(
            exclusion_reason="mega_thread",
            conversation_id=int(conv_id),
            author_id=None,
            affected_message_count=int(conv_rows.height),
            affected_candidate_count=int(would_be),
            affected_tweet_ids=sorted(conv_rows.get_column("tweet_id").to_list()),
        ))

    working = df.filter(~pl.col("conversation_id").is_in(list(MEGA_THREAD_CONVERSATION_IDS)))

    # --- Brand-family accounts: exclude any candidate whose customer
    # trigger is authored by one of these (they are not real customers
    # -- see docs/GOLDEN_SET.md / docs/GOLDEN_SET_ANNOTATION_REVIEW.md).
    excluded_trigger_ids: set[int] = set()
    for account in sorted(BRAND_FAMILY_ACCOUNTS):
        acct_rows = working.filter(pl.col("author_id") == account)
        if acct_rows.height == 0:
            report.entries.append(ExclusionEntry(
                exclusion_reason="brand_family_account",
                conversation_id=None,
                author_id=account,
                affected_message_count=0,
                affected_candidate_count=0,
            ))
            continue
        acct_tweet_ids = acct_rows.get_column("tweet_id").to_list()
        excluded_trigger_ids.update(acct_tweet_ids)
        # candidates that would have used one of these as the customer
        # trigger: brand rows whose parent_tweet_id is one of these ids.
        would_be = working.filter(
            (pl.col("role") == "brand") & pl.col("parent_tweet_id").is_in(acct_tweet_ids)
        ).height
        report.entries.append(ExclusionEntry(
            exclusion_reason="brand_family_account",
            conversation_id=None,
            author_id=account,
            affected_message_count=int(acct_rows.height),
            affected_candidate_count=int(would_be),
            affected_tweet_ids=sorted(acct_tweet_ids)[:50],
        ))

    # --- Fragments and bare DM-follow-ups: exclude as customer triggers
    # only (not deleted from the working frame -- they may still be
    # legitimate context for other candidates deeper in the same
    # conversation).
    customer_rows = working.filter(pl.col("role") == "customer")
    texts = customer_rows.get_column("text").to_list()
    tweet_ids = customer_rows.get_column("tweet_id").to_list()

    fragment_ids = [tid for tid, t in zip(tweet_ids, texts) if is_unusable_fragment(t)]
    dm_followup_ids = [
        tid for tid, t in zip(tweet_ids, texts)
        if tid not in fragment_ids and is_bare_dm_followup(t)
    ]

    for reason, ids in (("fragment", fragment_ids), ("dm_followup_no_issue", dm_followup_ids)):
        if not ids:
            report.entries.append(ExclusionEntry(
                exclusion_reason=reason, conversation_id=None, author_id=None,
                affected_message_count=0, affected_candidate_count=0,
            ))
            continue
        would_be = working.filter(
            (pl.col("role") == "brand") & pl.col("parent_tweet_id").is_in(ids)
        ).height
        report.entries.append(ExclusionEntry(
            exclusion_reason=reason,
            conversation_id=None,
            author_id=None,
            affected_message_count=len(ids),
            affected_candidate_count=int(would_be),
            affected_tweet_ids=sorted(ids)[:50],
        ))
        excluded_trigger_ids.update(ids)

    working = working.with_columns(
        pl.col("tweet_id").is_in(list(excluded_trigger_ids)).alias("excluded_as_trigger")
    )

    return working, report


def _build_parent_index(df: pl.DataFrame) -> dict[int, dict]:
    return {row["tweet_id"]: row for row in df.iter_rows(named=True)}


def _build_context_chain(index: dict[int, dict], start_parent_id) -> list[dict]:
    """Walk parent_tweet_id pointers upward from a customer trigger
    message's own parent, collecting ancestors in root-first order.
    Bounded implicitly by real conversation depth (small in this
    dataset); a hard cap prevents runaway traversal on unexpected data."""
    chain: list[dict] = []
    current_id = start_parent_id
    seen: set[int] = set()
    max_hops = 200
    hops = 0
    while current_id is not None and hops < max_hops:
        row = index.get(current_id)
        if row is None or current_id in seen:
            break
        seen.add(current_id)
        chain.append(row)
        current_id = row["parent_tweet_id"]
        hops += 1
    chain.reverse()
    return [
        {
            "tweet_id": r["tweet_id"],
            "role": r["role"],
            "author_id": r["author_id"],
            "text": r["text"],
            "timestamp": str(r["timestamp"]) if r["timestamp"] is not None else None,
        }
        for r in chain
    ]


def deduplicate_candidates(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Defensive dedup on resolution_id (should never trigger on real
    data, since brand_tweet_id is unique post-Phase-7A, but is exercised
    directly by a unit test and applied here for auditability)."""
    n_before = df.height
    out = df.unique(subset=["resolution_id"], keep="first", maintain_order=True)
    return out, n_before - out.height


def extract_resolution_candidates(df: pl.DataFrame) -> tuple[pl.DataFrame, ResolutionQualityReport, ExclusionReport]:
    """Top-level orchestration: apply exclusions, then pair every
    customer message with each brand reply whose parent_tweet_id points
    directly at it (the dataset's own structural relationship), attach
    ancestor context, classify response type, and assemble the
    candidate table + quality report."""
    report = ResolutionQualityReport()
    report.source_row_count = df.height
    report.conversations_inspected = int(df.get_column("conversation_id").n_unique())

    required = ["conversation_id", "tweet_id", "author_id", "role", "timestamp", "text", "parent_tweet_id"]
    missing_counts = df.select(required).null_count().to_dicts()[0]
    report.missing_required_field_counts = {k: int(v) for k, v in missing_counts.items() if k != "parent_tweet_id"}

    working, exclusion_report = apply_exclusions(df)

    report.mega_thread_conversation_ids = sorted(MEGA_THREAD_CONVERSATION_IDS)
    mega_entries = [e for e in exclusion_report.entries if e.exclusion_reason == "mega_thread"]
    report.mega_thread_message_count = sum(e.affected_message_count for e in mega_entries)
    report.mega_thread_would_be_candidate_count = sum(e.affected_candidate_count for e in mega_entries)

    index = _build_parent_index(working)

    brand_rows = working.filter(
        (pl.col("role") == "brand") & pl.col("parent_tweet_id").is_not_null()
    )

    candidates = []
    for row in brand_rows.iter_rows(named=True):
        parent_id = row["parent_tweet_id"]
        customer_row = index.get(parent_id)
        if customer_row is None:
            continue  # broken parent chain -- no customer trigger exists to pair with
        if customer_row["role"] != "customer":
            continue  # only pair actual customer -> brand edges
        if customer_row.get("excluded_as_trigger"):
            continue  # fragment / dm-followup / brand-family trigger -- skip this candidate

        context = _build_context_chain(index, customer_row["parent_tweet_id"])
        response_type = classify_response_type(row["text"])

        candidates.append({
            "resolution_id": f"RES-{customer_row['conversation_id']}-{row['tweet_id']}",
            "conversation_id": customer_row["conversation_id"],
            "customer_tweet_id": customer_row["tweet_id"],
            "customer_author_id": customer_row["author_id"],
            "customer_message": customer_row["text"],
            "customer_timestamp": customer_row["timestamp"],
            "brand_tweet_id": row["tweet_id"],
            "brand_author_id": row["author_id"],
            "brand_response": row["text"],
            "brand_timestamp": row["timestamp"],
            "parent_tweet_id": row["parent_tweet_id"],
            "response_type": response_type,
            "number_of_context_messages": len(context),
            "context_messages_json": json.dumps(context, ensure_ascii=False),
            "intent": None,  # see docs/PHASE_7B_RESOLUTION_CORPUS.md: not populated, by design
            "customer_source_row_id": customer_row.get("source_row_id"),
            "brand_source_row_id": row.get("source_row_id"),
        })

    if candidates:
        candidates_df = pl.DataFrame(candidates)
    else:
        candidates_df = pl.DataFrame({c: [] for c in CANDIDATE_COLUMNS})

    candidates_df, n_dup = deduplicate_candidates(candidates_df)
    report.duplicate_resolution_ids_found = n_dup

    candidates_df = candidates_df.select(CANDIDATE_COLUMNS).sort(
        ["conversation_id", "brand_timestamp", "brand_tweet_id"], nulls_last=True
    )

    report.candidate_resolution_count = candidates_df.height
    if candidates_df.height:
        type_counts = (
            candidates_df.get_column("response_type").value_counts().to_dicts()
        )
        counts_by_type = {d["response_type"]: d["count"] for d in type_counts}
    else:
        counts_by_type = {}
    report.dm_redirect_count = counts_by_type.get("dm_redirect", 0)
    report.acknowledgement_count = counts_by_type.get("acknowledgement", 0)
    report.clarification_question_count = counts_by_type.get("clarification_question", 0)
    report.substantive_response_count = counts_by_type.get("substantive_response", 0)

    report.multi_turn_candidate_count = int(
        candidates_df.filter(pl.col("number_of_context_messages") > 0).height
    ) if candidates_df.height else 0
    report.max_context_messages = int(
        candidates_df.get_column("number_of_context_messages").max() or 0
    ) if candidates_df.height else 0

    # Conversations with no brand response at all (customer-only threads
    # after exclusions were applied) -- computed on the working set.
    conv_ids_all = set(working.get_column("conversation_id").unique().to_list())
    conv_ids_with_brand_reply = set(
        working.filter(pl.col("role") == "brand").get_column("conversation_id").unique().to_list()
    )
    report.conversations_with_no_brand_response = len(conv_ids_all - conv_ids_with_brand_reply)

    report.excluded_conversations = exclusion_report.total_excluded_conversations()
    report.excluded_messages = exclusion_report.total_excluded_messages()
    report.excluded_candidate_pairs = exclusion_report.total_excluded_candidates()

    report.notes.append(
        "generic_template_count is null: distinguishing 'generic/template' "
        "wording from 'substantive but formulaic' wording was judged to "
        "require semantic interpretation beyond reliable deterministic "
        "detection, per this phase's instruction to stay conservative. "
        "dm_redirect and acknowledgement capture the most confidently "
        "non-substantive response shapes instead."
    )
    report.notes.append(
        "intent is null for every candidate by design: no deterministic "
        "intent source exists for the general corpus, and joining the "
        "200-example golden-set labels (which would be deterministic for "
        "that small overlap) was deliberately rejected to keep the "
        "golden set fully firewalled from any corpus destined for the "
        "retrieval system -- see docs/PHASE_7B_RESOLUTION_CORPUS.md."
    )

    return candidates_df, report, exclusion_report


def run_full_extraction(
    input_path: str | Path,
    output_path: str | Path,
    quality_report_path: str | Path,
    exclusion_report_path: str | Path,
) -> tuple[ResolutionQualityReport, ExclusionReport]:
    """Production entry point: read the Phase 7A Parquet (read-only),
    extract resolution candidates, write the candidate Parquet, the
    quality report JSON, and the exclusion report JSON. Never modifies
    the Phase 7A input."""
    df = pl.read_parquet(input_path)
    candidates_df, quality_report, exclusion_report = extract_resolution_candidates(df)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidates_df.write_parquet(output_path)

    quality_report.to_json(quality_report_path)
    exclusion_report.to_json(exclusion_report_path)

    return quality_report, exclusion_report
