import hashlib
import secrets
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
# Perform the same verification work when an account is absent.
_dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


def now_utc() -> datetime:
    return datetime.now(UTC)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_password(value: str, stored: str | None) -> bool:
    try:
        matched = password_hasher.verify(stored or _dummy_hash, value)
        return bool(matched and stored is not None)
    except (VerificationError, InvalidHashError):
        return False
