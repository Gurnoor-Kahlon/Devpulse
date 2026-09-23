from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.auth_dependencies import CurrentUser, Database
from app.core.errors import ErrorResponse
from app.schemas.monitors import MonitorCreate, MonitorPage, MonitorResponse, MonitorUpdate
from app.services import monitors

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
