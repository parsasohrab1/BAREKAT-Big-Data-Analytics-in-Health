"""NLP on clinical notes — diagnosis extraction."""

from __future__ import annotations

import re

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from barekat.ml.registry import load_active_artifact, register_model

# Keyword → ICD mapping for rule-based extraction
ICD_KEYWORDS: dict[str, list[str]] = {
    "E11.9": ["diabetes", "diabetic", "type 2 diabetes", "hyperglycemia", "دیابت"],
    "I10": ["hypertension", "high blood pressure", "htn", "فشار خون"],
    "I25.10": ["ischemic heart", "cad", "coronary", "angina", "قلب"],
    "J44.9": ["copd", "emphysema", "chronic obstructive", "تنفس"],
    "N18.9": ["ckd", "chronic kidney", "renal failure", "کلیه"],
    "C50.9": ["breast cancer", "malignancy breast", "سرطان سینه"],
    "C34.9": ["lung cancer", "lung malignancy", "سرطان ریه"],
    "E66.9": ["obesity", "bmi elevated", "overweight", "چاقی"],
    "F32.9": ["depression", "depressive", "mdd", "افسردگی"],
    "M17.9": ["osteoarthritis", "knee pain", "joint degeneration", "آرتروز"],
    "A41.9": ["sepsis", "septic", "bacteremia", "سپسیس"],
    "R65.21": ["severe sepsis", "septic shock", "شوک سپتیک"],
}


class ClinicalNotesNLP:
    """Extract ICD diagnoses from free-text clinical notes."""

    MODEL_NAME = "nlp_diagnosis"

    def __init__(self) -> None:
        self.vectorizer: TfidfVectorizer | None = None
        self.reference_texts: list[str] = []
        self.reference_icd: list[str] = []

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text).lower().strip())

    def extract_by_keywords(self, text: str, min_confidence: float = 0.5) -> list[dict]:
        normalized = self._normalize(text)
        results = []
        for icd, keywords in ICD_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in normalized)
            if hits == 0:
                continue
            confidence = min(1.0, hits / max(len(keywords) * 0.3, 1))
            if confidence >= min_confidence:
                results.append({"icd_code": icd, "confidence": round(confidence, 3), "method": "keyword"})
        return sorted(results, key=lambda x: x["confidence"], reverse=True)

    def train(self, data: dict[str, pd.DataFrame]) -> dict:
        notes = data.get("Clinical_Notes", pd.DataFrame())
        diagnoses = data.get("Diagnoses", pd.DataFrame())
        if notes.empty or diagnoses.empty:
            return {"version": None, "skipped": True, "reason": "no clinical notes or diagnoses"}

        primary = diagnoses[diagnoses["Primary_Diagnosis"].astype(bool)]
        ref = primary.merge(notes, on="Admission_ID", how="inner")
        if ref.empty:
            return {"version": None, "skipped": True, "reason": "no matched note-diagnosis pairs"}

        self.reference_texts = ref["Note_Text"].astype(str).tolist()
        self.reference_icd = ref["ICD_Code"].astype(str).tolist()
        self.vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2), stop_words="english")
        self.vectorizer.fit(self.reference_texts)

        registration = register_model(
            model_name=self.MODEL_NAME,
            artifact={
                "vectorizer": self.vectorizer,
                "reference_texts": self.reference_texts,
                "reference_icd": self.reference_icd,
            },
            metrics={"samples": len(ref), "unique_icd": len(set(self.reference_icd))},
            samples=len(ref),
        )
        return {
            "version": registration["version"],
            "samples": len(ref),
            "unique_icd": len(set(self.reference_icd)),
            "artifact_path": registration["artifact_path"],
        }

    def load(self) -> bool:
        saved = load_active_artifact(self.MODEL_NAME)
        if not saved:
            return False
        self.vectorizer = saved.get("vectorizer")
        self.reference_texts = saved.get("reference_texts", [])
        self.reference_icd = saved.get("reference_icd", [])
        return True

    def extract_diagnoses(self, text: str, top_k: int = 3) -> list[dict]:
        """Extract ICD codes from a clinical note."""
        keyword_hits = self.extract_by_keywords(text)
        if not self.load() or not self.vectorizer or not self.reference_texts:
            return keyword_hits[:top_k]

        query_vec = self.vectorizer.transform([self._normalize(text)])
        ref_vec = self.vectorizer.transform(self.reference_texts)
        sims = cosine_similarity(query_vec, ref_vec).flatten()
        top_idx = sims.argsort()[::-1][:top_k]

        tfidf_results = []
        for idx in top_idx:
            if sims[idx] < 0.05:
                continue
            tfidf_results.append({
                "icd_code": self.reference_icd[idx],
                "confidence": round(float(sims[idx]), 3),
                "method": "tfidf_similarity",
            })

        merged: dict[str, dict] = {}
        for item in keyword_hits + tfidf_results:
            icd = item["icd_code"]
            if icd not in merged or item["confidence"] > merged[icd]["confidence"]:
                merged[icd] = item
        return sorted(merged.values(), key=lambda x: x["confidence"], reverse=True)[:top_k]

    def batch_extract(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        notes = data.get("Clinical_Notes", pd.DataFrame())
        if notes.empty:
            return pd.DataFrame()
        rows = []
        for _, note in notes.iterrows():
            text = str(note.get("Note_Text", ""))
            for hit in self.extract_diagnoses(text):
                rows.append({
                    "note_id": note.get("Note_ID"),
                    "admission_id": note.get("Admission_ID"),
                    "icd_code": hit["icd_code"],
                    "confidence": hit["confidence"],
                    "method": hit["method"],
                })
        return pd.DataFrame(rows)
