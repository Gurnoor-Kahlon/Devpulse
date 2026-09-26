from fastapi import APIRouter

from app.api.auth_dependencies import CurrentUser, Database
from app.core.errors import ErrorResponse
from app.schemas.dashboard import DashboardResponse, DashboardWindow
from app.services.dashboard import get_dashboard

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
    responses={code: {"model": ErrorResponse} for code in (401, 503)},
)


@router.get("", response_model=DashboardResponse)
def get(db: Database, user_id: CurrentUser, window: DashboardWindow = "24h") -> DashboardResponse:
    return get_dashboard(db, user_id, window)
