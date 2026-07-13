"""ML pipeline orchestrator with versioning and alert persistence."""

from __future__ import annotations

import pandas as pd

from barekat.ml.clustering import PatientClusterer
from barekat.ml.data_loader import load_training_data
from barekat.ml.los import LOSPredictor
from barekat.ml.mortality_sepsis import EarlyWarningPredictor
from barekat.ml.nlp_notes import ClinicalNotesNLP
from barekat.ml.readmission import ReadmissionPredictor
from barekat.ml.vitals_monitor import VitalsMonitor
from barekat.services.alerts import persist_alerts


class MLPipeline:
    def __init__(self) -> None:
        self.readmission = ReadmissionPredictor()
        self.clustering = PatientClusterer()
        self.los = LOSPredictor()
        self.early_warning = EarlyWarningPredictor()
        self.nlp = ClinicalNotesNLP()
        self.vitals = VitalsMonitor()

    def run_all(self, data: dict | None = None) -> dict:
        if data is None:
            data = load_training_data()

        if not data:
            raise ValueError("No training data available")

        results: dict = {}
        results["readmission"] = self.readmission.train(data)
        results["clustering"] = self.clustering.train(data)
        results["los"] = self.los.train(data)
        results["early_warning"] = self.early_warning.train(data)
        results["nlp"] = self.nlp.train(data)
        results["vitals"] = self.vitals.train(data)

        alerts_df = self._collect_alerts(data)
        results["alerts_generated"] = len(alerts_df)
        results["alerts_persisted"] = self._persist_alerts_safe(alerts_df)
        return results

    def retrain(self) -> dict:
        """Periodic retrain using latest data from PostgreSQL or CSV."""
        return self.run_all(load_training_data(prefer_postgres=True))

    def _collect_alerts(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        frames = [
            self.readmission.generate_alerts(data),
            self.los.generate_bed_plan_alerts(data),
            self.early_warning.generate_alerts(data),
            self.vitals.generate_alerts(data),
        ]
        non_empty = [f for f in frames if not f.empty]
        if not non_empty:
            return pd.DataFrame()
        return pd.concat(non_empty, ignore_index=True)

    def _persist_alerts_safe(self, alerts_df: pd.DataFrame) -> int:
        if alerts_df.empty:
            return 0
        persist_cols = [
            c for c in [
                "patient_id", "admission_id", "alert_type",
                "severity", "message", "risk_score",
            ]
            if c in alerts_df.columns
        ]
        try:
            return persist_alerts(alerts_df[persist_cols])
        except Exception as exc:
            print(f"Warning: could not persist alerts to database: {exc}")
            return 0
