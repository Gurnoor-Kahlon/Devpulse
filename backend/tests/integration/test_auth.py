import os
import re
import smtplib
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import now_utc, token_hash, verify_password
from app.factory import create_app
from app.models.auth import AuthSession, AuthToken, RateLimitBucket, User
from app.services import mail
from app.services.auth import consume_token
from app.services.mail import send_auth_email
from app.services.throttle import throttle

pytestmark = pytest.mark.integration
PREFIX = "/api/v1/auth"
PASSWORD = "test-account-password-1"
EMAIL = "person@example.com"


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    messages: list[tuple[str, str, str]] = []

    def capture(settings: Settings, destination: str, purpose: str, token: str) -> None:
        messages.append((destination, purpose, token))

    monkeypatch.setattr(mail, "send_auth_email", capture)
    return messages


@pytest.fixture
def auth_app(database_engine: Engine, database_settings: Settings) -> Iterator[FastAPI]:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    app = create_app(database_settings)
    # Each client owns only HTTP state; one application lifespan owns the test pool.
    with TestClient(app):
        app.state.engine = database_engine
        app.state.session_factory = sessionmaker(database_engine, expire_on_commit=False)
        yield app


def client_for(app: FastAPI) -> TestClient:
    client = TestClient(app)
    client.headers["Origin"] = app.state.settings.app_origin
    response = client.get(f"{PREFIX}/csrf")
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def client(auth_app: FastAPI, outbox: list[tuple[str, str, str]]) -> Iterator[TestClient]:
    with_client = client_for(auth_app)
    try:
        yield with_client
    finally:
        with_client.close()


def register(client: TestClient, email: str = EMAIL) -> httpx.Response:
    return client.post(f"{PREFIX}/register", json={"email": email, "password": PASSWORD})


def login(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> httpx.Response:
    response = client.post(f"{PREFIX}/login", json={"email": email, "password": password})
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = client.get(f"{PREFIX}/csrf").json()["csrf_token"]
    return response


def test_registration_verification_login_logout(
    client: TestClient,
    outbox: list[tuple[str, str, str]],
    database_engine: Engine,
) -> None:
    old_cookie = client.cookies.get("devpulse_session")
    assert client.get(f"{PREFIX}/me").status_code == 401
    assert register(client, "PERSON@EXAMPLE.COM").status_code == 202
    code = outbox[-1][2]
    with Session(database_engine) as db:
        user = db.scalar(select(User))
        assert user.email == EMAIL and user.email_verified_at is None
        assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
        assert db.scalar(select(AuthToken.token_hash)) == token_hash(code)
    assert client.post(f"{PREFIX}/verify-email", json={"token": code}).status_code == 200
    assert client.post(f"{PREFIX}/verify-email", json={"token": code}).status_code == 400
    response = login(client)
    assert response.status_code == 200 and response.json()["email_verified_at"] is not None
    assert set(response.json()) == {"id", "email", "email_verified_at"}
    assert client.cookies.get("devpulse_session") != old_cookie
    with Session(database_engine) as db:
        assert (
            db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(old_cookie)))
            is None
        )
        record = db.scalar(select(AuthSession).where(AuthSession.user_id.is_not(None)))
        assert record.expires_at - record.created_at == timedelta(days=7)
        assert record.csrf_token_hash == token_hash(client.headers["X-CSRF-Token"])
    assert client.get(f"{PREFIX}/me").status_code == 200
    saved = client.cookies.get("devpulse_session")
    assert client.post(f"{PREFIX}/logout").status_code == 200
    assert not client.cookies
    client.cookies.set("devpulse_session", saved)
    assert client.get(f"{PREFIX}/me").status_code == 401


def test_wrong_password_and_absent_account_have_identical_errors(client: TestClient) -> None:
    register(client)
    wrong = login(client, password="incorrect")
    absent = login(client, email="missing@example.com", password="incorrect")
    assert wrong.status_code == absent.status_code == 401
    assert wrong.json()["error"] == absent.json()["error"]
    assert client.get(f"{PREFIX}/me").status_code == 401


@pytest.mark.parametrize(
    "mutation", ["missing-origin", "wrong-origin", "missing-csrf", "wrong-csrf"]
)
def test_csrf_failures_cannot_register(
    client: TestClient, database_engine: Engine, mutation: str
) -> None:
    if mutation == "missing-origin":
        del client.headers["Origin"]
    elif mutation == "wrong-origin":
        client.headers["Origin"] = "http://localhost:3000.attacker.example"
    elif mutation == "missing-csrf":
        del client.headers["X-CSRF-Token"]
    else:
        client.headers["X-CSRF-Token"] = "a" * 43
    assert register(client).status_code == 403
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize("expiry", ["absolute", "inactive"])
def test_session_expiry(client: TestClient, database_engine: Engine, expiry: str) -> None:
    register(client)
    login(client)
    with Session(database_engine) as db:
        values = {"last_activity_at": now_utc() - timedelta(hours=25)}
        if expiry == "absolute":
            values = {
                "created_at": now_utc() - timedelta(days=8),
                "expires_at": now_utc() - timedelta(seconds=1),
            }
        db.execute(update(AuthSession).where(AuthSession.user_id.is_not(None)).values(**values))
        db.commit()
    assert client.get(f"{PREFIX}/me").status_code == 401
    assert client.post(f"{PREFIX}/logout").status_code == 403


