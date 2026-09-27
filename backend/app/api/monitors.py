from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.auth_dependencies import CurrentUser, Database
from app.core.errors import ErrorResponse
from app.schemas.assertions import AssertionPage, AssertionUpdate
from app.schemas.dashboard import DashboardWindow
from app.schemas.monitor_history import CheckPage, MonitorAnalytics
from app.schemas.monitors import MonitorCreate, MonitorPage, MonitorResponse, MonitorUpdate
from app.services import assertions, monitor_history, monitors

router = APIRouter(
    prefix="/api/v1/monitors",
    tags=["Monitors"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 503)},
)


@router.get("", response_model=MonitorPage)
def list_owned(
    db: Database,
    user_id: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> MonitorPage:
    return monitors.list_monitors(db, user_id, limit, cursor)


@router.post("", response_model=MonitorResponse, status_code=201)
def create(
    body: MonitorCreate, db: Database, user_id: CurrentUser, response: Response
) -> MonitorResponse:
    monitor = monitors.create_monitor(db, user_id, body)
    response.headers["Location"] = f"/api/v1/monitors/{monitor.id}"
    return MonitorResponse.model_validate(monitor)


@router.get("/{monitor_id}", response_model=MonitorResponse)
def get(monitor_id: UUID, db: Database, user_id: CurrentUser) -> MonitorResponse:
    return MonitorResponse.model_validate(monitors.owned_monitor(db, user_id, monitor_id))


@router.patch("/{monitor_id}", response_model=MonitorResponse)
def update(
    monitor_id: UUID, body: MonitorUpdate, db: Database, user_id: CurrentUser
) -> MonitorResponse:
    return MonitorResponse.model_validate(monitors.update_monitor(db, user_id, monitor_id, body))


@router.delete("/{monitor_id}", status_code=204)
def archive(
    monitor_id: UUID,
    db: Database,
    user_id: CurrentUser,
    configuration_version: Annotated[int, Query(ge=1, le=2147483647)],
) -> Response:
    monitors.archive_monitor(db, user_id, monitor_id, configuration_version)
    return Response(status_code=204)


@router.get("/{monitor_id}/analytics", response_model=MonitorAnalytics)
def analytics(
    monitor_id: UUID, db: Database, user_id: CurrentUser, window: DashboardWindow = "24h"
) -> MonitorAnalytics:
    return monitor_history.get_analytics(db, user_id, monitor_id, window)


@router.get("/{monitor_id}/checks", response_model=CheckPage)
def checks(
    monitor_id: UUID,
    db: Database,
    user_id: CurrentUser,
    window: DashboardWindow = "24h",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(min_length=1, max_length=600)] = None,
) -> CheckPage:
    return monitor_history.list_checks(db, user_id, monitor_id, window, limit, cursor)


@router.get("/{monitor_id}/assertions", response_model=AssertionPage)
def get_assertions(monitor_id: UUID, db: Database, user_id: CurrentUser) -> AssertionPage:
    return assertions.get_assertions(db, user_id, monitor_id)


@router.put("/{monitor_id}/assertions", response_model=AssertionPage)
def put_assertions(
    monitor_id: UUID, body: AssertionUpdate, db: Database, user_id: CurrentUser
) -> AssertionPage:
    return assertions.replace_assertions(db, user_id, monitor_id, body)
