"""Tests for department risk thresholds."""

from barekat.ml.thresholds import get_threshold


def test_get_threshold_fallback():
    threshold = get_threshold("Unknown Department")
    assert 0 <= threshold <= 1
