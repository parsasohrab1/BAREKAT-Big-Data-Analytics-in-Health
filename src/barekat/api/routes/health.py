"""Health check endpoints."""

from fastapi import APIRouter

from barekat import __version__

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "healthy", "version": __version__, "service": "barekat-api"}


@router.get("/ready")
def readiness_check():
    try:
        from barekat.storage.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        return {"status": "not_ready", "database": str(exc)}
