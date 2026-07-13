"""Patient clustering for population health analytics."""

from __future__ import annotations

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from barekat.config.settings import get_settings
from barekat.ml.registry import load_active_artifact, register_model


class PatientClusterer:
    """Cluster patients based on clinical and demographic features."""

    MODEL_NAME = "clustering"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.n_clusters = self.settings.ml_cluster_count
        self.scaler = StandardScaler()
        self.model = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)

    def _build_patient_features(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        patients = data["Patients"].copy()
        admissions = data["Admissions"]

        adm_stats = admissions.groupby("Patient_ID").agg(
            total_admissions=("Admission_ID", "count"),
            avg_los=("Length_of_Stay", "mean"),
            icu_rate=("ICU_Required", "mean"),
            readmission_rate=("Readmission_Flag", "mean"),
        ).reset_index()

        features = patients.merge(adm_stats, on="Patient_ID", how="left").fillna(0)
        features.columns = [c.lower() for c in features.columns]

        numeric_cols = [
            c for c in [
                "age", "bmi", "diabetes", "hypertension",
                "total_admissions", "avg_los", "icu_rate", "readmission_rate",
            ]
            if c in features.columns
        ]
        if "gender" in features.columns:
            features["gender_m"] = (features["gender"] == "M").astype(int)
            numeric_cols.append("gender_m")

        return features[["patient_id"] + numeric_cols]

    def train(self, data: dict[str, pd.DataFrame]) -> dict:
        features = self._build_patient_features(data)
        X = features.drop(columns=["patient_id"])
        X_scaled = self.scaler.fit_transform(X)
        labels = self.model.fit_predict(X_scaled)
        features["cluster"] = labels

        silhouette = None
        if self.n_clusters > 1 and len(X) > self.n_clusters:
            silhouette = round(float(silhouette_score(X_scaled, labels)), 4)

        cluster_sizes = features["cluster"].value_counts().to_dict()
        metrics = {
            "n_clusters": self.n_clusters,
            "cluster_sizes": {str(k): int(v) for k, v in cluster_sizes.items()},
            "silhouette_score": silhouette,
        }

        registration = register_model(
            model_name=self.MODEL_NAME,
            artifact={"model": self.model, "scaler": self.scaler},
            metrics=metrics,
            samples=len(features),
        )

        return {
            "version": registration["version"],
            "n_clusters": self.n_clusters,
            "cluster_sizes": cluster_sizes,
            "silhouette_score": silhouette,
            "samples": len(features),
            "artifact_path": registration["artifact_path"],
        }

    def predict(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        saved = load_active_artifact(self.MODEL_NAME)
        if saved:
            self.model = saved["model"]
            self.scaler = saved["scaler"]

        features = self._build_patient_features(data)
        X = features.drop(columns=["patient_id"])
        X_scaled = self.scaler.transform(X)
        features["cluster"] = self.model.predict(X_scaled)
        return features[["patient_id", "cluster"]]
