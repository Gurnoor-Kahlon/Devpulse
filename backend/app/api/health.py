from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.errors import ErrorResponse

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
    responses={503: {"model": ErrorResponse, "description": "Application startup is incomplete."}},
    summary="Check API readiness",
)
async def ready(request: Request) -> HealthResponse:
    """Check completed application startup. Database readiness will be added with persistence."""
    if not request.app.state.ready:
        raise HTTPException(status_code=503)
    return HealthResponse()
