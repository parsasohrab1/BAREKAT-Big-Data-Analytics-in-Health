import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_healthcare_big_data(n_patients=5000, n_admissions=15000):
    """
    تولید داده‌های سنتتیک کلان سلامت برای یک سیستم بیمارستانی
    
    پارامترها:
    n_patients: تعداد بیماران
    n_admissions: تعداد بستری‌ها
    
    بازگشت: دیکشنری از دیتافریم‌ها (جداول مختلف)
    """
    np.random.seed(42)
    
    # 1. تولید جدول بیماران
    patients_data = {
        'Patient_ID': [f'PT{str(i).zfill(5)}' for i in range(n_patients)],
        'Age': np.random.randint(18, 95, n_patients),
        'Gender': np.random.choice(['M', 'F'], n_patients, p=[0.48, 0.52]),
        'Blood_Type': np.random.choice(['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'], 
                                       n_patients, p=[0.30, 0.06, 0.20, 0.04, 0.08, 0.02, 0.25, 0.05]),
        'BMI': np.random.normal(27, 5, n_patients),
        'Smoking_Status': np.random.choice(['Never', 'Former', 'Current'], n_patients, p=[0.50, 0.30, 0.20]),
        'Diabetes': np.random.binomial(1, 0.15, n_patients),
        'Hypertension': np.random.binomial(1, 0.30, n_patients)
    }
    patients_df = pd.DataFrame(patients_data)
    patients_df['BMI'] = np.clip(patients_df['BMI'], 15, 45)
    
    # 2. تولید جدول بستری‌ها
    admission_types = ['Emergency', 'Elective', 'Urgent']
    departments = ['Cardiology', 'Neurology', 'Oncology', 'Orthopedics', 'Internal Medicine', 
                   'Pediatrics', 'Surgery', 'Psychiatry']
    
    admissions_list = []
    for i in range(n_admissions):
        patient_id = np.random.choice(patients_df['Patient_ID'])
        patient_age = patients_df[patients_df['Patient_ID'] == patient_id]['Age'].iloc[0]
        
        admission_date = datetime(2023, 1, 1) + timedelta(days=np.random.randint(1, 730))
        discharge_date = admission_date + timedelta(days=np.random.randint(1, 30))
        
        # تشخیص‌ها بر اساس سن و بخش
        dept = np.random.choice(departments)
        if patient_age < 18 and dept != 'Pediatrics':
            dept = 'Pediatrics'
            
        admissions_list.append({
            'Admission_ID': f'AD{str(i).zfill(6)}',
            'Patient_ID': patient_id,
            'Admission_Date': admission_date,
            'Discharge_Date': discharge_date,
            'Department': dept,
            'Admission_Type': np.random.choice(admission_types, p=[0.30, 0.40, 0.30]),
            'Length_of_Stay': (discharge_date - admission_date).days,
            'ICU_Required': np.random.binomial(1, 0.15),
            'Readmission_Flag': np.random.binomial(1, 0.10)
        })
    
    admissions_df = pd.DataFrame(admissions_list)
    
    # 3. تولید جدول تشخیص‌ها (ICD-10 کدها)
    icd_codes = ['E11.9', 'I10', 'I25.10', 'J44.9', 'N18.9', 'C50.9', 'C34.9', 'E66.9', 'F32.9', 'M17.9']
    icd_descriptions = ['Type 2 Diabetes', 'Essential Hypertension', 'Chronic Ischemic Heart Disease',
                        'COPD', 'Chronic Kidney Disease', 'Breast Cancer', 'Lung Cancer', 
                        'Obesity', 'Major Depressive Disorder', 'Osteoarthritis']
    
    diagnoses_list = []
    for _, admission in admissions_df.iterrows():
        # هر بستری بین 1 تا 4 تشخیص دارد
        n_diagnoses = np.random.randint(1, 5)
        icd_indices = np.random.choice(len(icd_codes), n_diagnoses, replace=False)
        for idx in icd_indices:
            diagnoses_list.append({
                'Diagnosis_ID': f'DG{str(len(diagnoses_list)).zfill(6)}',
                'Admission_ID': admission['Admission_ID'],
                'ICD_Code': icd_codes[idx],
                'Diagnosis_Description': icd_descriptions[idx],
                'Primary_Diagnosis': idx == icd_indices[0]  # اولین تشخیص به عنوان تشخیص اصلی
            })
    
    diagnoses_df = pd.DataFrame(diagnoses_list)
    
    # 4. تولید جدول داروها
    medications = ['Metformin', 'Lisinopril', 'Atorvastatin', 'Omeprazole', 'Albuterol', 
                   'Losartan', 'Levothyroxine', 'Sertraline', 'Acetaminophen', 'Ibuprofen']
    dosage_units = ['mg', 'g', 'mcg']
    
    meds_list = []
    for _, admission in admissions_df.iterrows():
        # هر بستری بین 0 تا 4 دارو دارد
        n_meds = np.random.randint(0, 5)
        if n_meds > 0:
            for _ in range(n_meds):
                med = np.random.choice(medications)
                dosage_val = np.random.choice([25, 50, 100, 200, 500, 1000])
                dosage_unit = np.random.choice(dosage_units)
                meds_list.append({
                    'Medication_ID': f'MED{str(len(meds_list)).zfill(6)}',
                    'Admission_ID': admission['Admission_ID'],
                    'Medication_Name': med,
                    'Dosage': f"{dosage_val} {dosage_unit}",
                    'Frequency': np.random.choice(['Daily', 'BID', 'TID', 'QID', 'PRN']),
                    'Prescribed_Date': admission['Admission_Date'] + timedelta(days=np.random.randint(0, 5))
                })
    
    medications_df = pd.DataFrame(meds_list) if meds_list else pd.DataFrame()
    
    # 5. تولید جدول نتایج آزمایشگاهی
    lab_tests = ['CBC', 'BMP', 'LFT', 'Lipid Panel', 'HbA1c', 'TSH', 'Vitamin D']
    lab_results_list = []
    
    for _, admission in admissions_df.iterrows():
        n_tests = np.random.randint(1, 6)
        for _ in range(n_tests):
            test = np.random.choice(lab_tests)
            # مقادیر نرمال شبیه‌سازی‌شده
            if test == 'CBC':
                value = np.random.normal(7.5, 1.0)  # WBC x 10^3/uL
            elif test == 'HbA1c':
                value = np.random.normal(6.0, 1.5)  # %
            elif test == 'TSH':
                value = np.random.normal(2.5, 1.5)  # mIU/L
            else:
                value = np.random.normal(100, 30)
            
            lab_results_list.append({
                'Lab_ID': f'LB{str(len(lab_results_list)).zfill(6)}',
                'Admission_ID': admission['Admission_ID'],
                'Test_Name': test,
                'Result_Value': np.round(value, 2),
                'Unit': np.random.choice(['mg/dL', 'IU/L', 'mmol/L', '%']),
                'Test_Date': admission['Admission_Date'] + timedelta(days=np.random.randint(0, 10)),
                'Abnormal_Flag': np.random.binomial(1, 0.20)
            })
    
    lab_results_df = pd.DataFrame(lab_results_list)
    
    return {
        'Patients': patients_df,
        'Admissions': admissions_df,
        'Diagnoses': diagnoses_df,
        'Medications': medications_df,
        'Lab_Results': lab_results_df
    }

# تولید داده‌ها
healthcare_data = generate_healthcare_big_data(n_patients=1000, n_admissions=3000)

print("تعداد رکوردها:")
for table_name, df in healthcare_data.items():
    print(f"{table_name}: {len(df)}")

print("\nنمونه از جدول بیماران:")
print(healthcare_data['Patients'].head())
