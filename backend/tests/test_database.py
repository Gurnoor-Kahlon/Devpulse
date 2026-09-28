import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import Column, Integer, MetaData, Table, UniqueConstraint
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.base import Base
from app.factory import create_app


@pytest.fixture
def unavailable_url() -> Iterator[str]:
    # Reserve a loopback port without listening: no unrelated service can occupy it.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        yield (
            "postgresql+psycopg://devpulse:database-redaction-canary@127.0.0.1:"
            f"{reservation.getsockname()[1]}/devpulse_test"
        )


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///test.db",
        "postgresql://user@localhost/db",
        "postgresql+psycopg://",
        "postgresql+psycopg://user@localhost:99999/db",
    ],
)
def test_database_settings_reject_unsupported_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr(url))


def test_database_url_is_redacted() -> None:
    settings = Settings(database_url=SecretStr("postgresql+psycopg://user:secret@localhost/db"))
    assert "user:secret" not in repr(settings)
    assert "user:secret" not in settings.model_dump_json()


def test_database_outage_preserves_liveness_and_sanitizes_readiness(
    unavailable_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(Settings(environment="test", database_url=SecretStr(unavailable_url)))
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_unavailable"
        assert response.json()["request_id"] == response.headers["x-request-id"]
        failed_auth = client.get("/api/v1/auth/csrf")
        assert failed_auth.status_code == 503
        assert "database-redaction-canary" not in failed_auth.text
    output = capsys.readouterr().out + response.text
    assert "database-redaction-canary" not in output
    assert "psycopg" not in output


def test_failed_query_is_sanitized_and_pool_disposed(unavailable_url: str) -> None:
    app = create_app(Settings(database_url=SecretStr(unavailable_url)))
    with TestClient(app) as client:
        engine = app.state.engine
        original_pool = engine.pool
        engine.connect = Mock(
            side_effect=OperationalError("SELECT secret", {}, Exception("secret"))
        )
        assert client.get("/health/ready").status_code == 503
    assert app.state.ready is False
    assert engine.pool is not original_pool


def test_metadata_has_conventions_and_only_authorized_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "sessions",
        "auth_tokens",
        "rate_limit_buckets",
        "monitors",
        "check_runs",
        "checks",
        "incidents",
        "assertions",
        "notification_channels",
        "notification_deliveries",
    }
    table = Table(
        "example",
        MetaData(naming_convention=Base.metadata.naming_convention),
        Column("id", Integer, primary_key=True),
        Column("value", Integer, index=True),
        UniqueConstraint("value"),
    )
    assert table.primary_key.name == "pk_example"
    assert {index.name for index in table.indexes} == {"ix_example_value"}
    assert "uq_example_value" in {constraint.name for constraint in table.constraints}


@pytest.mark.parametrize("offline", [False, True])
def test_migration_cli_with_unavailable_database_is_safe(
    unavailable_url: str, offline: bool
) -> None:
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    if offline:
        command.append("--sql")
    result = subprocess.run(
        command,
        env={**os.environ, "DEVPULSE_DATABASE_URL": unavailable_url},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = result.stdout + result.stderr
    assert "database-redaction-canary" not in output
    assert "Traceback" not in output
    if offline:
        assert result.returncode == 0
        assert "CREATE TABLE alembic_version" in output
    else:
        assert result.returncode != 0
        assert "Database migration failed" in output
