import secrets
from datetime import timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import new_token, now_utc, token_hash
from app.models.auth import AuthSession, AuthToken, User

Purpose = Literal["verification", "reset"]


def active_session(db: Session, raw: str | None) -> AuthSession | None:
    if raw is None or len(raw) != 43:
        return None
    now = now_utc()
    return db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(raw),
            AuthSession.expires_at > now,
            AuthSession.last_activity_at > now - timedelta(hours=24),
        )
    )


def create_session(db: Session, user_id: UUID | None) -> tuple[AuthSession, str, str]:
    token, csrf = new_token(), new_token()
    now = now_utc()
    session = AuthSession(
        user_id=user_id,
        token_hash=token_hash(token),
        csrf_token_hash=token_hash(csrf),
        created_at=now,
        last_activity_at=now,
        expires_at=now + (timedelta(days=7) if user_id else timedelta(minutes=30)),
    )
    db.add(session)
    return session, token, csrf


def csrf_matches(session: AuthSession, value: str | None) -> bool:
    return (
        value is not None
        and len(value) == 43
        and secrets.compare_digest(session.csrf_token_hash, token_hash(value))
    )


def issue_token(db: Session, user: User, purpose: Purpose) -> tuple[UUID, str]:
    """Caller holds the user row lock (or has just inserted it)."""
    now = now_utc()
    db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    raw = new_token()
    token = AuthToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=token_hash(raw),
        created_at=now,
        expires_at=now
        + (timedelta(hours=24) if purpose == "verification" else timedelta(minutes=30)),
    )
    db.add(token)
    db.flush()
    return token.id, raw


def consume_token(db: Session, raw: str, purpose: Purpose) -> User:
    digest = token_hash(raw)
    user_id = db.scalar(select(AuthToken.user_id).where(AuthToken.token_hash == digest))
    if user_id is not None:
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        # Recheck after taking the user lock: concurrent consumers must serialize.
        token = db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == digest,
                AuthToken.purpose == purpose,
                AuthToken.consumed_at.is_(None),
                AuthToken.expires_at > now_utc(),
            )
        )
        if user is not None and token is not None:
            token.consumed_at = now_utc()
            return user
    raise ApiError(400, "invalid_token", "This code is invalid or has expired.")


def revoke_user_sessions(db: Session, user_id: UUID) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
