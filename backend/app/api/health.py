from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.errors import ErrorResponse
from app.db.session import database_is_ready

router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/live", response_model=HealthResponse, summary="Check API process liveness")
async def live() -> HealthResponse:
    """Return success when the API process can answer requests; no dependency checks."""
    return HealthResponse()


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Startup or PostgreSQL is unavailable."}
    },
    summary="Check API readiness",
)
def ready(available: Annotated[bool, Depends(database_is_ready)]) -> HealthResponse:
    """Check startup and a bounded PostgreSQL query in the thread pool."""
    if not available:
        raise HTTPException(status_code=503)
    return HealthResponse()
