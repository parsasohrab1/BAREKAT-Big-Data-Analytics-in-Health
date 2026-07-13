"""ML model management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from barekat.ml.data_loader import load_training_data
from barekat.ml.los import LOSPredictor
from barekat.ml.mortality_sepsis import EarlyWarningPredictor
from barekat.ml.nlp_notes import ClinicalNotesNLP
from barekat.ml.pipeline import MLPipeline
from barekat.ml.registry import get_active_model, list_models
from barekat.ml.thresholds import get_threshold, list_thresholds, set_threshold
from barekat.ml.vitals_monitor import VitalsMonitor
from barekat.security.rbac import require_permission, require_role, Role

router = APIRouter()


class ThresholdUpdate(BaseModel):
    risk_threshold: float = Field(..., ge=0, le=1)


class NoteExtractRequest(BaseModel):
    note_text: str = Field(..., min_length=10)
    top_k: int = Field(3, ge=1, le=10)


@router.post("/train")
def train_models(user: dict = Depends(require_role(Role.ADMIN, Role.RESEARCHER))):
    ml = MLPipeline()
    results = ml.run_all()
    return {"status": "completed", "results": results}


@router.post("/retrain")
def retrain_models(user: dict = Depends(require_role(Role.ADMIN))):
    ml = MLPipeline()
    results = ml.retrain()
    return {"status": "completed", "results": results}


@router.get("/models")
def get_models(user: dict = Depends(require_permission("read"))):
    return {"models": list_models(limit=50)}


@router.get("/models/{model_name}")
def get_model_detail(model_name: str, user: dict = Depends(require_permission("read"))):
    active = get_active_model(model_name)
    history = list_models(model_name=model_name, limit=10)
    if not active and not history:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"active": active, "history": history}


@router.get("/models/{model_name}/metrics")
def get_model_metrics(model_name: str, user: dict = Depends(require_permission("run_analytics"))):
    active = get_active_model(model_name)
    if not active:
        raise HTTPException(status_code=404, detail="No active model version")
    return {
        "model_name": model_name,
        "version": active.get("version"),
        "metrics": active.get("metrics"),
        "calibration": active.get("calibration"),
        "trained_at": active.get("trained_at"),
        "samples": active.get("samples"),
    }


@router.get("/predict/los")
def predict_los(limit: int = Query(50, ge=1, le=500), user: dict = Depends(require_permission("run_analytics"))):
    data = load_training_data()
    predictor = LOSPredictor()
    preds = predictor.predict(data).head(limit)
    return {"predictions": preds.to_dict(orient="records"), "use_case": "bed_planning"}


@router.get("/predict/early-warning")
def predict_early_warning(
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_permission("run_analytics")),
):
    data = load_training_data()
    predictor = EarlyWarningPredictor()
    risks = predictor.predict_risks(data).head(limit)
    return {
        "predictions": risks.to_dict(orient="records"),
        "use_case": "mortality_sepsis_early_warning",
    }


@router.post("/nlp/extract-diagnoses")
def extract_diagnoses_from_note(body: NoteExtractRequest, user: dict = Depends(require_permission("run_analytics"))):
    nlp = ClinicalNotesNLP()
    nlp.load()
    diagnoses = nlp.extract_diagnoses(body.note_text, top_k=body.top_k)
    return {"diagnoses": diagnoses, "use_case": "clinical_note_nlp"}


@router.get("/vitals/monitor/{admission_id}")
def monitor_vitals(admission_id: str, user: dict = Depends(require_permission("read"))):
    data = load_training_data()
    vitals = data.get("Vital_Signs")
    if vitals is None or vitals.empty:
        raise HTTPException(status_code=404, detail="No vital signs data available")
    monitor = VitalsMonitor()
    monitor.load()
    result = monitor.monitor_timeseries(vitals, admission_id)
    if result.get("status") == "no_data":
        raise HTTPException(status_code=404, detail=f"No vitals for admission {admission_id}")
    return {"monitoring": result, "use_case": "realtime_vitals"}


@router.get("/vitals/scores")
def vitals_deterioration_scores(
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_permission("run_analytics")),
):
    data = load_training_data()
    monitor = VitalsMonitor()
    scores = monitor.score_admissions(data).head(limit)
    return {"scores": scores.to_dict(orient="records")}


@router.get("/thresholds")
def get_thresholds(user: dict = Depends(require_permission("read"))):
    return {"thresholds": list_thresholds()}


@router.get("/thresholds/{department}")
def get_department_threshold(department: str, user: dict = Depends(require_permission("read"))):
    return {"department": department, "risk_threshold": get_threshold(department)}


@router.put("/thresholds/{department}")
def update_department_threshold(
    department: str,
    body: ThresholdUpdate,
    user: dict = Depends(require_role(Role.ADMIN, Role.CLINICIAN)),
):
    set_threshold(department, body.risk_threshold)
    return {"department": department, "risk_threshold": body.risk_threshold, "status": "updated"}


@router.get("/predict/readmission/explain/{admission_id}")
def explain_readmission(
    admission_id: str,
    user: dict = Depends(require_permission("view_phi")),
):
    """SHAP explanation — why is this patient high risk?"""
    from barekat.ml.data_loader import load_training_data
    from barekat.ml.explainability import ReadmissionExplainer

    data = load_training_data()
    explainer = ReadmissionExplainer()
    try:
        return explainer.explain_admission(data, admission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/predict/readmission/report/{admission_id}")
def readmission_clinical_report(
    admission_id: str,
    format: str = Query("html", pattern="^(html|json)$"),
    user: dict = Depends(require_permission("view_phi")),
):
    """Printable clinical report for readmission risk."""
    from fastapi.responses import HTMLResponse

    from barekat.ml.clinical_report import generate_clinical_report_html
    from barekat.ml.data_loader import load_training_data
    from barekat.ml.explainability import ReadmissionExplainer

    data = load_training_data()
    explainer = ReadmissionExplainer()
    try:
        explanation = explainer.explain_admission(data, admission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if format == "json":
        html = generate_clinical_report_html(explanation)
        return {"explanation": explanation, "html": html}

    html = generate_clinical_report_html(explanation)
    return HTMLResponse(content=html)

