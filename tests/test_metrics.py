"""Tests for ML evaluation metrics."""

import numpy as np

from barekat.ml.metrics import compute_calibration, evaluate_classifier


def test_evaluate_classifier_perfect_scores():
    y_true = np.array([0, 0, 1, 1, 1, 0])
    y_prob = np.array([0.1, 0.2, 0.9, 0.85, 0.95, 0.15])
    result = evaluate_classifier(y_true, y_prob, threshold=0.5)

    assert result["auc"] is not None
    assert result["auc"] > 0.9
    assert result["f1"] > 0.5
    assert "calibration" in result
    assert "brier_score" in result["calibration"]


def test_compute_calibration_structure():
    y_true = np.array([0, 0, 1, 1, 0, 1, 0, 1, 1, 0])
    y_prob = np.array([0.1, 0.2, 0.8, 0.7, 0.3, 0.9, 0.4, 0.6, 0.85, 0.15])
    cal = compute_calibration(y_true, y_prob, n_bins=5)

    assert "fraction_positive" in cal
    assert "mean_predicted" in cal
    assert cal["brier_score"] is not None
