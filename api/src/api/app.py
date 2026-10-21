from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import demo, health, files, jobs, reports, patients
from .routers import config as cfg_router
from .db import create_engine
from .services.job_store import JobStore
from .settings import allowed_origins, clerk_issuer, database_url


def _configure_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        # Downloads read the file name from it
        expose_headers=["Content-Disposition"],
        max_age=600,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_store = JobStore(create_engine(database_url()))
    await job_store.fail_unfinished()
    app.state.job_store = job_store
    yield
    await job_store.shutdown()


def create_app() -> FastAPI:
    # Every route except health needs a Clerk token, so the API does not start without Clerk
    if not clerk_issuer():
        raise RuntimeError("CLERK_ISSUER is not set. See api/.env.example")
    # Jobs are kept in Postgres (Supabase on the servers)
    if not database_url():
        raise RuntimeError("DATABASE_URL is not set. See api/.env.example")
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
    app.include_router(demo.router, prefix="/api/v1", tags=["Demo"])
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

