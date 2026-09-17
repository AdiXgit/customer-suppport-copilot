"""
Phase 10: metric calculations. Pure functions, no I/O, no golden-set
awareness of its own -- callers pass in whatever gold/predicted label
lists they have (evaluation/runner.py is the only place golden labels
are actually read from disk).
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from scipy.stats import spearmanr


def intent_classification_metrics(gold_labels: list[str], predicted_labels: list[str], labels: list[str]) -> dict:
    """Accuracy, macro P/R/F1, per-label P/R/F1, and a confusion matrix.
    `labels` fixes the label order (must include every class that can
    appear in either list, including OTHER/UNKNOWN) so the confusion
    matrix and per-label arrays are ordered consistently regardless of
    which classes happen to appear in this particular sample."""
    n = len(gold_labels)
    if n == 0:
        return {
            "n_examples": 0,
            "accuracy": 0.0,
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "macro_f1": 0.0,
            "per_intent": {label: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0} for label in labels},
            "confusion_matrix": {"labels": labels, "matrix": [[0] * len(labels) for _ in labels]},
            "gold_class_distribution": {},
            "predicted_class_distribution": {},
        }

    accuracy = sum(1 for g, p in zip(gold_labels, predicted_labels) if g == p) / n

    precision, recall, f1, support = precision_recall_fscore_support(
        gold_labels, predicted_labels, labels=labels, average=None, zero_division=0,
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        gold_labels, predicted_labels, labels=labels, average="macro", zero_division=0,
    )
    cm = confusion_matrix(gold_labels, predicted_labels, labels=labels)

    per_label = {
        labels[i]: {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
        }
        for i in range(len(labels))
    }

    return {
        "n_examples": n,
        "accuracy": round(accuracy, 4),
        "macro_precision": round(float(macro_precision), 4),
        "macro_recall": round(float(macro_recall), 4),
        "macro_f1": round(float(macro_f1), 4),
        "per_intent": per_label,
        "confusion_matrix": {
            "labels": labels,
            "matrix": cm.tolist(),
        },
        "gold_class_distribution": dict(Counter(gold_labels)),
        "predicted_class_distribution": dict(Counter(predicted_labels)),
    }


def escalation_metrics(system_escalate: list[bool], human_should_escalate: list) -> dict:
    """human_should_escalate entries accept either the boolean/None form used by
    Phase 11 (True = should escalate, False = agent can handle it, None =
    genuinely undeterminable) or the legacy 'yes' / 'no' / 'uncertain' strings
    from the original Phase 10 template design -- both are normalized here.
    UNCERTAIN/None cases are excluded from precision/recall/F1 (Step 11) but
    counted and reported explicitly, never silently dropped.

    UNSAFE_AUTO_RESOLUTION: human says yes (should escalate), system did not.
    UNNECESSARY_ESCALATION: human says no (should not escalate), system did.
    """
    assert len(system_escalate) == len(human_should_escalate)

    tp = fp = fn = tn = 0
    n_excluded = 0
    unsafe_auto_resolution = 0
    unnecessary_escalation = 0

    for sys_esc, human in zip(system_escalate, human_should_escalate):
        if human is None:
            n_excluded += 1
            continue
        if isinstance(human, bool):
            human_norm = "yes" if human else "no"
        else:
            human_norm = (human or "").strip().lower()
        if human_norm == "uncertain":
            n_excluded += 1
            continue
        should = human_norm == "yes"
        if should and sys_esc:
            tp += 1
        elif should and not sys_esc:
            fn += 1
            unsafe_auto_resolution += 1
        elif not should and sys_esc:
            fp += 1
            unnecessary_escalation += 1
        else:
            tn += 1

    n_scored = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall) > 0) else None
    agreement_rate = (tp + tn) / n_scored if n_scored else None

    return {
        "n_total": len(system_escalate),
        "n_uncertain_excluded": n_excluded,
        "n_scored": n_scored,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "agreement_rate": round(agreement_rate, 4) if agreement_rate is not None else None,
        "unsafe_auto_resolution_count": unsafe_auto_resolution,
        "unsafe_auto_resolution_rate": round(unsafe_auto_resolution / n_scored, 4) if n_scored else None,
        "unnecessary_escalation_count": unnecessary_escalation,
        "unnecessary_escalation_rate": round(unnecessary_escalation / n_scored, 4) if n_scored else None,
        "definitions": {
            "unsafe_auto_resolution": "Human judgment says escalation was required but the system auto-handled it (a false negative on 'should escalate').",
            "unnecessary_escalation": "Human judgment says escalation was not required but the system escalated (a false positive on 'should escalate').",
        },
    }


def spearman_agreement(scores_a: list[float], scores_b: list[float]) -> dict:
    """Ordinal (1-5 rating) agreement between two raters/judges."""
    if len(scores_a) < 2:
        return {"n": len(scores_a), "spearman_r": None, "p_value": None, "note": "insufficient data (need >=2 paired scores)"}
    r, p = spearmanr(scores_a, scores_b)
    return {"n": len(scores_a), "spearman_r": round(float(r), 4) if r == r else None, "p_value": round(float(p), 4) if p == p else None}


def cohen_kappa(labels_a: list, labels_b: list) -> dict:
    """Binary/categorical agreement (e.g. hallucination true/false)."""
    from sklearn.metrics import cohen_kappa_score
    if len(labels_a) < 2 or len(set(labels_a) | set(labels_b)) < 2:
        return {"n": len(labels_a), "kappa": None, "note": "insufficient variation to compute kappa"}
    kappa = cohen_kappa_score(labels_a, labels_b)
    agreement_rate = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / len(labels_a)
    return {"n": len(labels_a), "kappa": round(float(kappa), 4), "raw_agreement_rate": round(agreement_rate, 4)}
