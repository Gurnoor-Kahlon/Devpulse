from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.security import now_utc
from app.factory import create_app
from app.models.auth import AuthSession, User
from app.models.monitor import Monitor
from app.services.auth import create_session, issue_token

pytestmark = pytest.mark.integration
PREFIX = "/api/v1/monitors"
BODY = {"name": "Example API", "url": "https://example.com/health"}
ClientFactory = Callable[..., tuple[TestClient, UUID]]


@pytest.fixture
def monitor_app(database_engine: Engine, database_settings: Settings) -> Iterator[FastAPI]:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    app = create_app(database_settings)
    with TestClient(app):
        app.state.engine = database_engine
        app.state.session_factory = sessionmaker(database_engine, expire_on_commit=False)
        yield app


@pytest.fixture
def client_factory(monitor_app: FastAPI, database_engine: Engine) -> Iterator[ClientFactory]:
    clients: list[TestClient] = []

    def make(verified: bool = True, user_id: UUID | None = None) -> tuple[TestClient, UUID]:
        with Session(database_engine) as db:
            if user_id is None:
                user = User(
                    email=f"{uuid4().hex}@example.com",
                    password_hash="unused-test-hash",
                    email_verified_at=now_utc() if verified else None,
                )
                db.add(user)
                db.flush()
                user_id = user.id
            _, token, csrf = create_session(db, user_id)
            db.commit()
        client = TestClient(monitor_app)
        client.cookies.set("devpulse_session", token)
        client.headers.update(
            {"Origin": monitor_app.state.settings.app_origin, "X-CSRF-Token": csrf}
        )
        clients.append(client)
        return client, user_id

    yield make
    for client in clients:
        client.close()


def seed(db: Session, user_id: UUID, count: int, *, enabled: bool = True) -> list[Monitor]:
    now = now_utc()
    rows = [
        Monitor(
            user_id=user_id,
            name=f"Monitor {i}",
            url="https://example.com/",
            enabled=enabled,
            next_due_at=now if enabled else None,
        )
        for i in range(count)
    ]
    db.add_all(rows)
    db.commit()
    return rows


