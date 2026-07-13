"""Model evaluation metrics: AUC, F1, calibration."""

from __future__ import annotations

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_classifier(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
    n_bins: int = 10,
) -> dict:
    """Compute classification metrics including calibration data."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    y_pred = (y_prob >= threshold).astype(int)

    metrics: dict = {
        "threshold": threshold,
        "samples": int(len(y_true)),
        "positive_rate": round(float(y_true.mean()), 4),
    }

    if len(np.unique(y_true)) > 1:
        metrics["auc"] = round(float(roc_auc_score(y_true, y_prob)), 4)
    else:
        metrics["auc"] = None

    metrics["accuracy"] = round(float(accuracy_score(y_true, y_pred)), 4)
    metrics["f1"] = round(float(f1_score(y_true, y_pred, zero_division=0)), 4)
    metrics["precision"] = round(float(precision_score(y_true, y_pred, zero_division=0)), 4)
    metrics["recall"] = round(float(recall_score(y_true, y_pred, zero_division=0)), 4)
    metrics["brier_score"] = round(float(brier_score_loss(y_true, y_prob)), 4)

    calibration = compute_calibration(y_true, y_prob, n_bins=n_bins)
    metrics["calibration"] = calibration

    return metrics


def compute_calibration(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> dict:
    """Reliability diagram data for probability calibration."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)

    if len(y_true) < n_bins or len(np.unique(y_true)) < 2:
        return {
            "fraction_positive": [],
            "mean_predicted": [],
            "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4) if len(y_true) else None,
            "well_calibrated": None,
        }

    fraction_pos, mean_pred = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy="uniform",
    )
    # Mean absolute calibration error
    mace = float(np.mean(np.abs(fraction_pos - mean_pred)))

    return {
        "fraction_positive": [round(float(x), 4) for x in fraction_pos],
        "mean_predicted": [round(float(x), 4) for x in mean_pred],
        "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4),
        "mean_abs_calibration_error": round(mace, 4),
        "well_calibrated": mace < 0.1,
    }


def evaluate_regressor(y_true, y_pred) -> dict:
    """Regression metrics for LOS and similar models."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    y_true = np.asarray(y_true).astype(float)
    y_pred = np.asarray(y_pred).astype(float)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {
        "samples": int(len(y_true)),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "rmse": round(rmse, 3),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "mean_actual": round(float(y_true.mean()), 3),
        "mean_predicted": round(float(y_pred.mean()), 3),
    }
