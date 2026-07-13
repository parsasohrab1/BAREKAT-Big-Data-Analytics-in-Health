"""PACS connectivity — DICOM DIMSE (C-ECHO, C-FIND) and Orthanc REST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from barekat.config.settings import get_settings
from barekat.imaging.metadata import DICOMMetadata


@dataclass
class PACSConnection:
    host: str
    port: int
    called_ae: str
    calling_ae: str
    orthanc_url: str | None = None


def get_pacs_connection() -> PACSConnection:
    settings = get_settings()
    return PACSConnection(
        host=settings.pacs_host,
        port=settings.pacs_port,
        called_ae=settings.pacs_ae_title,
        calling_ae=settings.pacs_calling_ae,
        orthanc_url=settings.pacs_orthanc_url or None,
    )


def echo_pacs(conn: PACSConnection | None = None) -> dict[str, Any]:
    """C-ECHO verification to PACS."""
    conn = conn or get_pacs_connection()
    try:
        from pynetdicom import AE
        from pynetdicom.sop_class import Verification

        ae = AE(ae_title=conn.calling_ae)
        ae.add_requested_context(Verification)
        assoc = ae.associate(conn.host, conn.port, ae_title=conn.called_ae)
        if assoc.is_established:
            status = assoc.send_c_echo()
            assoc.release()
            return {
                "status": "connected",
                "host": conn.host,
                "port": conn.port,
                "called_ae": conn.called_ae,
                "c_echo_status": hex(status.Status) if status else None,
            }
        return {"status": "rejected", "host": conn.host, "port": conn.port}
    except ImportError:
        return {"status": "error", "message": "pynetdicom not installed"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "host": conn.host, "port": conn.port}


def find_studies(
    *,
    patient_id: str | None = None,
    study_date: str | None = None,
    modality: str | None = None,
    conn: PACSConnection | None = None,
) -> list[DICOMMetadata]:
    """C-FIND at STUDY level."""
    conn = conn or get_pacs_connection()
    if conn.orthanc_url:
        return _find_studies_orthanc(conn, patient_id=patient_id, modality=modality)

    try:
        from pynetdicom import AE
        from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind

        ae = AE(ae_title=conn.calling_ae)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
        assoc = ae.associate(conn.host, conn.port, ae_title=conn.called_ae)
        if not assoc.is_established:
            return []

        query = {
            "QueryRetrieveLevel": "STUDY",
            "PatientID": patient_id or "",
            "StudyDate": study_date or "",
            "ModalitiesInStudy": modality or "",
            "StudyInstanceUID": "",
            "StudyDescription": "",
            "BodyPartExamined": "",
            "NumberOfStudyRelatedInstances": "",
        }
        results: list[DICOMMetadata] = []
        for status, identifier in assoc.send_c_find(query):
            if status and status.Status in (0xFF00, 0xFF01) and identifier:
                results.append(DICOMMetadata(
                    patient_id=str(getattr(identifier, "PatientID", "")),
                    study_uid=str(getattr(identifier, "StudyInstanceUID", "")),
                    modality=str(getattr(identifier, "ModalitiesInStudy", "")),
                    study_date=str(getattr(identifier, "StudyDate", "")),
                    body_part=str(getattr(identifier, "BodyPartExamined", "")),
                    study_description=str(getattr(identifier, "StudyDescription", "")),
                    pacs_source=f"{conn.called_ae}@{conn.host}",
                ))
        assoc.release()
        return results
    except ImportError:
        return []
    except Exception:
        return []


def _find_studies_orthanc(
    conn: PACSConnection,
    *,
    patient_id: str | None,
    modality: str | None,
) -> list[DICOMMetadata]:
    base = conn.orthanc_url.rstrip("/")
    params: dict[str, str] = {}
    if patient_id:
        params["PatientID"] = patient_id
    if modality:
        params["Modality"] = modality

    try:
        with httpx.Client(base_url=base, timeout=30.0) as client:
            response = client.get("/studies", params=params)
            response.raise_for_status()
            study_ids = response.json()
            results = []
            for sid in study_ids[:50]:
                meta_resp = client.get(f"/studies/{sid}")
                meta_resp.raise_for_status()
                meta = meta_resp.json()
                main_tags = meta.get("PatientMainDicomTags", {})
                study_tags = meta.get("MainDicomTags", {})
                results.append(DICOMMetadata(
                    patient_id=main_tags.get("PatientID", ""),
                    study_uid=study_tags.get("StudyInstanceUID", sid),
                    modality=",".join(meta.get("Modalities", [])),
                    study_date=study_tags.get("StudyDate", ""),
                    body_part=study_tags.get("BodyPartExamined", ""),
                    study_description=study_tags.get("StudyDescription", ""),
                    pacs_source=f"orthanc:{base}",
                ))
            return results
    except Exception:
        return []


def retrieve_study_instances(study_uid: str, dest_dir, conn: PACSConnection | None = None) -> list[str]:
    """Download DICOM instances — Orthanc REST or local noop."""
    from pathlib import Path

    conn = conn or get_pacs_connection()
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    if not conn.orthanc_url:
        return []

    base = conn.orthanc_url.rstrip("/")
    downloaded: list[str] = []
    try:
        with httpx.Client(base_url=base, timeout=60.0) as client:
            studies = client.get("/studies", params={"StudyInstanceUID": study_uid}).json()
            if not studies:
                return []
            orthanc_id = studies[0]
            instances = client.get(f"/studies/{orthanc_id}/instances").json()
            for inst_id in instances:
                dcm = client.get(f"/instances/{inst_id}/file").content
                path = dest / f"{inst_id}.dcm"
                path.write_bytes(dcm)
                downloaded.append(str(path))
    except Exception:
        return []
    return downloaded
