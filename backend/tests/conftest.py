import logging
import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request

from app.core.config import Settings
from app.db.session import database_is_ready
from app.factory import create_app


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-integration", action="store_true", help="Run real PostgreSQL tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--run-integration"):
        skip = pytest.mark.skip(reason="Use --run-integration with TEST_DATABASE_URL")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolate_configuration(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in tuple(os.environ):
        if key.startswith("DEVPULSE_"):
            monkeypatch.delenv(key)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    names = ("", "devpulse", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "httpcore")
    loggers = [logging.getLogger(name) for name in names]
    original = [(log, log.handlers[:], log.level, log.propagate, log.disabled) for log in loggers]
    yield
    for log, handlers, level, propagate, disabled in original:
        log.handlers = handlers
        log.setLevel(level)
        log.propagate = propagate
        log.disabled = disabled


@pytest.fixture
def application() -> FastAPI:
    application = create_app(Settings(environment="test"))

    def startup_ready(request: Request) -> bool:
        return bool(request.app.state.ready)

    # Unit HTTP tests isolate PostgreSQL; integration tests use the real dependency.
    application.dependency_overrides[database_is_ready] = startup_ready
    return application
