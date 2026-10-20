import os

from fastapi import Header, HTTPException, Request, status

from .services.job_store import JobStore

_VALID_KEYS: frozenset[str] = frozenset(
    k.strip() for k in os.getenv("CDSS_API_KEYS", "").split(",") if k.strip()
)


async def verify_api_key(x_api_key: str = Header(default="")) -> str:
    if not _VALID_KEYS:
        # Dev mode: no keys configured → allow all
        return "dev"
    if x_api_key not in _VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_API_KEY", "message": "Invalid or missing API key"},
        )
    return x_api_key


def get_job_store(request: Request) -> JobStore:
    return request.app.state.job_store
