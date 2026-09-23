from datetime import timedelta

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import now_utc, token_hash
from app.models.auth import RateLimitBucket


def throttle(db: Session, scopes: list[tuple[str, int, int]]) -> None:
    """Atomically count all scopes, and persist rejected requests too."""
    now = now_utc()
    retry_after = 0
    for scope, limit, seconds in sorted(scopes):
        expired = RateLimitBucket.expires_at <= now
        statement = insert(RateLimitBucket).values(
            scope_hash=token_hash(scope), counter=1, expires_at=now + timedelta(seconds=seconds)
        )
        counter = db.scalar(
            statement.on_conflict_do_update(
                index_elements=[RateLimitBucket.scope_hash],
                set_={
                    "counter": case((expired, 1), else_=RateLimitBucket.counter + 1),
                    "expires_at": case(
                        (expired, statement.excluded.expires_at), else_=RateLimitBucket.expires_at
                    ),
                },
            ).returning(RateLimitBucket.counter)
        )
        if counter is not None and counter > limit:
            retry_after = max(retry_after, seconds)
    db.commit()
    if retry_after:
        raise ApiError(
            429,
            "rate_limited",
            "Too many requests. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
