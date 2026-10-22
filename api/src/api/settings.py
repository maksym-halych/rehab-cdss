import os

_LOCAL_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]


def allowed_origins() -> list[str]:
    """Frontend origins: CORS allows them, and Clerk tokens must come from one of them (azp)."""
    env_origins = [
        o.strip() for o in os.getenv("CDSS_ALLOWED_ORIGINS", "").split(",") if o.strip()
    ]
    return _LOCAL_ORIGINS + env_origins


def clerk_issuer() -> str:
    """Clerk Frontend API URL, for example https://example.clerk.accounts.dev."""
    return os.getenv("CLERK_ISSUER", "").strip().rstrip("/")


def database_url() -> str:
    """SQLAlchemy URL of the Postgres database, with the async driver.

    Supabase and docker show "postgresql://..." URLs; they are changed to asyncpg here.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url
