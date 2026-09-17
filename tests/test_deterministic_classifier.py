"""
Unit tests for src/intent/deterministic_classifier.py.

All tests use small synthetic strings/fixtures -- none reads the real
41,092-row corpus (that's covered by
tests/test_intent_corpus_smoke.py) and none reads or references the
golden set at all (per this phase's explicit rule that golden labels
must never be used to fit, tune, or validate this classifier).
"""

import json

from intent.deterministic_classifier import (
    ACCOUNT_ACCESS,
    ACCOUNT_SECURITY,
    BILLING,
    COMPLAINT,
    CONTENT,
    FEATURE,
    MARKET,
    OTHER,
    TECHNICAL,
    classify_candidate,
    classify_text,
)


# ---------------------------------------------------------------------
# All 9 canonical labels reachable
# ---------------------------------------------------------------------

def test_account_access_reachable():
    r = classify_text("I can't log in, it says my password is invalid")
    assert r.primary_intent == ACCOUNT_ACCESS


def test_account_security_reachable():
    r = classify_text("My account was hacked and the email was changed")
    assert r.primary_intent == ACCOUNT_SECURITY


def test_billing_reachable():
    r = classify_text("I was charged twice this month for my subscription")
    assert r.primary_intent == BILLING


def test_technical_reachable():
    r = classify_text("The app keeps crashing every time I try to play a song")
    assert r.primary_intent == TECHNICAL


def test_content_reachable():
    r = classify_text("Why isn't the new Taylor Swift album on Spotify")
    assert r.primary_intent == CONTENT


def test_feature_reachable():
    r = classify_text("Please add a dark mode option to the app")
    assert r.primary_intent == FEATURE


def test_complaint_reachable():
    r = classify_text("This is the worst customer service I have ever experienced")
    assert r.primary_intent == COMPLAINT


def test_market_reachable():
    r = classify_text("When will Spotify be available in Nepal")
    assert r.primary_intent == MARKET


def test_other_reachable_for_uninformative_text():
    r = classify_text("ok cool thanks for that info I guess")
    assert r.primary_intent == OTHER


# ---------------------------------------------------------------------
# Deterministic / reproducible
# ---------------------------------------------------------------------

def test_classification_is_deterministic():
    text = "I can't log in, it says my password is invalid"
    r1 = classify_text(text)
    r2 = classify_text(text)
    assert r1.to_dict() == r2.to_dict()


def test_classify_candidate_reproducible():
    msg = "The app crashes on startup"
    r1 = classify_candidate(msg, None)
    r2 = classify_candidate(msg, None)
    assert r1.to_dict() == r2.to_dict()


# ---------------------------------------------------------------------
# Account Access vs Technical -- finalized tie-break
# (docs/TAXONOMY_CONTRACT_FINAL.md)
# ---------------------------------------------------------------------

def test_tiebreak_bare_login_failure_is_access():
    r = classify_text("I can't log in, please help")
    assert r.primary_intent == ACCOUNT_ACCESS


def test_tiebreak_invalid_password_is_access_not_technical():
    r = classify_text("it says my password is invalid when I try to log in")
    assert r.primary_intent == ACCOUNT_ACCESS


def test_tiebreak_technical_identifier_wins():
    r = classify_text("trying to log in but the CSRF token is invalid")
    assert r.primary_intent == TECHNICAL
    assert r.labeling_reason == "login_with_technical_identifier"


def test_tiebreak_http_error_code_wins():
    r = classify_text("I'm getting error 404 trying to login to my account")
    assert r.primary_intent == TECHNICAL


def test_tiebreak_broken_ui_wins():
    r = classify_text("the login buttons don't work on the app")
    assert r.primary_intent == TECHNICAL
    assert r.labeling_reason == "login_with_broken_ui_element"


def test_tiebreak_troubleshooting_behavior_wins():
    r = classify_text("I cleared cache, uninstalled, reinstalled and now I can't log in")
    assert r.primary_intent == TECHNICAL
    assert r.labeling_reason == "login_with_troubleshooting_behavior"


def test_tiebreak_smart_quote_normalized():
    """Smart/curly apostrophe must be handled identically to a straight one."""
    r = classify_text("it says my password is invalid, I can’t log in")
    assert r.primary_intent == ACCOUNT_ACCESS


# ---------------------------------------------------------------------
# Technical vs Content Availability
# ---------------------------------------------------------------------

def test_technical_vs_content_error_language_wins_technical():
    r = classify_text("this song won't play, I get an error message every time")
    assert r.primary_intent == TECHNICAL


def test_technical_vs_content_named_entity_no_bug_language_is_content():
    r = classify_text("why isn't the new Drake album on Spotify")
    assert r.primary_intent == CONTENT


