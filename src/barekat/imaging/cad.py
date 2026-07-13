"""CAD (Computer-Aided Diagnosis) — placeholder for next phase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CADFinding:
    label: str
    confidence: float
    region: str
    icd_hint: str = ""
    severity: str = "low"
    model_version: str = "cad-stub-v0"


class CADAnalyzer:
    """Stub CAD analyzer — replace with real models in next phase.

    Planned models:
    - Chest X-ray: pneumothorax, cardiomegaly, nodule detection
    - CT: hemorrhage, PE, lung nodule
    - Mammography: mass / calcification
    """

    MODEL_STATUS = "stub_not_trained"

    def analyze(self, study_uid: str, modality: str = "") -> dict[str, Any]:
        modality = modality.upper()
        findings: list[CADFinding] = []

        if modality in ("CR", "DX", "XR"):
            findings.append(CADFinding(
                label="No acute finding (stub)",
                confidence=0.55,
                region="chest",
                severity="low",
            ))
        elif modality == "CT":
            findings.append(CADFinding(
                label="CAD CT analysis — phase 2",
                confidence=0.0,
                region="volume",
                severity="low",
            ))
        else:
            findings.append(CADFinding(
                label=f"CAD not available for modality {modality or 'unknown'}",
                confidence=0.0,
                region="n/a",
            ))

        return {
            "study_uid": study_uid,
            "modality": modality,
            "model_status": self.MODEL_STATUS,
            "phase": "next",
            "findings": [
                {
                    "label": f.label,
                    "confidence": f.confidence,
                    "region": f.region,
                    "icd_hint": f.icd_hint,
                    "severity": f.severity,
                    "model_version": f.model_version,
                }
                for f in findings
            ],
            "disclaimer": "CAD results are stub placeholders — not for clinical use.",
        }
