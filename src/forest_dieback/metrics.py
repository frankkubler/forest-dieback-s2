"""Métriques d'évaluation face à la vérité photo-interprétée."""

from __future__ import annotations

import numpy as np


def binary_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true).astype(bool)
    y_pred = np.asarray(y_pred).astype(bool)
    tp = np.sum(y_true & y_pred)
    fp = np.sum(~y_true & y_pred)
    fn = np.sum(y_true & ~y_pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": float(precision), "recall": float(recall), "f1": float(f1)}


def detection_delay(ref_dates, pred_dates) -> float:
    """Délai médian (jours) entre la date de référence et la détection.

    Les deux entrées sont des tableaux de dates numpy (datetime64) alignés ;
    NaT signifie « jamais détecté » et n'entre pas dans la médiane.
    """
    ref = np.asarray(ref_dates, dtype="datetime64[D]")
    pred = np.asarray(pred_dates, dtype="datetime64[D]")
    ok = ~np.isnat(ref) & ~np.isnat(pred)
    if not ok.any():
        return float("nan")
    return float(np.median((pred[ok] - ref[ok]).astype(int)))
