import logging
import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.factory import create_app


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
    return create_app(Settings(environment="test"))
