import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health, files, jobs, reports, patients
from .routers import config as cfg_router
from .services.job_store import JobStore

_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
_env_origins = [
    o.strip()
    for o in os.getenv("CDSS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]
_ALL_ORIGINS = _CORS_ORIGINS + _env_origins


def _configure_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALL_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "X-API-Key", "Content-Type"],
        max_age=600,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_store = JobStore()
    app.state.job_store = job_store
    yield
    await job_store.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rehab CDSS API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    _configure_cors(app)
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(files.router, prefix="/api/v1", tags=["Files"])
    app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
    app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])
    app.include_router(patients.router, prefix="/api/v1", tags=["Patients"])
    app.include_router(cfg_router.router, prefix="/api/v1", tags=["Config"])
    return app


def launch_api() -> None:
    import uvicorn
    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


def launch_all() -> None:
    """Start both Gradio (port 7860) and FastAPI (port 8000) in one process."""
    from ui.app import launch_app as _launch_gradio

    api_thread = threading.Thread(target=launch_api, daemon=True)
    api_thread.start()
    _launch_gradio()
