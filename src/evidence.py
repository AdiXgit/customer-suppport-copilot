"""
Phase 9, Step 3: historical-evidence sufficiency assessment.

This sits between retrieval (Phase 8) and generation/escalation
(Phase 9). It does NOT call an LLM and does NOT use golden labels --
it is a small set of deterministic, documented heuristics over the
retrieved cases and the raw customer message.

IMPORTANT, non-obvious finding this module is built around: Phase 8's
own manual retrieval audit (data/retrieval/spotifycares_retrieval_evaluation.json)
found that top-1 similarity score does NOT reliably separate good
matches from poor ones on this corpus -- the audited "poor" matches
actually had a HIGHER average top-1 similarity (0.91) than the
audited "good" matches (0.84), because very short/generic customer
messages (bare version strings, "please fix?") score spuriously high
against other short generic messages. Because of this, similarity
alone is used only as a low floor (catches genuinely dissimilar
retrieval), not as the primary sufficiency signal. The primary
signals are structural: how many of the retrieved responses are
themselves weak evidence (acknowledgements / DM redirects with no
visible resolution), how scattered the retrieved intents are, and
whether the customer's own message carries enough information to be
answered in isolation at all.

All thresholds are named constants, configurable, and documented here
rather than tuned against any labeled set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MIN_SIMILARITY_FLOOR = 0.45  # below this, treat retrieval as noise regardless of anything else
WEAK_RESPONSE_TYPES = {"acknowledgement", "dm_redirect"}
WEAK_RESPONSE_FRACTION_THRESHOLD = 0.6  # >=60% of top-k are weak-evidence response types
MIN_DISTINCT_INTENTS_FOR_CONFLICT = 3    # top-k spanning this many different intents looks scattered
LOW_INFO_WORD_COUNT = 3                  # customer message word count (mentions stripped) at or below this is "bare"

REASON_NO_RESULTS = "NO_RESULTS"
REASON_LOW_SIMILARITY = "LOW_SIMILARITY"
REASON_CONFLICTING_INTENTS = "CONFLICTING_INTENTS"
REASON_WEAK_RESPONSE_TYPES = "WEAK_RESPONSE_TYPES"
REASON_LOW_INFORMATION_QUERY = "LOW_INFORMATION_QUERY"


@dataclass
class EvidenceAssessment:
    sufficient: bool
    reasons: list[str] = field(default_factory=list)
    top_similarity: float | None = None
    distinct_intents: int = 0
    weak_response_fraction: float = 0.0


def _word_count(text: str) -> int:
    stripped = re.sub(r"@\w+", "", text or "").strip()
    return len(stripped.split())


def assess_evidence(customer_message: str, retrieved_cases: list[dict]) -> EvidenceAssessment:
    """retrieved_cases: list of dicts as returned by src/agent.py's
    retrieval step, each with at least 'similarity', 'intent', and
    'response_type' keys."""
    reasons: list[str] = []

    if not retrieved_cases:
        return EvidenceAssessment(sufficient=False, reasons=[REASON_NO_RESULTS])

    top_similarity = retrieved_cases[0]["similarity"]
    if top_similarity < MIN_SIMILARITY_FLOOR:
        reasons.append(REASON_LOW_SIMILARITY)

    distinct_intents = len({c["intent"] for c in retrieved_cases})
    if distinct_intents >= MIN_DISTINCT_INTENTS_FOR_CONFLICT:
        reasons.append(REASON_CONFLICTING_INTENTS)

    weak_count = sum(1 for c in retrieved_cases if c.get("response_type") in WEAK_RESPONSE_TYPES)
    weak_fraction = weak_count / len(retrieved_cases)
    if weak_fraction >= WEAK_RESPONSE_FRACTION_THRESHOLD:
        reasons.append(REASON_WEAK_RESPONSE_TYPES)

    if _word_count(customer_message) <= LOW_INFO_WORD_COUNT:
        reasons.append(REASON_LOW_INFORMATION_QUERY)

    return EvidenceAssessment(
        sufficient=len(reasons) == 0,
        reasons=reasons,
        top_similarity=top_similarity,
        distinct_intents=distinct_intents,
        weak_response_fraction=weak_fraction,
    )
