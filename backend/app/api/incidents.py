from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.auth_dependencies import CurrentUser, Database
from app.core.errors import ErrorResponse
from app.schemas.incidents import IncidentDetail, IncidentPage
from app.services import incidents

router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Incidents"],
    responses={code: {"model": ErrorResponse} for code in (401, 404, 503)},
)


@router.get("", response_model=IncidentPage)
def list_owned(
    db: Database,
    user_id: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    status: Literal["open", "resolved"] | None = None,
    monitor_id: UUID | None = None,
) -> IncidentPage:
    return incidents.list_incidents(db, user_id, limit, cursor, status, monitor_id)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get(incident_id: UUID, db: Database, user_id: CurrentUser) -> IncidentDetail:
    return incidents.get_incident(db, user_id, incident_id)
