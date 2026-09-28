from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.auth_dependencies import CurrentUser, Database
from app.core.errors import ErrorResponse
from app.schemas.notifications import DeliveryPage, NotificationPreferences, NotificationUpdate
from app.services import notifications

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 503)},
)


@router.get("/preferences", response_model=NotificationPreferences)
def preferences(db: Database, user_id: CurrentUser) -> NotificationPreferences:
    return notifications.preferences(db, user_id)


@router.put("/preferences", response_model=NotificationPreferences)
def update_preferences(
    body: NotificationUpdate, db: Database, user_id: CurrentUser
) -> NotificationPreferences:
    return notifications.update_preferences(db, user_id, body)


@router.get("/deliveries", response_model=DeliveryPage)
def deliveries(
    db: Database,
    user_id: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    incident_id: UUID | None = None,
) -> DeliveryPage:
    return notifications.list_deliveries(db, user_id, limit, cursor, incident_id)
