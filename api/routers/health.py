from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