def test_reset_revokes_every_session_and_cannot_be_reused(
    client: TestClient,
    auth_app: FastAPI,
    outbox: list[tuple[str, str, str]],
    database_engine: Engine,
) -> None:
    register(client)
    assert login(client).status_code == 200  # Unverified accounts may sign in.
    other = client_for(auth_app)
    try:
        assert login(other).status_code == 200
        assert client.post(f"{PREFIX}/forgot-password", json={"email": EMAIL}).status_code == 202
        code = outbox[-1][2]
        assert (
            client.post(
                f"{PREFIX}/reset-password", json={"token": code, "password": "replacement-password"}
            ).status_code
            == 200
        )
        assert other.get(f"{PREFIX}/me").status_code == 401
        client.headers["X-CSRF-Token"] = client.get(f"{PREFIX}/csrf").json()["csrf_token"]
        assert (
            client.post(
                f"{PREFIX}/reset-password", json={"token": code, "password": "another-password"}
            ).status_code
            == 400
        )
        assert login(client).status_code == 401
        assert login(client, password="replacement-password").status_code == 200
        with Session(database_engine) as db:
            assert verify_password("replacement-password", db.scalar(select(User.password_hash)))
    finally:
        other.close()


def test_resend_supersedes_prior_token_and_wrong_purpose_fails(
    client: TestClient,
    outbox: list[tuple[str, str, str]],
) -> None:
    register(client)
    old = outbox[-1][2]
    assert client.post(f"{PREFIX}/resend-verification", json={"email": EMAIL}).status_code == 202
    new = outbox[-1][2]
    assert client.post(f"{PREFIX}/verify-email", json={"token": old}).status_code == 400
    assert (
        client.post(
            f"{PREFIX}/reset-password", json={"token": new, "password": PASSWORD}
        ).status_code
        == 400
    )
    assert client.post(f"{PREFIX}/verify-email", json={"token": new}).status_code == 200


def test_expired_email_code_is_rejected(
    client: TestClient, outbox: list[tuple[str, str, str]], database_engine: Engine
) -> None:
    register(client)
    with Session(database_engine) as db:
        db.execute(
            update(AuthToken).values(
                created_at=now_utc() - timedelta(days=2),
                expires_at=now_utc() - timedelta(seconds=1),
            )
        )
        db.commit()
    assert client.post(f"{PREFIX}/verify-email", json={"token": outbox[-1][2]}).status_code == 400


def test_email_requests_and_duplicate_registration_are_generic(
    client: TestClient, outbox: list[tuple[str, str, str]]
) -> None:
    first = register(client)
    duplicate = register(client)
    absent = client.post(f"{PREFIX}/forgot-password", json={"email": "absent@example.com"})
    assert first.status_code == duplicate.status_code == absent.status_code == 202
    assert first.json() == duplicate.json() == absent.json()
    assert len(outbox) == 1


def test_smtp_failure_preserves_account_and_allows_resend(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    database_engine: Engine,
    capsys: pytest.CaptureFixture[str],
    outbox: list[tuple[str, str, str]],
) -> None:
    original = mail.send_auth_email

    def fail(*args: object) -> None:
        assert database_engine.pool.checkedout() == 0
        raise smtplib.SMTPException("smtp-secret-canary")

    monkeypatch.setattr(mail, "send_auth_email", fail)
    assert register(client).status_code == 202
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(AuthToken.consumed_at)) is not None
    assert "smtp-secret-canary" not in capsys.readouterr().out
    monkeypatch.setattr(mail, "send_auth_email", original)
    assert client.post(f"{PREFIX}/resend-verification", json={"email": EMAIL}).status_code == 202
    assert len(outbox) == 1


def test_login_throttle_is_shared_across_sessions(client: TestClient, auth_app: FastAPI) -> None:
    register(client)
    for _ in range(10):
        assert login(client, password="wrong").status_code == 401
    other = client_for(auth_app)
    try:
        result = login(other)
        assert result.status_code == 429 and result.headers["retry-after"]
    finally:
        other.close()


def test_email_throttle_shared_across_endpoints(
    client: TestClient, database_engine: Engine
) -> None:
    register(client)
    for endpoint in ("resend-verification", "forgot-password"):
        assert client.post(f"{PREFIX}/{endpoint}", json={"email": EMAIL}).status_code == 202
    assert register(client).status_code == 429
    with Session(database_engine) as db:
        db.execute(update(RateLimitBucket).values(expires_at=now_utc() - timedelta(seconds=1)))
        db.commit()
    assert register(client).status_code == 202


