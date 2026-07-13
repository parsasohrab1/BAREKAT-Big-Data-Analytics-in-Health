"""Medical imaging API — PACS, DICOM ingest, viewer, CAD stub."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from barekat.imaging.cad import CADAnalyzer
from barekat.imaging.pacs_client import echo_pacs, find_studies, get_pacs_connection, retrieve_study_instances
from barekat.imaging.store import (
    get_study_by_uid,
    get_thumbnail_bytes,
    get_viewer_file_path,
    ingest_dicom_file,
    ingest_directory,
    list_studies,
)
from barekat.imaging.thumbnail import render_png_bytes
from barekat.security.rbac import require_permission, require_role, Role

router = APIRouter()


class PACSQueryRequest(BaseModel):
    patient_id: str | None = None
    study_date: str | None = None
    modality: str | None = Field(None, description="CT, MR, CR, DX, ...")


class PACSRetrieveRequest(BaseModel):
    study_uid: str
    ingest: bool = True


@router.get("/pacs/config")
def pacs_config(user: dict = Depends(require_permission("read"))):
    conn = get_pacs_connection()
    return {
        "host": conn.host,
        "port": conn.port,
        "called_ae": conn.called_ae,
        "calling_ae": conn.calling_ae,
        "orthanc_url": conn.orthanc_url,
    }


@router.post("/pacs/echo")
def pacs_echo(user: dict = Depends(require_role(Role.ADMIN, Role.CLINICIAN))):
    return echo_pacs()


@router.post("/pacs/query")
def pacs_query(body: PACSQueryRequest, user: dict = Depends(require_permission("view_phi"))):
    studies = find_studies(
        patient_id=body.patient_id,
        study_date=body.study_date,
        modality=body.modality,
    )
    return {"count": len(studies), "studies": [s.to_dict() for s in studies]}


@router.post("/pacs/retrieve")
def pacs_retrieve(body: PACSRetrieveRequest, user: dict = Depends(require_role(Role.ADMIN, Role.CLINICIAN))):
    with tempfile.TemporaryDirectory() as tmp:
        files = retrieve_study_instances(body.study_uid, tmp)
        if not files:
            raise HTTPException(status_code=404, detail="Study not found or PACS retrieve unavailable (use Orthanc URL)")

        ingested = []
        if body.ingest:
            for f in files:
                meta = ingest_dicom_file(Path(f), pacs_source="pacs")
                if meta:
                    ingested.append(meta.to_dict())

        return {"study_uid": body.study_uid, "files_retrieved": len(files), "ingested": ingested}


@router.post("/upload")
async def upload_dicom(
    file: UploadFile = File(...),
    user: dict = Depends(require_role(Role.ADMIN, Role.CLINICIAN)),
):
    suffix = ".dcm" if not file.filename.endswith(".dcm") else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    meta = ingest_dicom_file(tmp_path, pacs_source="upload")
    tmp_path.unlink(missing_ok=True)
    if not meta:
        raise HTTPException(status_code=400, detail="Invalid DICOM file")
    return {"status": "ingested", "study": meta.to_dict()}


@router.post("/ingest/local")
def ingest_local_directory(
    directory: str = Query(..., description="Path to directory with .dcm files"),
    user: dict = Depends(require_role(Role.ADMIN)),
):
    path = Path(directory)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    results = ingest_directory(path, pacs_source="local")
    return {"ingested": len(results), "studies": [r.to_dict() for r in results]}


@router.get("/studies")
def get_studies(
    limit: int = Query(50, ge=1, le=200),
    modality: str | None = None,
    user: dict = Depends(require_permission("view_phi")),
):
    df = list_studies(limit=limit, modality=modality)
    return {"studies": df.to_dict(orient="records")}


@router.get("/studies/{study_uid}")
def get_study(study_uid: str, user: dict = Depends(require_permission("view_phi"))):
    study = get_study_by_uid(study_uid)
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    return study


@router.get("/studies/{study_uid}/thumbnail")
def study_thumbnail(study_uid: str, user: dict = Depends(require_permission("view_phi"))):
    data = get_thumbnail_bytes(study_uid)
    if not data:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return Response(content=data, media_type="image/png")


@router.get("/studies/{study_uid}/viewer")
def study_viewer_image(
    study_uid: str,
    window: float | None = None,
    level: float | None = None,
    user: dict = Depends(require_permission("view_phi")),
):
    file_path = get_viewer_file_path(study_uid)
    if not file_path:
        raise HTTPException(status_code=404, detail="DICOM instance not available")
    try:
        png = render_png_bytes(file_path, window=window, level=level)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Render failed: {exc}") from exc
    return Response(content=png, media_type="image/png")


@router.get("/studies/{study_uid}/cad")
def study_cad_analysis(study_uid: str, user: dict = Depends(require_permission("run_analytics"))):
    study = get_study_by_uid(study_uid)
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    analyzer = CADAnalyzer()
    return analyzer.analyze(study_uid, modality=study.get("modality", ""))
