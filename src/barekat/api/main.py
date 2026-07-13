"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from barekat import __version__
from barekat.api.middleware.audit import AuditMiddleware
from barekat.api.middleware.prometheus import PrometheusMiddleware
from barekat.api.middleware.rate_limit import RateLimitMiddleware
from barekat.api.middleware.security import SecurityMiddleware
from barekat.api.middleware.tenant import TenantMiddleware
from barekat.api.routes import (
    analytics, auth, compliance, fhir, health, imaging, ingest, lake, ml,
    observability, patients, reports, stream, tenants,
)
from barekat.config.settings import get_settings
from barekat.observability.exporter import refresh_metrics_from_db
from barekat.streaming.redis_listener import redis_subscriber


@asynccontextmanager
async def lifespan(app: FastAPI):
    from barekat.config.settings import get_settings
    from barekat.observability.metrics import SERVICE_INFO

    settings = get_settings()
    SERVICE_INFO.info({"version": __version__, "env": settings.barekat_env})

    if settings.db_auto_migrate:
        try:
            from barekat.db.migrate import apply_migrations

            applied = apply_migrations()
            if applied:
                print(f"Applied migrations: {', '.join(applied)}")
        except Exception as exc:
            print(f"Database migration skipped/failed: {exc}")

    loop = asyncio.get_running_loop()
    try:
        redis_subscriber.start(loop)
    except Exception as exc:
        print(f"Redis alert subscriber not started: {exc}")

    refresh_task = None
    if settings.observability_enabled:
        async def _metrics_loop():
            while True:
                await asyncio.sleep(settings.metrics_refresh_seconds)
                try:
                    refresh_metrics_from_db()
                except Exception:
                    pass

        refresh_task = asyncio.create_task(_metrics_loop())

    yield

    if refresh_task:
        refresh_task.cancel()
    redis_subscriber.stop()


app = FastAPI(
    title="BAREKAT Health Analytics API",
    description="پلتفرم تحلیل کلان‌داده سلامت - API",
    version=__version__,
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityMiddleware)
if get_settings().observability_enabled:
    app.add_middleware(PrometheusMiddleware)

app.include_router(health.router, tags=["Health"])


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics_root():
    refresh_metrics_from_db()
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(ml.router, prefix="/api/v1/ml", tags=["Machine Learning"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["Streaming Ingest"])
app.include_router(fhir.router, prefix="/api/v1/fhir", tags=["FHIR Interoperability"])
app.include_router(imaging.router, prefix="/api/v1/imaging", tags=["Medical Imaging"])
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance & Privacy"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Multi-Tenancy"])
app.include_router(stream.router, prefix="/api/v1/stream", tags=["Real-time Stream"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports & Notifications"])
app.include_router(lake.router, prefix="/api/v1/lake", tags=["Data Lake"])
app.include_router(observability.router, prefix="/api/v1/observability", tags=["Observability"])

_MOBILE_DIR = Path(__file__).resolve().parents[3] / "frontend" / "mobile"
if _MOBILE_DIR.is_dir():
    app.mount("/mobile", StaticFiles(directory=str(_MOBILE_DIR), html=True), name="mobile-pwa")