def create(client: TestClient, **changes: object) -> dict[str, object]:
    response = client.post(PREFIX, json={**BODY, **changes})
    assert response.status_code == 201, response.text
    assert response.headers["location"] == f"{PREFIX}/{response.json()['id']}"
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def test_create_defaults_read_and_persistence(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    client, owner = client_factory()
    assert client.get(PREFIX).json() == {"items": [], "next_cursor": None}
    result = create(client)
    assert result["method"] == "GET" and result["expected_status"] == 200
    assert result["timeout_seconds"] == 5 and result["interval_seconds"] == 60
    assert result["configuration_version"] == 1 and result["enabled"] is True
    assert result["current_state"] == "unknown" and result["last_completed_check_at"] is None
    assert result["next_due_at"] is not None
    assert "user_id" not in result and "deleted_at" not in result
    assert client.get(f"{PREFIX}/{result['id']}").json() == result
    assert client.get(PREFIX).json()["items"] == [result]
    with Session(database_engine) as db:
        row = db.get(Monitor, UUID(str(result["id"])))
        assert row.user_id == owner and row.current_state == "unknown"


def test_verification_required_for_create_and_enable(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    client, owner = client_factory(verified=False)
    for enabled in (True, False):
        response = client.post(PREFIX, json={**BODY, "enabled": enabled})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "email_verification_required"
    with Session(database_engine) as db:
        row = seed(db, owner, 1, enabled=False)[0]
        monitor_id = row.id
        _, token = issue_token(db, db.get(User, owner), "verification")
        db.commit()
    path = f"{PREFIX}/{monitor_id}"
    assert client.patch(path, json={"configuration_version": 1, "enabled": True}).status_code == 403
    assert client.get(path).status_code == 200
    assert (
        client.patch(path, json={"configuration_version": 1, "name": "Renamed"}).status_code == 200
    )
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert client.patch(path, json={"configuration_version": 2, "enabled": True}).status_code == 200
    create(client)


def test_authentication_csrf_and_origin_on_every_write(
    client_factory: ClientFactory, monitor_app: FastAPI
) -> None:
    client, _ = client_factory()
    monitor = create(client)
    path = f"{PREFIX}/{monitor['id']}"
    writes = [
        ("POST", PREFIX, BODY),
        ("PATCH", path, {"configuration_version": 1, "name": "Edit"}),
        ("DELETE", path + "?configuration_version=1", None),
    ]
    # A client without entering a lifespan reuses the migrated application.
    with_client = TestClient(monitor_app)
    try:
        for method, url, body in writes:
            assert with_client.request(method, url, json=body).status_code == 401
        assert with_client.get(PREFIX).status_code == 401
        csrf = with_client.get("/api/v1/auth/csrf").json()["csrf_token"]
        with_client.headers.update(
            {"Origin": monitor_app.state.settings.app_origin, "X-CSRF-Token": csrf}
        )
        for method, url, body in writes:
            assert with_client.request(method, url, json=body).status_code == 401
        for headers in ({"X-CSRF-Token": "invalid"}, {"Origin": "https://attacker.example"}):
            for method, url, body in writes:
                assert client.request(method, url, json=body, headers=headers).status_code == 403
        del client.headers["X-CSRF-Token"]
        for method, url, body in writes:
            assert client.request(method, url, json=body).status_code == 403
    finally:
        with_client.close()


def test_expired_and_revoked_sessions_cannot_read_or_write(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    client, owner = client_factory()
    create(client)
    with Session(database_engine) as db:
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == owner)
            .values(last_activity_at=now_utc() - timedelta(hours=25))
        )
        db.commit()
    assert client.get(PREFIX).status_code == 401
    assert client.post(PREFIX, json=BODY).status_code == 401
    fresh, _ = client_factory(user_id=owner)
    with Session(database_engine) as db:
        db.execute(delete(AuthSession).where(AuthSession.user_id == owner))
        db.commit()
    assert fresh.get(PREFIX).status_code == 401


def test_ownership_and_archived_rows_are_inaccessible(client_factory: ClientFactory) -> None:
    owner, _ = client_factory()
    other, _ = client_factory()
    monitor = create(owner)
    for identifier in (monitor["id"], uuid4()):
        path = f"{PREFIX}/{identifier}"
        assert other.get(path).status_code == 404
        assert (
            other.patch(path, json={"configuration_version": 1, "name": "stolen"}).status_code
            == 404
        )
        assert other.delete(path, params={"configuration_version": 1}).status_code == 404
    assert other.get(PREFIX).json()["items"] == []
    path = f"{PREFIX}/{monitor['id']}"
    assert owner.delete(path, params={"configuration_version": 1}).status_code == 204
    assert owner.get(path).status_code == 404
    assert owner.patch(path, json={"configuration_version": 2, "enabled": True}).status_code == 404
    assert owner.delete(path, params={"configuration_version": 2}).status_code == 404
    assert owner.get(PREFIX).json()["items"] == []


def test_edit_conflicts_noops_pause_resume_and_archive_preserve_evidence(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    client, owner = client_factory()
    monitor = create(client)
    path = f"{PREFIX}/{monitor['id']}"
    checked_at = now_utc()
    with Session(database_engine) as db:
        db.execute(
            update(Monitor)
            .where(Monitor.user_id == owner)
            .values(current_state="down", last_completed_check_at=checked_at)
        )
        db.commit()
    edit = client.patch(path, json={"configuration_version": 1, "name": "Renamed"}).json()
    assert edit["configuration_version"] == 2 and edit["next_due_at"] == monitor["next_due_at"]
    assert (
        client.patch(path, json={"configuration_version": 1, "enabled": False}).status_code == 409
    )
    assert client.delete(path, params={"configuration_version": 1}).status_code == 409
    unchanged = client.patch(path, json={"configuration_version": 2, "name": "Renamed"}).json()
    assert unchanged == edit
    pause = client.patch(path, json={"configuration_version": 2, "enabled": False}).json()
    assert pause["next_due_at"] is None and pause["current_state"] == "down"
    resume = client.patch(
        path,
        json={
            "configuration_version": 3,
            "enabled": True,
            "interval_seconds": 120,
            "method": "HEAD",
        },
    ).json()
    assert resume["next_due_at"] is not None and resume["configuration_version"] == 4
    assert resume["last_completed_check_at"] == edit["last_completed_check_at"]
    assert client.delete(path).status_code == 422
    assert client.delete(path, params={"configuration_version": 4}).status_code == 204
    with Session(database_engine) as db:
        row = db.get(Monitor, UUID(str(monitor["id"])))
        assert row.deleted_at is not None and row.enabled is False and row.next_due_at is None
        assert row.configuration_version == 5 and row.current_state == "down"
        assert row.last_completed_check_at == checked_at


def test_cursor_pagination_ties_insertions_and_ownership(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    client, owner = client_factory()
    other, _ = client_factory()
    with Session(database_engine) as db:
        rows = seed(db, owner, 5)
        ids = {str(row.id) for row in rows}
        db.execute(
            update(Monitor)
            .where(Monitor.user_id == owner)
            .values(created_at=now_utc() - timedelta(days=1))
        )
        db.commit()
    first = client.get(PREFIX, params={"limit": 2}).json()
    cursor = first["next_cursor"]
    assert other.get(PREFIX, params={"cursor": cursor}).json()["items"] == []
    added = create(client)
    received = first["items"]
    while cursor:
        page = client.get(PREFIX, params={"limit": 2, "cursor": cursor}).json()
        received.extend(page["items"])
        cursor = page["next_cursor"]
    assert len(received) == len(ids) and {row["id"] for row in received} == ids
    assert added["id"] not in ids
    for params in ({"limit": 0}, {"limit": 101}, {"cursor": "%%%"}, {"cursor": "x" * 201}):
        assert client.get(PREFIX, params=params).status_code == 422


def test_quota_concurrency_and_archive_releases_account_slot(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    first, owner = client_factory()
    second, _ = client_factory(user_id=owner)
    with Session(database_engine) as db:
        seed(db, owner, 9, enabled=False)
    barrier = Barrier(2)

    def attempt(client: TestClient) -> httpx.Response:
        barrier.wait(timeout=5)
        return client.post(PREFIX, json={**BODY, "enabled": False})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (first, second)))
    assert sorted(result.status_code for result in results) == [201, 409]
    rejected = next(result for result in results if result.status_code == 409)
    assert rejected.json()["error"]["code"] == "monitor_quota_exceeded"
    accepted = next(result.json() for result in results if result.status_code == 201)
    assert (
        first.delete(f"{PREFIX}/{accepted['id']}", params={"configuration_version": 1}).status_code
        == 204
    )
    create(first, enabled=False)
    with Session(database_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Monitor).where(Monitor.deleted_at.is_(None)))
            == 10
        )
        assert db.scalar(select(func.count()).select_from(Monitor)) == 11


