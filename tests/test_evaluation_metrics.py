"""
Unit tests for evaluation/metrics.py. Purely synthetic data -- no
golden set, no live model calls.
"""

from evaluation.metrics import cohen_kappa, escalation_metrics, intent_classification_metrics, spearman_agreement

LABELS = ["A", "B", "C"]


def test_intent_metrics_perfect_agreement():
    gold = ["A", "B", "C", "A"]
    pred = ["A", "B", "C", "A"]
    m = intent_classification_metrics(gold, pred, LABELS)
    assert m["accuracy"] == 1.0
    assert m["macro_f1"] == 1.0
    assert m["n_examples"] == 4


def test_intent_metrics_exposes_per_class_and_confusion_matrix():
    gold = ["A", "A", "B", "C"]
    pred = ["A", "B", "B", "C"]
    m = intent_classification_metrics(gold, pred, LABELS)
    assert m["accuracy"] == 0.75
    assert set(m["per_intent"].keys()) == set(LABELS)
    assert m["per_intent"]["A"]["support"] == 2
    assert m["confusion_matrix"]["labels"] == LABELS
    assert len(m["confusion_matrix"]["matrix"]) == 3


def test_intent_metrics_zero_examples_does_not_crash():
    m = intent_classification_metrics([], [], LABELS)
    assert m["n_examples"] == 0
    assert m["accuracy"] == 0.0


def test_escalation_metrics_basic_confusion():
    system_escalate = [True, False, True, False]
    human_should = ["yes", "no", "no", "yes"]
    m = escalation_metrics(system_escalate, human_should)
    assert m["true_positive"] == 1
    assert m["false_positive"] == 1
    assert m["false_negative"] == 1
    assert m["true_negative"] == 1
    assert m["n_scored"] == 4
    assert m["unsafe_auto_resolution_count"] == 1
    assert m["unnecessary_escalation_count"] == 1


def test_escalation_metrics_excludes_uncertain():
    system_escalate = [True, False, True]
    human_should = ["yes", "uncertain", "no"]
    m = escalation_metrics(system_escalate, human_should)
    assert m["n_uncertain_excluded"] == 1
    assert m["n_scored"] == 2
    assert m["n_total"] == 3


def test_escalation_metrics_all_uncertain_returns_none_metrics():
    m = escalation_metrics([True, False], ["uncertain", "uncertain"])
    assert m["n_scored"] == 0


def test_escalation_metrics_accepts_boolean_and_none_form():
    """Phase 11's human_should_escalate uses True/False/None, not the legacy
    'yes'/'no'/'uncertain' strings -- both encodings must normalize the same."""
    system_escalate = [True, False, True, False, True]
    human_should = [True, False, False, True, None]
    m = escalation_metrics(system_escalate, human_should)
    assert m["true_positive"] == 1
    assert m["false_positive"] == 1
    assert m["false_negative"] == 1
    assert m["true_negative"] == 1
    assert m["n_uncertain_excluded"] == 1
    assert m["n_scored"] == 4
    assert m["n_total"] == 5
    assert m["precision"] == 0.5
    assert m["unsafe_auto_resolution_rate"] == 0.25


def test_spearman_agreement_perfect_correlation():
    a = [1, 2, 3, 4, 5]
    b = [1, 2, 3, 4, 5]
    result = spearman_agreement(a, b)
    assert result["spearman_r"] == 1.0


def test_spearman_agreement_insufficient_data():
    result = spearman_agreement([3], [3])
    assert result["spearman_r"] is None
    assert "insufficient" in result["note"]


def test_cohen_kappa_perfect_agreement():
    a = [True, False, True, False, True]
    b = [True, False, True, False, True]
    result = cohen_kappa(a, b)
    assert result["kappa"] == 1.0


def test_cohen_kappa_insufficient_variation():
    result = cohen_kappa([True], [True])
    assert result["kappa"] is None
