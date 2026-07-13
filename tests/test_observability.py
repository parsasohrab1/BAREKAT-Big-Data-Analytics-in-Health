"""Tests for observability metrics and drift detection."""

import numpy as np

from barekat.observability.drift import compute_psi
from barekat.observability.metrics import record_drift, record_etl_run


def test_psi_identical_distributions():
    data = np.random.normal(0, 1, 1000)
    psi = compute_psi(data, data)
    assert psi < 0.01


def test_psi_shifted_distribution():
    baseline = np.random.normal(0, 1, 1000)
    shifted = np.random.normal(2, 1, 1000)
    psi = compute_psi(baseline, shifted)
    assert psi > 0.1


def test_record_etl_metrics():
    record_etl_run("incremental", "success", duration_sec=12.5)
    record_etl_run("incremental", "failed", duration_sec=None)


def test_record_drift_metrics():
    record_drift("readmission", psi=0.25, auc_drop=0.06, detected=True)
    record_drift("readmission", psi=0.05, auc_drop=0.01, detected=False)
