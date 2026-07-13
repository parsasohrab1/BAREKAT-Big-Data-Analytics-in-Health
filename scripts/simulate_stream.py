"""Simulate HL7/FHIR streaming events into Kafka via ingest API."""

from __future__ import annotations

import argparse
import time

import httpx

SAMPLE_HL7_VITALS = """MSH|^~\\&|MONITOR|ICU|BAREKAT|HOSP|20260713090000||ORU^R01|MSG{idx}|P|2.5
PID|1||PT{patient}^^^HOSP||DOE^JOHN
OBR|1|||VITALS^VITAL SIGNS
OBX|1|NM|8867-4^Heart Rate||{hr}|bpm
OBX|2|NM|2708-6^SpO2||{spo2}|%
OBX|3|NM|8480-6^Systolic BP||{sbp}|mmHg
OBX|4|NM|2524-7^Lactate||{lactate}|mmol/L"""

SAMPLE_FHIR_OBS = {
    "resourceType": "Observation",
    "id": "obs-{idx}",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
    "subject": {"reference": "Patient/{patient}"},
    "valueQuantity": {"value": 0, "unit": "beats/minute"},
}


def main():
    parser = argparse.ArgumentParser(description="Simulate HL7/FHIR stream ingest")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--token", required=True, help="JWT access token")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--format", choices=["hl7", "fhir", "both"], default="both")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"}
    client = httpx.Client(base_url=args.api, headers=headers, timeout=10.0)

    scenarios = [
        {"hr": 85, "spo2": 97, "sbp": 120, "lactate": 1.2},
        {"hr": 125, "spo2": 93, "sbp": 105, "lactate": 2.5},
        {"hr": 145, "spo2": 88, "sbp": 85, "lactate": 4.8},
    ]

    for i in range(args.count):
        patient = f"{i % 50:05d}"
        vitals = scenarios[i % len(scenarios)]
        if args.format in ("hl7", "both"):
            hl7 = SAMPLE_HL7_VITALS.format(idx=i, patient=patient, **vitals)
            resp = client.post("/api/v1/ingest/hl7", json={"message": hl7})
            print(f"[HL7] {resp.status_code} {resp.json()}")

        if args.format in ("fhir", "both"):
            obs = SAMPLE_FHIR_OBS.copy()
            obs["id"] = f"obs-{i}"
            obs["subject"] = {"reference": f"Patient/{patient}"}
            obs["valueQuantity"] = {"value": vitals["hr"], "unit": "beats/minute"}
            resp = client.post("/api/v1/ingest/fhir", json={"resource": obs})
            print(f"[FHIR] {resp.status_code} {resp.json()}")

        time.sleep(args.interval)

    client.close()
    print("Done.")


if __name__ == "__main__":
    main()
