from uuid import uuid4

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.api.auth_dependencies import (
    CsrfSession,
    Database,
    check_origin,
    clear_cookies,
    client_scope,
    cookie_names,
    request_session,
    set_cookies,
    settings_for,
)
from app.core.errors import ApiError, ErrorResponse
from app.core.security import new_token, now_utc, password_hasher, token_hash, verify_password
from app.models.auth import AuthSession, User
from app.schemas.auth import (
    CsrfResponse,
    EmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetRequest,
    TokenRequest,
    UserResponse,
)
from app.services.auth import (
    Purpose,
    consume_token,
    create_session,
    csrf_matches,
    issue_token,
    revoke_user_sessions,
)
from app.services.mail import deliver_token
from app.services.throttle import throttle

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
    responses={code: {"model": ErrorResponse} for code in (400, 401, 403, 429, 503)},
)
EMAIL_MESSAGE = MessageResponse(
    message="If this request is eligible, an email will arrive shortly."
)


@router.get("/csrf", response_model=CsrfResponse)
def csrf(request: Request, response: Response, db: Database) -> CsrfResponse:
    if request.headers.get("origin") is not None:
        check_origin(request)
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise ApiError(403, "csrf_rejected", "Refresh the page and try again.")
    throttle(db, [(f"csrf:{client_scope(request)}", 60, 3600)])
    settings = settings_for(request)
    session = request_session(request, db)
    _, csrf_name = cookie_names(settings)
    raw_csrf = request.cookies.get(csrf_name)
    if session is None:
        session, raw_session, raw_csrf = create_session(db, None)
        set_cookies(response, settings, raw_session, raw_csrf, False)
    elif not csrf_matches(session, raw_csrf):
        raw_csrf = new_token()
        session.csrf_token_hash = token_hash(raw_csrf)
        # Do not extend the absolute browser session lifetime on CSRF refresh.
        response.set_cookie(
            csrf_name,
            raw_csrf,
            httponly=True,
            secure=settings.environment == "production",
            samesite="lax",
            path="/",
        )
    session.last_activity_at = now_utc()
    db.commit()
    assert raw_csrf is not None
    return CsrfResponse(csrf_token=raw_csrf)


def email_throttle(request: Request, db: Database, email: str) -> None:
    throttle(
        db, [(f"email:ip:{client_scope(request)}", 10, 3600), (f"email:address:{email}", 3, 3600)]
    )


@router.post("/register", response_model=MessageResponse, status_code=202)
def register(
    body: RegisterRequest, request: Request, db: Database, session: CsrfSession
) -> MessageResponse:
    email_throttle(request, db, body.email)
    hashed = password_hasher.hash(body.password.get_secret_value())
    user = db.scalar(
        insert(User)
        .values(id=uuid4(), email=body.email, password_hash=hashed)
        .on_conflict_do_nothing(index_elements=[User.email])
        .returning(User)
    )
    if user is None:
        db.commit()
        return EMAIL_MESSAGE
    token_id, raw = issue_token(db, user, "verification")
    db.commit()
    deliver_token(db, settings_for(request), body.email, "verification", token_id, raw)
    return EMAIL_MESSAGE


@router.post("/login", response_model=UserResponse)
def login(
    body: LoginRequest, request: Request, response: Response, db: Database, session: CsrfSession
) -> UserResponse:
    throttle(
        db, [(f"login:ip:{client_scope(request)}", 20, 900), (f"login:email:{body.email}", 10, 900)]
    )
    # Login and reset share the user row lock so reset cannot miss a concurrent session.
    user = db.scalar(select(User).where(User.email == body.email).with_for_update())
    if not verify_password(body.password.get_secret_value(), user.password_hash if user else None):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    assert user is not None
    current = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == session.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        current is None
        or current.expires_at <= now_utc()
        or not csrf_matches(current, request.headers.get("x-csrf-token"))
    ):
        raise ApiError(403, "csrf_rejected", "Refresh the page and try again.")
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(body.password.get_secret_value())
        user.updated_at = now_utc()
    db.delete(current)
    _, raw, raw_csrf = create_session(db, user.id)
    result = UserResponse.model_validate(user)
    db.commit()
    set_cookies(response, settings_for(request), raw, raw_csrf, True)
    return result


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request, response: Response, db: Database, session: CsrfSession
) -> MessageResponse:
    db.execute(delete(AuthSession).where(AuthSession.id == session.id))
    db.commit()
    clear_cookies(response, settings_for(request))
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=UserResponse)
def me(request: Request, db: Database) -> UserResponse:
    session = request_session(request, db)
    user = db.get(User, session.user_id) if session and session.user_id else None
    if user is None or session is None:
        raise ApiError(401, "authentication_required", "Sign in to continue.")
    session.last_activity_at = now_utc()
    result = UserResponse.model_validate(user)
    db.commit()
    return result


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    body: TokenRequest, request: Request, db: Database, session: CsrfSession
) -> MessageResponse:
    throttle(db, [(f"token:ip:{client_scope(request)}", 20, 900)])
    user = consume_token(db, body.token.get_secret_value(), "verification")
    user.email_verified_at = user.email_verified_at or now_utc()
    user.updated_at = now_utc()
    db.commit()
    return MessageResponse(message="Email verified.")


def request_email(
    body: EmailRequest, request: Request, db: Database, verification: bool
) -> MessageResponse:
    email_throttle(request, db, body.email)
    user = db.scalar(select(User).where(User.email == body.email).with_for_update())
    if user is None or (verification and user.email_verified_at is not None):
        db.commit()
        return EMAIL_MESSAGE
    purpose: Purpose = "verification" if verification else "reset"
    token_id, raw = issue_token(db, user, purpose)
    db.commit()
    deliver_token(db, settings_for(request), body.email, purpose, token_id, raw)
    return EMAIL_MESSAGE


@router.post("/resend-verification", response_model=MessageResponse, status_code=202)
def resend(
    body: EmailRequest, request: Request, db: Database, session: CsrfSession
) -> MessageResponse:
    return request_email(body, request, db, True)


@router.post("/forgot-password", response_model=MessageResponse, status_code=202)
def forgot(
    body: EmailRequest, request: Request, db: Database, session: CsrfSession
) -> MessageResponse:
    return request_email(body, request, db, False)


@router.post("/reset-password", response_model=MessageResponse)
def reset(
    body: ResetRequest, request: Request, response: Response, db: Database, session: CsrfSession
) -> MessageResponse:
    throttle(db, [(f"token:ip:{client_scope(request)}", 20, 900)])
    hashed = password_hasher.hash(body.password.get_secret_value())
    user = consume_token(db, body.token.get_secret_value(), "reset")
    user.password_hash = hashed
    user.updated_at = now_utc()
    revoke_user_sessions(db, user.id)
    db.commit()
    clear_cookies(response, settings_for(request))
    return MessageResponse(message="Password reset. Sign in with your new password.")