def test_atomic_throttle_and_token_consumption(
    client: TestClient, outbox: list[tuple[str, str, str]], database_engine: Engine
) -> None:
    register(client)
    code = outbox[-1][2]

    def consume(_: int) -> bool:
        with Session(database_engine) as db:
            try:
                consume_token(db, code, "verification")
                db.commit()
                return True
            except ApiError:
                return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(consume, range(2))) == [False, True]

    def limited(_: int) -> bool:
        with Session(database_engine) as db:
            try:
                throttle(db, [("concurrency-test", 1, 60)])
                return True
            except ApiError:
                return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(limited, range(4))).count(True) == 1


def test_password_tokens_cookies_are_absent_from_logs(
    client: TestClient, outbox: list[tuple[str, str, str]], capsys: pytest.CaptureFixture[str]
) -> None:
    register(client)
    login(client)
    logs = capsys.readouterr().out
    for secret in (
        PASSWORD,
        EMAIL,
        outbox[-1][2],
        client.cookies.get("devpulse_session"),
        client.headers["X-CSRF-Token"],
    ):
        assert secret not in logs


def test_csrf_is_bound_to_session_and_rejects_cross_site_bootstrap(
    client: TestClient, auth_app: FastAPI
) -> None:
    other = client_for(auth_app)
    try:
        other.headers["X-CSRF-Token"] = client.headers["X-CSRF-Token"]
        assert register(other).status_code == 403
        assert (
            other.get(f"{PREFIX}/csrf", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        )
        assert (
            other.get(f"{PREFIX}/csrf", headers={"Origin": "https://evil.example"}).status_code
            == 403
        )
    finally:
        other.close()


def test_parallel_registrations_preserve_one_account(
    client: TestClient,
    auth_app: FastAPI,
    database_engine: Engine,
    outbox: list[tuple[str, str, str]],
) -> None:
    other = client_for(auth_app)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert [
                response.status_code for response in executor.map(register, (client, other))
            ] == [202, 202]
        with Session(database_engine) as db:
            assert db.scalar(select(func.count()).select_from(User)) == 1
        assert len(outbox) == 1
    finally:
        other.close()


def test_password_reset_serializes_with_login(
    client: TestClient, auth_app: FastAPI, outbox: list[tuple[str, str, str]]
) -> None:
    register(client)
    other = client_for(auth_app)
    try:
        assert client.post(f"{PREFIX}/forgot-password", json={"email": EMAIL}).status_code == 202
        code = outbox[-1][2]
        with ThreadPoolExecutor(max_workers=2) as executor:
            logging_in = executor.submit(login, other)
            resetting = executor.submit(
                client.post,
                f"{PREFIX}/reset-password",
                json={"token": code, "password": "replacement-password"},
            )
            assert logging_in.result().status_code in {200, 401}
            assert resetting.result().status_code == 200
        assert other.get(f"{PREFIX}/me").status_code == 401
        # Reset may revoke the session after the concurrent login refreshed its CSRF token.
        other.headers["X-CSRF-Token"] = other.get(f"{PREFIX}/csrf").json()["csrf_token"]
        assert login(other, password="replacement-password").status_code == 200
    finally:
        other.close()


def test_me_returns_only_the_cookie_owner(client: TestClient, auth_app: FastAPI) -> None:
    register(client)
    first = login(client).json()
    other = client_for(auth_app)
    try:
        assert register(other, "other@example.com").status_code == 202
        second = login(other, "other@example.com").json()
        assert first["id"] != second["id"]
        assert client.get(f"{PREFIX}/me", params={"user_id": second["id"]}).json() == first
        assert other.get(f"{PREFIX}/me").json() == second
    finally:
        other.close()


@pytest.mark.mailpit
def test_real_smtp_verification_and_reset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mail, "send_auth_email", send_auth_email)
    email = f"auth-{uuid4().hex}@example.com"
    base = os.environ.get("TEST_MAILPIT_URL", "http://127.0.0.1:8025")

    def code_from_mailpit(subject: str) -> str:
        with httpx.Client(base_url=base, trust_env=False, timeout=5) as smtp_ui:
            response = smtp_ui.get("/api/v1/messages")
            response.raise_for_status()
            found = next(
                item
                for item in response.json()["messages"]
                if item["Subject"] == subject and item["To"][0]["Address"] == email
            )
            message = smtp_ui.get(f"/api/v1/message/{found['ID']}").json()
            matched = re.search(r"[A-Za-z0-9_-]{43}", message["Text"])
            assert matched
            return matched.group()

    assert register(client, email).status_code == 202
    verification = code_from_mailpit("Verify your DevPulse email")
    assert client.post(f"{PREFIX}/verify-email", json={"token": verification}).status_code == 200
    assert login(client, email).status_code == 200
    assert client.post(f"{PREFIX}/forgot-password", json={"email": email}).status_code == 202
    reset = code_from_mailpit("Reset your DevPulse password")
    assert (
        client.post(
            f"{PREFIX}/reset-password", json={"token": reset, "password": "replacement-password"}
        ).status_code
        == 200
    )
