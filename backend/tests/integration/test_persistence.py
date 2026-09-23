from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_database_engine, get_session
from app.factory import create_app

pytestmark = pytest.mark.integration
BACKEND = Path(__file__).resolve().parents[2]


def test_real_connection_and_utc(database_settings: Settings) -> None:
    engine = create_database_engine(database_settings)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
            assert connection.scalar(text("SHOW timezone")) == "UTC"
            assert connection.scalar(text("SHOW statement_timeout")) == "5s"
            assert connection.scalar(text("SHOW lock_timeout")) == "3s"
    finally:
        engine.dispose()


def test_readiness_with_real_postgresql(database_settings: Settings) -> None:
    app = create_app(database_settings)
    with TestClient(app) as client:
        assert client.get("/health/ready").json() == {"status": "ok"}
        assert app.state.engine.pool.checkedout() == 0


def test_session_dependency_closes_uncommitted_work(database_settings: Settings) -> None:
    app = create_app(database_settings)
    with TestClient(app):
        request = Request({"type": "http", "app": app})
        dependency = get_session(request)
        session = next(dependency)
        session.execute(text("CREATE TEMP TABLE unfinished (id integer)"))
        assert app.state.engine.pool.checkedout() == 1
        dependency.close()
        assert app.state.engine.pool.checkedout() == 0
        with app.state.engine.connect() as connection:
            assert connection.scalar(text("SELECT to_regclass('pg_temp.unfinished')")) is None


def test_clean_database_migration_roundtrip(database_engine: Engine) -> None:
    output = StringIO()
    config = Config(str(BACKEND / "alembic.ini"), stdout=output)
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        assert inspect(connection).get_table_names() == []
        connection.commit()
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) == {
            "alembic_version",
            "users",
            "sessions",
            "auth_tokens",
            "rate_limit_buckets",
        }
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a4c16df5c2ab"
        connection.commit()
        command.current(config, check_heads=True)
        command.check(config)
        command.upgrade(config, "head")
        connection.commit()
        command.downgrade(config, "base")
        assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 0
        connection.commit()
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a4c16df5c2ab"
    assert "a4c16df5c2ab" in output.getvalue()


def test_session_commits_and_rollbacks_stay_inside_outer_transaction(
    database_engine: Engine,
) -> None:
    with database_engine.begin() as connection:
        connection.execute(text("CREATE TABLE fixture_values (value integer NOT NULL)"))
    with database_engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            session.execute(text("INSERT INTO fixture_values VALUES (1)"))
            session.commit()
            session.execute(text("INSERT INTO fixture_values VALUES (2)"))
            session.rollback()
            assert session.scalar(text("SELECT count(*) FROM fixture_values")) == 1
        outer.rollback()
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM fixture_values")) == 0


def test_isolated_session_fixture(database_session: Session) -> None:
    schema = database_session.scalar(text("SELECT current_schema()"))
    assert schema.startswith("test_")
    database_session.execute(text("CREATE TABLE fixture_values (id integer PRIMARY KEY)"))
    database_session.commit()
    assert database_session.scalar(text("SELECT count(*) FROM fixture_values")) == 0
