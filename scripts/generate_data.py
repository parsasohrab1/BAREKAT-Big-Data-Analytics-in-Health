"""Generate synthetic healthcare big data."""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def generate_healthcare_big_data(n_patients: int = 5000, n_admissions: int = 15000) -> dict[str, pd.DataFrame]:
    """تولید داده‌های سنتتیک کلان سلامت برای یک سیستم بیمارستانی."""
    np.random.seed(42)

    patients_data = {
        "Patient_ID": [f"PT{str(i).zfill(5)}" for i in range(n_patients)],
        "Age": np.random.randint(18, 95, n_patients),
        "Gender": np.random.choice(["M", "F"], n_patients, p=[0.48, 0.52]),
        "Blood_Type": np.random.choice(
            ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
            n_patients,
            p=[0.30, 0.06, 0.20, 0.04, 0.08, 0.02, 0.25, 0.05],
        ),
        "BMI": np.random.normal(27, 5, n_patients),
        "Smoking_Status": np.random.choice(["Never", "Former", "Current"], n_patients, p=[0.50, 0.30, 0.20]),
        "Diabetes": np.random.binomial(1, 0.15, n_patients),
        "Hypertension": np.random.binomial(1, 0.30, n_patients),
    }
    patients_df = pd.DataFrame(patients_data)
    patients_df["BMI"] = np.clip(patients_df["BMI"], 15, 45)

    admission_types = ["Emergency", "Elective", "Urgent"]
    departments = [
        "Cardiology", "Neurology", "Oncology", "Orthopedics",
        "Internal Medicine", "Pediatrics", "Surgery", "Psychiatry",
    ]

    admissions_list = []
    for i in range(n_admissions):
        patient_id = np.random.choice(patients_df["Patient_ID"])
        patient_age = patients_df[patients_df["Patient_ID"] == patient_id]["Age"].iloc[0]

        admission_date = datetime(2023, 1, 1) + timedelta(days=int(np.random.randint(1, 730)))
        discharge_date = admission_date + timedelta(days=int(np.random.randint(1, 30)))

        dept = np.random.choice(departments)
        if patient_age < 18 and dept != "Pediatrics":
            dept = "Pediatrics"

        admissions_list.append({
            "Admission_ID": f"AD{str(i).zfill(6)}",
            "Patient_ID": patient_id,
            "Admission_Date": admission_date,
            "Discharge_Date": discharge_date,
            "Department": dept,
            "Admission_Type": np.random.choice(admission_types, p=[0.30, 0.40, 0.30]),
            "Length_of_Stay": (discharge_date - admission_date).days,
            "ICU_Required": int(np.random.binomial(1, 0.15)),
            "Readmission_Flag": np.random.binomial(1, 0.10),
            "Mortality_Flag": 0,
            "Sepsis_Flag": 0,
        })

    admissions_df = pd.DataFrame(admissions_list)

    icd_codes = ["E11.9", "I10", "I25.10", "J44.9", "N18.9", "C50.9", "C34.9", "E66.9", "F32.9", "M17.9"]
    icd_descriptions = [
        "Type 2 Diabetes", "Essential Hypertension", "Chronic Ischemic Heart Disease",
        "COPD", "Chronic Kidney Disease", "Breast Cancer", "Lung Cancer",
        "Obesity", "Major Depressive Disorder", "Osteoarthritis",
    ]

    diagnoses_list = []
    for _, admission in admissions_df.iterrows():
        n_diagnoses = np.random.randint(1, 5)
        icd_indices = np.random.choice(len(icd_codes), n_diagnoses, replace=False)
        for idx in icd_indices:
            diagnoses_list.append({
                "Diagnosis_ID": f"DG{str(len(diagnoses_list)).zfill(6)}",
                "Admission_ID": admission["Admission_ID"],
                "ICD_Code": icd_codes[idx],
                "Diagnosis_Description": icd_descriptions[idx],
                "Primary_Diagnosis": idx == icd_indices[0],
            })

    diagnoses_df = pd.DataFrame(diagnoses_list)

    medications = [
        "Metformin", "Lisinopril", "Atorvastatin", "Omeprazole", "Albuterol",
        "Losartan", "Levothyroxine", "Sertraline", "Acetaminophen", "Ibuprofen",
    ]
    dosage_units = ["mg", "g", "mcg"]

    meds_list = []
    for _, admission in admissions_df.iterrows():
        n_meds = np.random.randint(0, 5)
        for _ in range(n_meds):
            dosage_val = np.random.choice([25, 50, 100, 200, 500, 1000])
            meds_list.append({
                "Medication_ID": f"MED{str(len(meds_list)).zfill(6)}",
                "Admission_ID": admission["Admission_ID"],
                "Medication_Name": np.random.choice(medications),
                "Dosage": f"{dosage_val} {np.random.choice(dosage_units)}",
                "Frequency": np.random.choice(["Daily", "BID", "TID", "QID", "PRN"]),
                "Prescribed_Date": admission["Admission_Date"] + timedelta(days=int(np.random.randint(0, 5))),
            })

    medications_df = pd.DataFrame(meds_list) if meds_list else pd.DataFrame()

    lab_tests = ["CBC", "BMP", "LFT", "Lipid Panel", "HbA1c", "TSH", "Vitamin D"]
    lab_results_list = []

    for _, admission in admissions_df.iterrows():
        n_tests = np.random.randint(1, 6)
        for _ in range(n_tests):
            test = np.random.choice(lab_tests)
            if test == "CBC":
                value = np.random.normal(7.5, 1.0)
            elif test == "HbA1c":
                value = np.random.normal(6.0, 1.5)
            elif test == "TSH":
                value = np.random.normal(2.5, 1.5)
            else:
                value = np.random.normal(100, 30)

            lab_results_list.append({
                "Lab_ID": f"LB{str(len(lab_results_list)).zfill(6)}",
                "Admission_ID": admission["Admission_ID"],
                "Test_Name": test,
                "Result_Value": np.round(value, 2),
                "Unit": np.random.choice(["mg/dL", "IU/L", "mmol/L", "%"]),
                "Test_Date": admission["Admission_Date"] + timedelta(days=int(np.random.randint(0, 10))),
                "Abnormal_Flag": np.random.binomial(1, 0.20),
            })

    lab_results_df = pd.DataFrame(lab_results_list)

    # Outcome flags correlated with severity proxies
    for idx, row in admissions_df.iterrows():
        age = patients_df.loc[patients_df["Patient_ID"] == row["Patient_ID"], "Age"].iloc[0]
        sepsis_p = 0.03 + 0.25 * row["ICU_Required"] + (0.08 if age > 70 else 0)
        mortality_p = 0.01 + 0.20 * row["ICU_Required"] + 0.15 * sepsis_p + (0.05 if age > 80 else 0)
        admissions_df.at[idx, "Sepsis_Flag"] = int(np.random.binomial(1, min(sepsis_p, 0.6)))
        admissions_df.at[idx, "Mortality_Flag"] = int(np.random.binomial(1, min(mortality_p, 0.4)))

    # Clinical notes for NLP
    note_templates = [
        "Patient presents with {dx}. History of {comorbid}. Plan: monitor vitals, continue treatment.",
        "Progress note: {dx} suspected. Vitals stable. Labs pending. Assessment per {dept} protocol.",
        "یادداشت پزشک: بیمار با علائم {dx}. سابقه {comorbid}. نیاز به پایش علائم حیاتی.",
    ]
    comorbidities = ["hypertension", "diabetes", "COPD", "CKD", "obesity"]
    notes_list = []
    adm_diag = diagnoses_df.groupby("Admission_ID").first().reset_index()
    for _, adm in admissions_df.iterrows():
        dx_row = adm_diag[adm_diag["Admission_ID"] == adm["Admission_ID"]]
        dx = dx_row["Diagnosis_Description"].iloc[0] if not dx_row.empty else "unspecified condition"
        template = np.random.choice(note_templates)
        note_text = template.format(
            dx=dx.lower(),
            comorbid=np.random.choice(comorbidities),
            dept=adm["Department"],
        )
        notes_list.append({
            "Note_ID": f"NT{str(len(notes_list)).zfill(6)}",
            "Admission_ID": adm["Admission_ID"],
            "Note_Type": np.random.choice(["progress", "admission", "discharge"]),
            "Note_Text": note_text,
            "Authored_At": adm["Admission_Date"] + timedelta(hours=int(np.random.randint(2, 48))),
        })
    clinical_notes_df = pd.DataFrame(notes_list)

    # Vital signs time-series (every 4–8 hours during stay)
    vitals_list = []
    for _, adm in admissions_df.iterrows():
        los = max(int(adm["Length_of_Stay"]), 1)
        n_readings = min(int(np.random.randint(3, max(los * 3, 4))), 48)
        base_hr = np.random.randint(65, 95)
        sepsis = adm["Sepsis_Flag"]
        for r in range(n_readings):
            hr = base_hr + (np.random.randint(15, 35) if sepsis else np.random.randint(-10, 15))
            temp = np.random.normal(37.8 if sepsis else 37.0, 0.4)
            spo2 = np.random.randint(88, 99) if sepsis else np.random.randint(94, 100)
            vitals_list.append({
                "Vital_ID": f"VT{str(len(vitals_list)).zfill(7)}",
                "Admission_ID": adm["Admission_ID"],
                "Heart_Rate": int(np.clip(hr, 40, 160)),
                "Respiratory_Rate": int(np.random.randint(18, 28) if sepsis else np.random.randint(12, 20)),
                "Systolic_BP": int(np.random.randint(85, 110) if sepsis else np.random.randint(110, 140)),
                "Diastolic_BP": int(np.random.randint(50, 75)),
                "Temperature_C": round(float(np.clip(temp, 35.5, 40.5)), 1),
                "SpO2": int(spo2),
                "Lactate": round(float(np.random.normal(3.5, 1.0) if sepsis else np.random.normal(1.2, 0.4)), 2),
                "Recorded_At": adm["Admission_Date"] + timedelta(hours=4 * r),
            })
    vital_signs_df = pd.DataFrame(vitals_list)

    return {
        "Patients": patients_df,
        "Admissions": admissions_df,
        "Diagnoses": diagnoses_df,
        "Medications": medications_df,
        "Lab_Results": lab_results_df,
        "Clinical_Notes": clinical_notes_df,
        "Vital_Signs": vital_signs_df,
    }