def test_global_quota_serializes_create_against_resume(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    creator, _ = client_factory()
    resumer, _ = client_factory()
    paused = create(resumer, enabled=False)
    with Session(database_engine) as db:
        for group in range(10):
            user = User(
                email=f"quota{group}@example.com",
                password_hash="unused",
                email_verified_at=now_utc(),
            )
            db.add(user)
            db.flush()
            seed(db, user.id, 9 if group == 9 else 10)
    barrier = Barrier(2)

    def attempt(resume: bool) -> httpx.Response:
        barrier.wait(timeout=5)
        if resume:
            return resumer.patch(
                f"{PREFIX}/{paused['id']}", json={"configuration_version": 1, "enabled": True}
            )
        return creator.post(PREFIX, json=BODY)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (False, True)))
    assert sum(result.status_code in (200, 201) for result in results) == 1
    assert sum(result.status_code == 409 for result in results) == 1
    rejected = next(result for result in results if result.status_code == 409)
    assert rejected.json()["error"]["code"] == "enabled_monitor_quota_exceeded"
    with Session(database_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Monitor).where(Monitor.enabled.is_(True)))
            == 100
        )
    winner = resumer if results[1].status_code == 200 else creator
    result = next(result.json() for result in results if result.status_code in (200, 201))
    assert (
        winner.patch(
            f"{PREFIX}/{result['id']}",
            json={
                "configuration_version": result["configuration_version"],
                "name": "Rename at capacity",
            },
        ).status_code
        == 200
    )
    assert (
        winner.patch(
            f"{PREFIX}/{result['id']}",
            json={"configuration_version": result["configuration_version"] + 1, "enabled": False},
        ).status_code
        == 200
    )
    create(creator)


def test_concurrent_edits_accept_only_one_version(client_factory: ClientFactory) -> None:
    first, owner = client_factory()
    second, _ = client_factory(user_id=owner)
    monitor = create(first)
    barrier = Barrier(2)

    def attempt(pair: tuple[TestClient, str]) -> httpx.Response:
        client, name = pair
        barrier.wait(timeout=5)
        return client.patch(
            f"{PREFIX}/{monitor['id']}", json={"configuration_version": 1, "name": name}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ((first, "First"), (second, "Second"))))
    assert sorted(result.status_code for result in results) == [200, 409]
    winner = next(result.json() for result in results if result.status_code == 200)
    assert first.get(f"{PREFIX}/{monitor['id']}").json() == winner


def test_database_constraints_and_monitor_migration_preserve_accounts(
    client_factory: ClientFactory, database_engine: Engine
) -> None:
    _, owner = client_factory()
    with Session(database_engine) as db:
        row = seed(db, owner, 1)[0]
        for changes in (
            {"interval_seconds": 59},
            {"timeout_seconds": 11},
            {"expected_status": 600},
            {"method": "POST"},
            {"name": " "},
            {"configuration_version": 0},
            {"deleted_at": now_utc()},
            {"enabled": False},
            {"user_id": uuid4()},
        ):
            with pytest.raises(IntegrityError), db.begin_nested():
                db.execute(update(Monitor).where(Monitor.id == row.id).values(**changes))
        db.rollback()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "a4c16df5c2ab")
        assert connection.scalar(select(func.count()).select_from(User)) == 1
        connection.commit()
        command.upgrade(config, "head")
        assert connection.scalar(select(func.count()).select_from(User)) == 1
        assert connection.scalar(select(func.count()).select_from(Monitor)) == 0


def test_invalid_input_and_monitor_urls_never_leak_into_logs(
    client_factory: ClientFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    client, _ = client_factory()
    canary = "monitor-query-secret-canary"
    created = create(client, url=f"https://example.com/?key={canary}")
    assert client.get(f"{PREFIX}/{created['id']}").status_code == 200
    invalid = client.post(PREFIX, json={**BODY, "url": f"https://user:{canary}@example.com"})
    assert invalid.status_code == 422 and canary not in invalid.text
    assert invalid.json()["request_id"] == invalid.headers["x-request-id"]
    assert canary not in capsys.readouterr().out
