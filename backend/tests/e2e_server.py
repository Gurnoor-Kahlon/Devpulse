"""Disposable browser-test API; never use as an application entrypoint."""

import os
import sys
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from uuid import uuid4

import uvicorn
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import DemoPublication, Settings
from app.db.session import create_database_engine
from app.factory import create_app


def main() -> None:
    raw = os.environ.get("TEST_DATABASE_URL", "")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=SecretStr(raw),
        app_origin="http://localhost:3000",
        log_level="WARNING",
        smtp_host="127.0.0.1",
        smtp_port=1025,
        smtp_mode="plain",
        smtp_username=None,
        smtp_password=None,
    )
    if not (make_url(raw).database or "").endswith("_test"):
        raise ValueError("A dedicated database ending in _test is required.")
    schema = f"e2e_{uuid4().hex}"
    admin = create_database_engine(settings)
    engine = create_engine(
        raw,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": f"-c search_path={schema} -c timezone=UTC -c statement_timeout=5000",
        },
    )
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with engine.connect() as connection, patch.dict(Settings.model_config, {"env_file": None}):
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        if (
            os.environ.get("TEST_INCIDENT_FIXTURES") == "1"
            or os.environ.get("TEST_DASHBOARD_FIXTURES") == "1"
            or os.environ.get("TEST_MONITOR_HISTORY_FIXTURES") == "1"
            or os.environ.get("TEST_ASSERTION_FIXTURES") == "1"
            or os.environ.get("TEST_NOTIFICATION_FIXTURES") == "1"
            or os.environ.get("TEST_DEMO_FIXTURES") == "1"
        ):
            from tests.incident_browser_fixture import seed_incident_browser_fixture

            seed_incident_browser_fixture(
                engine,
                retain_monitor_history=(
                    os.environ.get("TEST_DASHBOARD_FIXTURES") == "1"
                    or os.environ.get("TEST_MONITOR_HISTORY_FIXTURES") == "1"
                    or os.environ.get("TEST_ASSERTION_FIXTURES") == "1"
                    or os.environ.get("TEST_NOTIFICATION_FIXTURES") == "1"
                    or os.environ.get("TEST_DEMO_FIXTURES") == "1"
                ),
                with_assertions=os.environ.get("TEST_ASSERTION_FIXTURES") == "1",
                with_notifications=os.environ.get("TEST_NOTIFICATION_FIXTURES") == "1",
                extra_manual_runs=20
                if os.environ.get("TEST_MONITOR_HISTORY_FIXTURES") == "1"
                else 0,
            )
        if os.environ.get("TEST_DEMO_FIXTURES") == "1":
            from sqlalchemy import select
            from sqlalchemy.orm import Session

            from app.models.monitor import Monitor

            with Session(engine) as db:
                monitor = db.scalars(select(Monitor)).one()
                settings = settings.model_copy(
                    update={
                        "demo_publications": (
                            DemoPublication(
                                owner_id=monitor.user_id,
                                monitor_id=monitor.id,
                                configuration_version=monitor.configuration_version,
                                slug="controlled-http",
                                label="Controlled HTTP endpoint",
                                controlled_failure=True,
                            ),
                        )
                    }
                )
        with patch("app.factory.create_database_engine", return_value=engine):
            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(settings),
                    host="127.0.0.1",
                    port=8000,
                    proxy_headers=False,
                    access_log=False,
                    log_config=None,
                )
            )

            def stop_on_input() -> None:
                sys.stdin.readline()
                server.should_exit = True

            Thread(target=stop_on_input, daemon=True).start()
            server.run()
    finally:
        engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never include a connection string or credentials in process output.
        print(
            "E2E API failed. Check the test database, migrations, and available ports.",
            file=sys.stderr,
        )
        sys.exit(1)
