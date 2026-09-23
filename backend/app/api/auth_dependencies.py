from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import now_utc
from app.db.session import get_session
from app.models.auth import AuthSession, User
from app.services.auth import active_session, csrf_matches

Database = Annotated[Session, Depends(get_session)]


def settings_for(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def cookie_names(settings: Settings) -> tuple[str, str]:
    prefix = "__Host-" if settings.environment == "production" else ""
    return f"{prefix}devpulse_session", f"{prefix}devpulse_csrf"


def set_cookies(
    response: Response, settings: Settings, token: str, csrf: str, authenticated: bool
) -> None:
    for name, value in zip(cookie_names(settings), (token, csrf), strict=True):
        response.set_cookie(
            name,
            value,
            max_age=604800 if authenticated else 1800,
            httponly=True,
            secure=settings.environment == "production",
            samesite="lax",
            path="/",
        )


def clear_cookies(response: Response, settings: Settings) -> None:
    for name in cookie_names(settings):
        response.delete_cookie(
            name,
            path="/",
            httponly=True,
            secure=settings.environment == "production",
            samesite="lax",
        )


def check_origin(request: Request) -> None:
    if request.headers.get("origin") != settings_for(request).app_origin:
        raise ApiError(403, "csrf_rejected", "Refresh the page and try again.")


def client_scope(request: Request) -> str:
    # Forwarded headers are not trusted here; configure trusted ingress separately.
    return request.client.host if request.client else "unknown"


def request_session(request: Request, db: Session) -> AuthSession | None:
    name, _ = cookie_names(settings_for(request))
    return active_session(db, request.cookies.get(name))


def require_csrf(request: Request, db: Database) -> AuthSession:
    check_origin(request)
    session = request_session(request, db)
    if session is None or not csrf_matches(session, request.headers.get("x-csrf-token")):
        raise ApiError(403, "csrf_rejected", "Refresh the page and try again.")
    session.last_activity_at = now_utc()
    db.commit()
    return session


CsrfSession = Annotated[AuthSession, Depends(require_csrf)]


def require_user(request: Request, db: Database) -> UUID:
    session = request_session(request, db)
    user = db.get(User, session.user_id) if session and session.user_id else None
    if user is None or session is None:
        raise ApiError(401, "authentication_required", "Sign in to continue.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        if not csrf_matches(session, request.headers.get("x-csrf-token")):
            raise ApiError(403, "csrf_rejected", "Refresh the page and try again.")
    session.last_activity_at = now_utc()
    db.commit()
    return user.id


CurrentUser = Annotated[UUID, Depends(require_user)]
