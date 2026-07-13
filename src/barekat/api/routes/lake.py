"""Data Lake API — medallion status and job triggers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from barekat.lake.pipeline import LakePipeline
from barekat.lake import catalog
from barekat.security.rbac import require_permission, require_role, Role

router = APIRouter()


@router.get("/status")
def lake_status(user: dict = Depends(require_permission("read"))):
    return LakePipeline().status()


@router.get("/tables")
def list_lake_tables(
    layer: str | None = Query(None, pattern="^(bronze|silver|gold)$"),
    user: dict = Depends(require_permission("read")),
):
    return {"tables": catalog.list_tables(layer)}


@router.get("/jobs")
def list_lake_jobs(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_role(Role.ADMIN, Role.RESEARCHER)),
):
    return {"jobs": catalog.recent_jobs(limit=limit)}


@router.post("/run/full")
def run_lake_full(user: dict = Depends(require_role(Role.ADMIN))):
    from barekat.worker.tasks import run_lake_batch

    task = run_lake_batch.delay(mode="full")
    return {"status": "queued", "task_id": task.id}


@router.post("/run/silver")
def run_lake_silver(user: dict = Depends(require_role(Role.ADMIN, Role.RESEARCHER))):
    from barekat.lake.batch.bronze_to_silver import run_bronze_to_silver

    return run_bronze_to_silver()


@router.post("/run/gold")
def run_lake_gold(user: dict = Depends(require_role(Role.ADMIN, Role.RESEARCHER))):
    from barekat.lake.batch.silver_to_gold import run_silver_to_gold

    return run_silver_to_gold()
