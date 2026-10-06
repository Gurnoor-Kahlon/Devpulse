"""Showcase configuration must never target normal app data."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location(
    "showcase_control", ROOT / "containers/showcase/control.py"
)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


@pytest.mark.parametrize(
    ("flag", "environment", "host", "database"),
    [
        ("0", "test", "postgres", "devpulse_test"),
        ("1", "production", "postgres", "devpulse_test"),
        ("1", "development", "postgres", "devpulse_test"),
        ("1", "test", "localhost", "devpulse_test"),
        ("1", "test", "postgres", "devpulse"),
    ],
)
def test_refuses_non_showcase_database_before_connecting(
    monkeypatch, flag, environment, host, database
):
    monkeypatch.setenv("DEVPULSE_SHOWCASE", flag)
    monkeypatch.setattr(
        control,
        "load_settings",
        lambda: SimpleNamespace(
            environment=environment,
            database_url=SecretStr(f"postgresql+psycopg://devpulse@{host}/{database}"),
        ),
    )

    def forbidden(_settings):
        pytest.fail("Unsafe configuration reached the database connection.")

    monkeypatch.setattr(control, "create_database_engine", forbidden)
    with pytest.raises(ValueError, match="disposable Docker"):
        control.main("seed", "00000000-0000-0000-0000-000000000000")
