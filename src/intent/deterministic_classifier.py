"""
Phase 7D: deterministic, rule-based intent classifier for the Phase 7C
historical resolution corpus.

Applies the finalized 9-intent taxonomy (docs/INTENTS.md,
docs/TAXONOMY_CONTRACT_FINAL.md) using only regex/keyword pattern
matching on the customer's own message text -- no LLM, no embeddings,
no semantic similarity, and (per this phase's explicit instruction)
NOT fit or tuned against the golden set in any way.

Design principle: precision over coverage. Every match is traceable to
a named reason code. Anything not confidently matched becomes
OTHER / UNKNOWN rather than a guess.

Rule priority order (a message is checked against rules in this order;
the first-priority match becomes primary_intent, a second match becomes
secondary_issue with ambiguous=True):

  1. Exclusion-shaped text (praise-only / off-topic) -> OTHER/UNKNOWN
  2. Account Security          (explicit compromise language)
  3. Country/Market Availability (whole-service availability)
  4. Content Availability & Catalog Accuracy (specific content missing/wrong)
  5. Premium Subscription & Billing (incl. the documented billing-signup
     exception where a technical error occurs during a plan/signup flow)
  6. App & Playback Technical Issues (incl. the finalized Access-vs-
     Technical tie-break criteria)
  7. Account Access & Login    (login-shaped, no malfunction evidence)
  8. Feature Request & Product Feedback
  9. General Complaint / Service Dissatisfaction
 10. OTHER / UNKNOWN (nothing matched)

This ordering is a deliberate, documented design choice (see
docs/TODO.md's Phase 7D entry), not a re-derivation of Phase 2's root-
message regexes verbatim -- several patterns are narrowed here
specifically to keep precision high on a corpus that includes
mid-conversation trigger messages, not just first-contact complaints.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict


def _normalize(text: str) -> str:
    """Normalize curly/smart quotes to straight ASCII quotes before any
    regex matching. Real tweets very commonly contain typographic
    apostrophes (') and quotes from mobile keyboards, which a literal
    `'?` in a regex does NOT treat as equivalent to a straight `'` --
    without this, patterns like `isn't`, `won't`, `where's` silently
    fail to match a large share of real messages. This is a precision-
    neutral normalization (it only affects punctuation shape, not
    semantics), applied uniformly before every rule in this module."""
    if not text:
        return text
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return text

# ---------------------------------------------------------------------
# Canonical intent strings (must match docs/TAXONOMY_CONTRACT_FINAL.md exactly)
# ---------------------------------------------------------------------

ACCOUNT_ACCESS = "Account Access & Login"
ACCOUNT_SECURITY = "Account Security"
BILLING = "Premium Subscription & Billing"
TECHNICAL = "App & Playback Technical Issues"
CONTENT = "Content Availability & Catalog Accuracy"
FEATURE = "Feature Request & Product Feedback"
COMPLAINT = "General Complaint / Service Dissatisfaction"
MARKET = "Country/Market Availability Inquiry"
OTHER = "OTHER / UNKNOWN"

CANONICAL_INTENTS = {
    ACCOUNT_ACCESS, ACCOUNT_SECURITY, BILLING, TECHNICAL,
    CONTENT, FEATURE, COMPLAINT, MARKET, OTHER,
}

PRIORITY_ORDER = [ACCOUNT_SECURITY, MARKET, CONTENT, BILLING, TECHNICAL, ACCOUNT_ACCESS, FEATURE, COMPLAINT]

# ---------------------------------------------------------------------
# Exclusion-shaped text (not a labelable request at all -> OTHER/UNKNOWN
# with a specific reason code, per docs/TAXONOMY_CONTRACT_FINAL.md's
# "OTHER/UNKNOWN rule" -- this module has no separate `excluded` field,
# so these are folded into OTHER/UNKNOWN with a distinguishing reason).
# ---------------------------------------------------------------------

_PRAISE_ONLY_RE = re.compile(
    r"^(@\w+\s*)*(thanks|thank you|thankyou|thx|ty|awesome|love (you|this|it)|"
    r"great job|nice one|you(’|')?re the best|kudos)\b[!. ]*$",
    re.IGNORECASE,
)

_OFF_TOPIC_RE = re.compile(
    r"\b(hire me|job opening|graphic designer|looking for work|"
    r"partnership|sponsorship|collaborat(e|ion)|business inquiry)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# 2. Account Security -- explicit third-party compromise language.
# High precision: requires an explicit compromise verb/noun, not just
# "security" as a topic word (see docs/TAXONOMY_CONFLICT_REVIEW.md's
# GOLD-0183 finding: a bare "account security" mention with no detail
# is NOT enough evidence -- this classifier requires more).
# ---------------------------------------------------------------------

_SECURITY_RE = re.compile(
    r"\b(hack(ed|ing)?|compromised|someone (else )?(is using|used|logged into|"
    r"got into|accessed|hijacked|took over)\s*(my)?\s*(account)?|stolen (account|acct)|"
    r"unauthori[sz]ed (access|payment|charge|use)|"
    r"changed (my )?(email|password) (without|w/o) (my )?(permission|consent|verification)|"
    r"account (was |got )?(taken over|hijacked))\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# 3. Country/Market Availability -- whole-SERVICE availability, not
# specific content. Requires the availability language to attach to
# the service itself (spotify / it / the app / you guys), not a named
# song/artist/album.
# ---------------------------------------------------------------------

_MARKET_RE = re.compile(
    r"\b(spotify|it|this app|the app|the service|you guys|y'?all)\b"
    r"[^.?!\n]{0,40}\b(available|launch(ed|ing)?|come|coming)\b"
    r"[^.?!\n]{0,30}\b(in|to)\b[^.?!\n]{0,25}\b[A-Z][a-zA-Z]+\b"
    r"|\b(when will|why (isn'?t|is)n?'?t?)\b[^.?!\n]{0,15}\bspotify\b[^.?!\n]{0,30}\b(available|launch|come)\b"
    r"|\blaunch\b[^.?!\n]{0,15}\bin\b[^.?!\n]{0,20}\balready\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# 4. Content Availability & Catalog Accuracy -- specific song/album/
# artist/podcast missing, removed, region-locked, or mistagged.
# ---------------------------------------------------------------------

_CONTENT_RE = re.compile(
    r"\b(why (isn'?t|is)n?'?t?|where'?s|where is)\b[^.?!\n]{0,60}\b(album|song|track|artist|podcast|ep\b)\b"
    r"|\b(album|song|track|ep)\b[^.?!\n]{0,40}\bnot (on|available (on|in) spotify)\b"
    r"|\bnot (on|available on) spotify\b"
    r"|\b(add|bring back|release|post)\b[^.?!\n]{0,40}\b(album|song|track|ep|discography|single)\b"
    r"|\b(removed|pulled|taken down)\b[^.?!\n]{0,30}\bfrom spotify\b"
    r"|\bwrong (artist|album|name)\b|\bmerge\b[^.?!\n]{0,20}\b(artist|profile|account)s?\b"
    r"|\bmislabel|\bcategori[sz]ed under\b|\bduplicate (track|song|album)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# 5. Premium Subscription & Billing.
# ---------------------------------------------------------------------

_BILLING_ACTION_RE = re.compile(
    r"\b(charg(e|ed|ing)|billing|bill(ed)?|payment|paypal|credit card|debit card|"
    r"refund|invoice|subscri(be|bed|bing|ption)|renew(al|ed|ing)?|cancel(l)?(ed|ing)?|"
    r"discount|promo(tion)?|coupon|gift card|pay(ing|ment)?|"
    r"family (plan|premium|sharing)|student (discount|account|plan|price)|"
    r"upgrade (to|my) premium)\b",
    re.IGNORECASE,
)

_SIGNUP_CONTEXT_RE = re.compile(r"\b(sign ?up|signing up|re-?do (sign ?up|registration)|activate)\b", re.IGNORECASE)
_BILLING_PLAN_CONTEXT_RE = re.compile(r"\b(premium|student|hulu|trial|discount|subscription)\b", re.IGNORECASE)

# ---------------------------------------------------------------------
# 6. App & Playback Technical Issues, including the finalized Access-
# vs-Technical tie-break criteria (docs/INTENTS.md).
# ---------------------------------------------------------------------

_TECH_MALFUNCTION_RE = re.compile(
    r"\b(crash(ed|ing|es)?|freez(e|es|ing)|buffer(ing)?|keeps? (skipping|pausing|stopping|"
    r"disconnecting|cutting out|freezing)|won'?t (play|load|open|work|respond|let me)|"
    r"not (working|playing|responding|loading|connecting|syncing)|error message|bug\b|"
    r"stopped (working|connecting|syncing)|disappeared|vanish(ed)?|"
    r"deleted (all|my) (songs|downloads|playlists|music)|"
    r"not (optimized|supported) for|no support for|blank screen|nothing (happens|responds))\b",
    re.IGNORECASE,
)

_LOGIN_TOPIC_RE = re.compile(
    r"\b(log ?in|login|sign ?in|log(ging|ged)? ?(in|out)|"
    r"can'?t (get|access) (my|into) account|"
    r"password|username|credentials|reset my password|verify my account)\b",
    re.IGNORECASE,
)

# Tie-break criteria 1-3 (docs/INTENTS.md "Tie-Break" section)
_TECH_ID_RE = re.compile(
    r"\berror\s*\d{3}\b|\bcsr?f token\b|\bexception\b|\bstatus\s*code\b|"
    r"\b(4|5)\d{2}\s*(error)?\b",
    re.IGNORECASE,
)
_BROKEN_UI_RE = re.compile(
    r"\b(button(s)?|form|page)\b[^.?!\n]{0,20}\b(doesn'?t|don'?t|not) work\b"
    r"|\b(app|site|website)\b[^.?!\n]{0,20}\bcrash(es|ed)?\b",
    re.IGNORECASE,
)
_TROUBLESHOOTING_RE = re.compile(
    r"\b(reinstall(ed|ing)?|re-?install(ed|ing)?|clear(ed)? (my )?cache|"
    r"restart(ed|ing)? (my|the)? ?(device|phone|app|computer|router)|"
    r"uninstall(ed|ing)?|tried (a )?different browser|logged out.{0,20}logged? back)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# 8. Feature Request & Product Feedback.
# ---------------------------------------------------------------------

_FEATURE_RE = re.compile(
    r"\b((please|pls) (add|make|bring back|implement)|can you (add|make|implement)|"
    r"would (be|love) (great|awesome|nice|amazing) if|wish (you|spotify) (had|would|could)|"
    r"it would be (nice|great|awesome) if|"
    r"any (chance|plans) (of|for)\b|feature request|(should|could) (add|implement|build)\b|"
    r"why (isn'?t there|is there no)\b[^.?!\n]{0,40}\b(feature|option|way to)\b)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# 9. General Complaint / Service Dissatisfaction.
# ---------------------------------------------------------------------

_COMPLAINT_RE = re.compile(
    r"\b(worst (customer service|support|app|service|company)|"
    r"terrible (customer service|support|service)|"
    r"horrible (service|support|experience)|"
    r"poor customer service|useless (support|app|service)|"
    r"no response|nobody (replies|responds)|ignored my (dm|email)|"
    r"switch(ing)? to (apple music|tidal|youtube music|deezer)|"
    r"lost a customer|customer service is (bad|terrible|poor|awful)|"
    r"awful (service|support|experience))\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# Non-English heuristic (reused from Phase 1/5: ASCII-ratio lower bound)
# ---------------------------------------------------------------------

def is_likely_non_english(text: str) -> bool:
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return (ascii_chars / len(text)) < 0.9


@dataclass
class ClassificationResult:
    primary_intent: str
    secondary_issue: str | None
    labeling_method: str
    labeling_reason: str
    labeling_confidence: str
    ambiguous: bool
    non_english: bool
    matched_intents: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _match_intents(text: str) -> list[tuple[str, str, str]]:
    """Returns [(intent, reason_code, confidence), ...] for every rule
    that matched, in PRIORITY_ORDER. Does not decide primary/secondary."""
    if not text:
        return []

    matches: list[tuple[str, str, str]] = []

    if _SECURITY_RE.search(text):
        matches.append((ACCOUNT_SECURITY, "explicit_compromise_language", "high"))

    if _MARKET_RE.search(text):
        matches.append((MARKET, "whole_service_availability_phrase", "medium"))

    if _CONTENT_RE.search(text):
        matches.append((CONTENT, "specific_content_missing_or_miscataloged", "medium"))

    billing_action = _BILLING_ACTION_RE.search(text)
    signup_with_plan_context = _SIGNUP_CONTEXT_RE.search(text) and _BILLING_PLAN_CONTEXT_RE.search(text)
    if billing_action or signup_with_plan_context:
        reason = "billing_action_keyword" if billing_action else "signup_with_plan_context"
        matches.append((BILLING, reason, "high" if billing_action else "medium"))

    login_topic = _LOGIN_TOPIC_RE.search(text)
    tech_malfunction = _TECH_MALFUNCTION_RE.search(text)
    tech_id = _TECH_ID_RE.search(text)
    broken_ui = _BROKEN_UI_RE.search(text)
    troubleshooting = _TROUBLESHOOTING_RE.search(text)

    if login_topic:
        # Finalized Access-vs-Technical tie-break: check criteria 1-3 in order.
        if tech_id:
            matches.append((TECHNICAL, "login_with_technical_identifier", "high"))
        elif broken_ui:
            matches.append((TECHNICAL, "login_with_broken_ui_element", "high"))
        elif troubleshooting:
            matches.append((TECHNICAL, "login_with_troubleshooting_behavior", "medium"))
        else:
            matches.append((ACCOUNT_ACCESS, "login_topic_no_malfunction_evidence", "high"))
    elif tech_malfunction or tech_id or broken_ui:
        matches.append((TECHNICAL, "technical_malfunction_language", "high" if tech_malfunction else "medium"))

    if _FEATURE_RE.search(text):
        matches.append((FEATURE, "feature_request_phrase", "medium"))

    if _COMPLAINT_RE.search(text):
        matches.append((COMPLAINT, "vague_dissatisfaction_phrase", "medium"))

    return matches


def classify_text(text: str) -> ClassificationResult:
    """Classify a single message string. This is the core rule engine;
    `classify_candidate` below wraps it with the root-context fallback."""
    non_english = is_likely_non_english(text)
    text = _normalize(text or "")

    if _PRAISE_ONLY_RE.match(text.strip()):
        return ClassificationResult(OTHER, None, "deterministic", "praise_only_pattern", "high", False, non_english, [])

    if _OFF_TOPIC_RE.search(text):
        return ClassificationResult(OTHER, None, "deterministic", "off_topic_pattern", "high", False, non_english, [])

    matches = _match_intents(text)
    if not matches:
        return ClassificationResult(OTHER, None, "deterministic", "no_pattern_matched", "low", False, non_english, [])

    # order matches by PRIORITY_ORDER, dedup by intent (keep first/strongest)
    seen = {}
    for intent, reason, conf in matches:
        if intent not in seen:
            seen[intent] = (reason, conf)
    ordered = [i for i in PRIORITY_ORDER if i in seen]

    primary = ordered[0]
    reason, conf = seen[primary]
    secondary = ordered[1] if len(ordered) > 1 else None
    ambiguous = len(ordered) > 1

    return ClassificationResult(
        primary_intent=primary,
        secondary_issue=secondary,
        labeling_method="deterministic",
        labeling_reason=reason,
        labeling_confidence=conf,
        ambiguous=ambiguous,
        non_english=non_english,
        matched_intents=ordered,
    )


def classify_candidate(customer_message: str, context_messages_json: str | None) -> ClassificationResult:
    """Classify a resolution-corpus row. Tries the candidate's own
    customer_message first (the primary signal, per this phase's
    instructions). If that yields OTHER/UNKNOWN with low confidence and
    the candidate has ancestor context (i.e. it is NOT itself the
    conversation's root message), falls back to classifying the
    conversation's ROOT message (context[0]) instead -- the root is
    where the customer's actual problem was first stated, and mid-
    conversation follow-ups ("here's my email", "yes") are often not
    intent-bearing on their own. This fallback is a deliberate,
    documented design decision (see docs/TODO.md's Phase 7D entry), not
    a reuse of Phase 2's root-only regexes verbatim."""
    direct = classify_text(customer_message)
    if direct.primary_intent != OTHER or not context_messages_json:
        return direct

    try:
        context = json.loads(context_messages_json)
    except (json.JSONDecodeError, TypeError):
        context = []

    if not context:
        return direct

    root_text = context[0].get("text", "")
    root_result = classify_text(root_text)
    if root_result.primary_intent == OTHER:
        return direct  # fallback didn't help either; keep the direct (OTHER) result

    return ClassificationResult(
        primary_intent=root_result.primary_intent,
        secondary_issue=root_result.secondary_issue,
        labeling_method="deterministic_root_context",
        labeling_reason=f"root_context:{root_result.labeling_reason}",
        labeling_confidence=root_result.labeling_confidence,
        ambiguous=root_result.ambiguous,
        non_english=direct.non_english or root_result.non_english,
        matched_intents=root_result.matched_intents,
    )