def save_to_csv(data: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_map = {
        "Patients": "patients.csv",
        "Admissions": "admissions.csv",
        "Diagnoses": "diagnoses.csv",
        "Medications": "medications.csv",
        "Lab_Results": "lab_results.csv",
        "Clinical_Notes": "clinical_notes.csv",
        "Vital_Signs": "vital_signs.csv",
    }
    for table_name, filename in file_map.items():
        if table_name in data and not data[table_name].empty:
            data[table_name].to_csv(output_dir / filename, index=False)
            print(f"  Saved {filename}: {len(data[table_name])} records")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic healthcare data")
    parser.add_argument("--patients", type=int, default=1000, help="Number of patients")
    parser.add_argument("--admissions", type=int, default=3000, help="Number of admissions")
    parser.add_argument("--output", type=str, default="./data/raw", help="Output directory")
    args = parser.parse_args()

    print(f"Generating data: {args.patients} patients, {args.admissions} admissions...")
    data = generate_healthcare_big_data(args.patients, args.admissions)

    print("\nRecord counts:")
    for table_name, df in data.items():
        print(f"  {table_name}: {len(df)}")

    print(f"\nSaving to {args.output}...")
    save_to_csv(data, Path(args.output))
    print("Done.")


if __name__ == "__main__":
    main()
