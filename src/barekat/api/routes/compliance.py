"""Compliance and privacy API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from barekat.privacy.anonymizer import (
    anonymize_patient,
    deidentify_for_export,
    erase_patient,
    get_anonymization_status,
    pseudonymize_patient,
)
from barekat.privacy.compliance import compliance_summary, get_frameworks, get_requirements
from barekat.privacy.retention import (
    get_deletion_jobs,
    get_retention_policies,
    place_legal_hold,
    purge_expired_data,
    record_consent,
    release_legal_hold,
)
from barekat.security.audit import get_access_logs, log_access
from barekat.security.rbac import require_permission, require_role, Role
from barekat.storage.database import engine

router = APIRouter()


class ConsentRequest(BaseModel):
    patient_id: str
    purpose: str
    lawful_basis: str = Field(
        default="consent",
        pattern="^(consent|contract|legal_obligation|vital_interest|public_interest|legitimate_interest|treatment|research)$",
    )
    granted: bool = True
    notes: str | None = None


class LegalHoldRequest(BaseModel):
    patient_id: str | None = None
    data_category: str | None = None
    reason: str


class DashboardAuditRequest(BaseModel):
    page: str
    action: str = "page_view"


@router.get("/frameworks")
def list_frameworks(user: dict = Depends(require_permission("read"))):
    from barekat.config.settings import get_settings
    fw = get_settings().compliance_framework
    return {"frameworks": get_frameworks(fw), "active": fw}


@router.get("/summary")
def compliance_status(user: dict = Depends(require_role(Role.ADMIN))):
    from barekat.config.settings import get_settings
    return compliance_summary(get_settings().compliance_framework)


@router.get("/requirements")
def list_requirements(user: dict = Depends(require_permission("read"))):
    from barekat.config.settings import get_settings
    return {"requirements": get_requirements(get_settings().compliance_framework)}


@router.get("/audit-logs")
def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    username: str | None = None,
    patient_id: str | None = None,
    action: str | None = None,
    user: dict = Depends(require_role(Role.ADMIN)),
):
    logs, total = get_access_logs(
        limit=limit, offset=offset, username=username,
        patient_id=patient_id, action=action,
    )
    return {"total": total, "limit": limit, "offset": offset, "data": logs}


@router.post("/dashboard-audit")
def dashboard_audit(
    body: DashboardAuditRequest,
    request: Request,
    user: dict = Depends(require_permission("read")),
):
    log_access(
        action=body.action,
        resource=f"dashboard/{body.page}",
        username=user.get("sub"),
        role=user.get("role"),
        resource_type="dashboard",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={"page": body.page},
    )
    return {"status": "logged"}


@router.get("/retention/policies")
def retention_policies(user: dict = Depends(require_role(Role.ADMIN))):
    return {"policies": get_retention_policies()}


@router.post("/retention/purge")
def trigger_retention_purge(user: dict = Depends(require_role(Role.ADMIN))):
    try:
        result = purge_expired_data(triggered_by=user.get("sub", "admin"))
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/retention/jobs")
def deletion_job_history(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_role(Role.ADMIN)),
):
    return {"jobs": get_deletion_jobs(limit)}


@router.post("/pseudonymize/{patient_id}")
def pseudonymize(patient_id: str, user: dict = Depends(require_role(Role.ADMIN))):
    try:
        return pseudonymize_patient(patient_id, actor=user.get("sub", "admin"))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/anonymize/{patient_id}")
def anonymize(patient_id: str, user: dict = Depends(require_role(Role.ADMIN))):
    try:
        return anonymize_patient(patient_id, actor=user.get("sub", "admin"))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/erasure/{patient_id}")
def erasure(patient_id: str, user: dict = Depends(require_role(Role.ADMIN))):
    try:
        return erase_patient(patient_id, actor=user.get("sub", "admin"))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/anonymization/{patient_id}")
def anonymization_status(patient_id: str, user: dict = Depends(require_role(Role.ADMIN))):
    status_row = get_anonymization_status(patient_id)
    if not status_row:
        return {"patient_id": patient_id, "status": "identified"}
    return status_row


@router.post("/consent")
def record_patient_consent(body: ConsentRequest, user: dict = Depends(require_permission("write"))):
    return record_consent(
        patient_id=body.patient_id,
        purpose=body.purpose,
        lawful_basis=body.lawful_basis,
        granted=body.granted,
        recorded_by=user.get("sub", "unknown"),
        notes=body.notes,
    )


@router.post("/legal-hold")
def create_legal_hold(body: LegalHoldRequest, user: dict = Depends(require_role(Role.ADMIN))):
    return place_legal_hold(
        patient_id=body.patient_id,
        data_category=body.data_category,
        reason=body.reason,
        placed_by=user.get("sub", "admin"),
    )


@router.post("/legal-hold/{hold_id}/release")
def release_hold(hold_id: int, user: dict = Depends(require_role(Role.ADMIN))):
    try:
        return release_legal_hold(hold_id, released_by=user.get("sub", "admin"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/security/status")
def security_status(user: dict = Depends(require_role(Role.ADMIN))):
    from barekat.config.settings import get_settings
    from barekat.security.phi_crypto import phi_encryption_active

    settings = get_settings()
    return {
        "tls_enabled": settings.tls_enabled,
        "secrets_backend": settings.secrets_backend,
        "phi_encryption_active": phi_encryption_active(),
        "mfa_required_for_admin": settings.mfa_required_for_admin,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "waf_enabled": settings.waf_enabled,
    }


@router.post("/phi/encrypt")
def encrypt_phi_fields(user: dict = Depends(require_role(Role.ADMIN))):
    from barekat.security.phi_migration import encrypt_clinical_notes
    return encrypt_clinical_notes(triggered_by=user.get("sub", "admin"))


@router.get("/export/deidentified")
def export_deidentified(
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(require_permission("export")),
):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM raw.patients ORDER BY patient_id LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()

    deidentified = deidentify_for_export([dict(r) for r in rows])
    log_access(
        action="export_deidentified",
        resource="/api/v1/compliance/export/deidentified",
        username=user.get("sub"),
        role=user.get("role"),
        resource_type="export",
        details={"record_count": len(deidentified)},
    )
    return {"count": len(deidentified), "data": deidentified}
