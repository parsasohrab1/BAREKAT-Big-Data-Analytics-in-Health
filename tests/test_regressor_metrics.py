"""Tests for regression metrics."""

import numpy as np
from barekat.ml.metrics import evaluate_regressor


def test_evaluate_regressor_perfect_fit():
    y = np.array([3.0, 5.0, 7.0, 9.0])
    metrics = evaluate_regressor(y, y)
    assert metrics["mae"] == 0.0
    assert metrics["rmse"] == 0.0
    assert metrics["r2"] == 1.0
