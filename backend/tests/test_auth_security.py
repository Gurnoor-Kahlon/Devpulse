import pytest
from pydantic import SecretStr, ValidationError
from starlette.responses import Response

from app.api.auth_dependencies import clear_cookies, set_cookies
from app.core.config import Settings
from app.core.security import new_token, password_hasher, token_hash, verify_password
from app.schemas.auth import RegisterRequest, ResetRequest


def test_argon2id_hashes_are_salted_and_passwords_are_not_truncated() -> None:
    password = "a" * 127 + "b"
    first, second = password_hasher.hash(password), password_hasher.hash(password)
    assert first.startswith("$argon2id$") and first != second
    assert verify_password(password, first)
    assert not verify_password("a" * 128, first)
    assert not verify_password(password, None)
    assert not verify_password(password, "invalid-hash")


@pytest.mark.parametrize("length", [0, 11, 129])
def test_password_boundaries(length: int) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", password=SecretStr("x" * length))


def test_normalization_and_secret_repr() -> None:
    request = RegisterRequest(email=" USER@EXAMPLE.COM ", password=SecretStr("  spaced password  "))
    assert request.email == "user@example.com"
    assert request.password.get_secret_value() == "  spaced password  "
    assert "spaced password" not in repr(request)
    raw = new_token()
    assert len(raw) == 43 and len(token_hash(raw)) == 64
    assert raw != new_token()
    reset = ResetRequest(token=SecretStr(raw), password=SecretStr("new-password-value"))
    assert raw not in repr(reset)


@pytest.mark.parametrize(
    "overrides",
    [
        {"environment": "production"},
        {"environment": "production", "app_origin": "https://example.com"},
        {"smtp_username": "user"},
        {"smtp_username": "user", "smtp_password": "password"},
        {"app_origin": "https://example.com/path"},
        {"app_origin": "https://user:pass@example.com"},
        {"smtp_port": 0},
    ],
)
def test_unsafe_auth_configuration_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_production_cookie_flags_and_deletion() -> None:
    settings = Settings(environment="production", app_origin="https://example.com", smtp_mode="tls")
    response = Response()
    set_cookies(response, settings, new_token(), new_token(), True)
    for cookie in response.headers.getlist("set-cookie"):
        assert cookie.startswith("__Host-devpulse_")
        assert all(
            flag in cookie
            for flag in ("Secure", "HttpOnly", "SameSite=lax", "Path=/", "Max-Age=604800")
        )
        assert "Domain=" not in cookie
    cleared = Response()
    clear_cookies(cleared, settings)
    assert all(
        "Max-Age=0" in value and "Secure" in value
        for value in cleared.headers.getlist("set-cookie")
    )
