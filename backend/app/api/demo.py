from fastapi import APIRouter, Request

from app.api.auth_dependencies import Database, settings_for
from app.core.errors import ErrorResponse
from app.schemas.dashboard import DashboardWindow
from app.schemas.demo import DemoResponse
from app.services.demo import get_demo

router = APIRouter(
    prefix="/api/v1/demo",
    tags=["Public demo"],
    responses={503: {"model": ErrorResponse}},
)


@router.get("", response_model=DemoResponse)
def get(request: Request, db: Database, window: DashboardWindow = "24h") -> DemoResponse:
    return get_demo(db, settings_for(request), window)
