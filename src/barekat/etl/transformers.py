"""ETL transformers for health data normalization."""

import pandas as pd


class DataTransformer:
  """Transform raw health data into analytics-ready format."""

  COLUMN_MAP = {
    "Patients": {
      "Patient_ID": "patient_id",
      "Age": "age",
      "Gender": "gender",
      "Blood_Type": "blood_type",
      "BMI": "bmi",
      "Smoking_Status": "smoking_status",
      "Diabetes": "diabetes",
      "Hypertension": "hypertension",
    },
    "Admissions": {
      "Admission_ID": "admission_id",
      "Patient_ID": "patient_id",
      "Admission_Date": "admission_date",
      "Discharge_Date": "discharge_date",
      "Department": "department",
      "Admission_Type": "admission_type",
      "Length_of_Stay": "length_of_stay",
      "ICU_Required": "icu_required",
      "Readmission_Flag": "readmission_flag",
    },
    "Diagnoses": {
      "Diagnosis_ID": "diagnosis_id",
      "Admission_ID": "admission_id",
      "ICD_Code": "icd_code",
      "Diagnosis_Description": "diagnosis_description",
      "Primary_Diagnosis": "primary_diagnosis",
    },
    "Medications": {
      "Medication_ID": "medication_id",
      "Admission_ID": "admission_id",
      "Medication_Name": "medication_name",
      "Dosage": "dosage",
      "Frequency": "frequency",
      "Prescribed_Date": "prescribed_date",
    },
    "Lab_Results": {
      "Lab_ID": "lab_id",
      "Admission_ID": "admission_id",
      "Test_Name": "test_name",
      "Result_Value": "result_value",
      "Unit": "unit",
      "Test_Date": "test_date",
      "Abnormal_Flag": "abnormal_flag",
    },
  }

  TABLE_DB_MAP = {
    "Patients": "patients",
    "Admissions": "admissions",
    "Diagnoses": "diagnoses",
    "Medications": "medications",
    "Lab_Results": "lab_results",
  }

  def normalize_columns(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    mapping = self.COLUMN_MAP.get(table_name, {})
    return df.rename(columns=mapping)

  def clean_patients(self, df: pd.DataFrame) -> pd.DataFrame:
    df = self.normalize_columns(df, "Patients")
    df["bmi"] = df["bmi"].clip(15, 45)
    df["diabetes"] = df["diabetes"].astype(bool)
    df["hypertension"] = df["hypertension"].astype(bool)
    return df

  def clean_admissions(self, df: pd.DataFrame) -> pd.DataFrame:
    df = self.normalize_columns(df, "Admissions")
    for col in ("admission_date", "discharge_date"):
      if col in df.columns:
        df[col] = pd.to_datetime(df[col])
    df["icu_required"] = df["icu_required"].astype(bool)
    df["readmission_flag"] = df["readmission_flag"].astype(bool)
    return df

  def clean_diagnoses(self, df: pd.DataFrame) -> pd.DataFrame:
    df = self.normalize_columns(df, "Diagnoses")
    df["primary_diagnosis"] = df["primary_diagnosis"].astype(bool)
    return df

  def clean_medications(self, df: pd.DataFrame) -> pd.DataFrame:
    df = self.normalize_columns(df, "Medications")
    if "prescribed_date" in df.columns:
      df["prescribed_date"] = pd.to_datetime(df["prescribed_date"])
    return df

  def clean_lab_results(self, df: pd.DataFrame) -> pd.DataFrame:
    df = self.normalize_columns(df, "Lab_Results")
    if "test_date" in df.columns:
      df["test_date"] = pd.to_datetime(df["test_date"])
    df["abnormal_flag"] = df["abnormal_flag"].astype(bool)
    return df

  def build_admission_summary(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "Admissions" not in data or data["Admissions"].empty:
      return pd.DataFrame()

    admissions = self.clean_admissions(data["Admissions"].copy())
    summary = admissions[["admission_id", "patient_id", "department", "length_of_stay"]].copy()

    if "Diagnoses" in data and not data["Diagnoses"].empty:
      diagnoses = self.normalize_columns(data["Diagnoses"].copy(), "Diagnoses")
      diag_counts = diagnoses.groupby("admission_id").size().reset_index(name="diagnosis_count")
      summary = summary.merge(diag_counts, on="admission_id", how="left")
    else:
      summary["diagnosis_count"] = 0

    if "Medications" in data and not data["Medications"].empty:
      medications = self.normalize_columns(data["Medications"].copy(), "Medications")
      med_counts = medications.groupby("admission_id").size().reset_index(name="medication_count")
      summary = summary.merge(med_counts, on="admission_id", how="left")
    else:
      summary["medication_count"] = 0

    if "Lab_Results" in data and not data["Lab_Results"].empty:
      lab_results = self.normalize_columns(data["Lab_Results"].copy(), "Lab_Results")
      lab_counts = lab_results.groupby("admission_id").size().reset_index(name="lab_test_count")
      summary = summary.merge(lab_counts, on="admission_id", how="left")
    else:
      summary["lab_test_count"] = 0

    return summary.fillna(0)
