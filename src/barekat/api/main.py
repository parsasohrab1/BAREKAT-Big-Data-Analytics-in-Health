"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from barekat import __version__
from barekat.api.routes import analytics, auth, health, patients


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="BAREKAT Health Analytics API",
    description="پلتفرم تحلیل کلان‌داده سلامت - API",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
