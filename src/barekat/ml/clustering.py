"""Patient clustering for population health analytics."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from barekat.config.settings import get_settings


class PatientClusterer:
    """Cluster patients based on clinical and demographic features."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.n_clusters = self.settings.ml_cluster_count
        self.scaler = StandardScaler()
        self.model = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)
        self.model_path = Path(self.settings.data_models_path) / "clustering_model.joblib"
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

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

        numeric_cols = ["age", "bmi", "diabetes", "hypertension",
                        "total_admissions", "avg_los", "icu_rate", "readmission_rate"]
        features["gender_m"] = (features["gender"] == "M").astype(int)
        numeric_cols.append("gender_m")

        return features[["patient_id"] + [c for c in numeric_cols if c in features.columns]]

    def train(self, data: dict[str, pd.DataFrame]) -> dict:
        features = self._build_patient_features(data)
        X = features.drop(columns=["patient_id"])
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)

        features["cluster"] = self.model.labels_
        joblib.dump({"model": self.model, "scaler": self.scaler}, self.model_path)

        cluster_sizes = features["cluster"].value_counts().to_dict()
        return {
            "n_clusters": self.n_clusters,
            "cluster_sizes": cluster_sizes,
            "samples": len(features),
            "model_path": str(self.model_path),
        }

    def predict(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        if self.model_path.exists():
            saved = joblib.load(self.model_path)
            self.model = saved["model"]
            self.scaler = saved["scaler"]

        features = self._build_patient_features(data)
        X = features.drop(columns=["patient_id"])
        X_scaled = self.scaler.transform(X)
        features["cluster"] = self.model.predict(X_scaled)
        return features[["patient_id", "cluster"]]