# ---------------------------------------------------------------------
# Feature Request vs General Complaint
# ---------------------------------------------------------------------

def test_feature_vs_complaint_concrete_ask_wins_feature():
    r = classify_text("please add a shuffle button or I'm switching to Tidal")
    assert r.primary_intent == FEATURE


def test_feature_vs_complaint_pure_venting_is_complaint():
    r = classify_text("just lost a customer, switching to apple music, worst customer service")
    assert r.primary_intent == COMPLAINT


# ---------------------------------------------------------------------
# Country/Market vs Content Availability
# ---------------------------------------------------------------------

def test_market_vs_content_service_availability_is_market():
    r = classify_text("why isn't Spotify available in Egypt")
    assert r.primary_intent == MARKET


def test_market_vs_content_specific_content_is_content():
    r = classify_text("why isn't this album available in Egypt")
    assert r.primary_intent == CONTENT


# ---------------------------------------------------------------------
# OTHER/UNKNOWN fallback
# ---------------------------------------------------------------------

def test_other_for_praise_only():
    r = classify_text("Thanks!")
    assert r.primary_intent == OTHER
    assert r.labeling_reason == "praise_only_pattern"


def test_other_for_off_topic():
    r = classify_text("hey I'm a graphic designer looking for job opportunities")
    assert r.primary_intent == OTHER
    assert r.labeling_reason == "off_topic_pattern"


def test_other_for_no_pattern_matched():
    r = classify_text("hmm okay I guess that makes sense")
    assert r.primary_intent == OTHER
    assert r.labeling_reason == "no_pattern_matched"
    assert r.labeling_confidence == "low"


# ---------------------------------------------------------------------
# Multiple-issue / ambiguous handling
# ---------------------------------------------------------------------

def test_multiple_issues_sets_secondary_and_ambiguous():
    # Security (hacked) + Billing (charged) both present.
    r = classify_text("my account was hacked and now I'm being charged for a subscription I didn't want")
    assert r.primary_intent == ACCOUNT_SECURITY  # higher priority
    assert r.secondary_issue == BILLING
    assert r.ambiguous is True


def test_single_issue_has_no_secondary_and_not_ambiguous():
    r = classify_text("I was charged twice this month")
    assert r.secondary_issue is None
    assert r.ambiguous is False


# ---------------------------------------------------------------------
# Non-English handling
# ---------------------------------------------------------------------

def test_non_english_flag_set_for_non_ascii_heavy_text():
    # The ASCII-ratio heuristic (reused from Phase 1/5) only reliably
    # catches non-Latin scripts -- mostly-Latin European text (e.g.
    # German) is a documented lower-bound limitation, not a bug here.
    r = classify_text("私はログインできません。パスワードが間違っています")
    assert r.non_english is True


def test_non_english_flag_false_for_english():
    r = classify_text("I can't log in, my password is invalid")
    assert r.non_english is False


# ---------------------------------------------------------------------
# Root-context fallback (multi-turn) + no mutation of input
# ---------------------------------------------------------------------

def test_root_context_fallback_used_when_direct_message_uninformative():
    context = json.dumps([
        {"tweet_id": 1, "role": "customer", "author_id": "c", "text": "my account was hacked!", "timestamp": None},
        {"tweet_id": 2, "role": "brand", "author_id": "SpotifyCares", "text": "can you DM us?", "timestamp": None},
    ])
    r = classify_candidate("ok will do", context)
    assert r.primary_intent == ACCOUNT_SECURITY
    assert r.labeling_method == "deterministic_root_context"
    assert r.labeling_reason == "root_context:explicit_compromise_language"


def test_root_context_fallback_not_used_when_direct_message_is_informative():
    context = json.dumps([{"tweet_id": 1, "role": "customer", "author_id": "c", "text": "my account was hacked!", "timestamp": None}])
    r = classify_candidate("I was also charged twice for my subscription", context)
    assert r.primary_intent == BILLING
    assert r.labeling_method == "deterministic"


def test_root_context_fallback_gives_up_gracefully_when_root_also_uninformative():
    context = json.dumps([{"tweet_id": 1, "role": "customer", "author_id": "c", "text": "ok", "timestamp": None}])
    r = classify_candidate("thanks", context)
    assert r.primary_intent == OTHER


def test_malformed_context_json_does_not_crash():
    r = classify_candidate("some message", "not valid json{{{")
    assert r.primary_intent in {OTHER}  # falls back to direct classification only


def test_no_context_available_falls_back_to_direct_result():
    r = classify_candidate("thanks", None)
    assert r.primary_intent == OTHER


def test_classify_functions_do_not_mutate_input_strings():
    original = "I can’t log in"
    original_copy = str(original)
    classify_text(original)
    assert original == original_copy
