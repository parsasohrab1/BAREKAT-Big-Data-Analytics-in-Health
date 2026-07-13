"""Tests for CAD stub."""

from barekat.imaging.cad import CADAnalyzer


def test_cad_stub_chest():
    analyzer = CADAnalyzer()
    result = analyzer.analyze("1.2.3.4", modality="CR")
    assert result["model_status"] == "stub_not_trained"
    assert result["phase"] == "next"
    assert len(result["findings"]) >= 1
