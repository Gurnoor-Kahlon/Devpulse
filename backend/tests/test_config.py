import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import ConfigurationError, Settings, load_settings


def test_environment_overrides_dotenv_without_changing_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("DEVPULSE_LOG_LEVEL=WARNING\nDEVPULSE_API_DOCS_ENABLED=false\n")
    monkeypatch.setenv("DEVPULSE_LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=dotenv)
    assert settings.log_level == "DEBUG"
    assert settings.api_docs_enabled is False
    assert settings.environment == "development"


@pytest.mark.parametrize("field", ["ENVIRONMENT", "LOG_LEVEL", "API_DOCS_ENABLED"])
def test_invalid_configuration_fails_without_exposing_values(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    supplied = "configuration-redaction-canary"
    monkeypatch.setenv(f"DEVPULSE_{field}", supplied)
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert field.lower() in str(caught.value)
    assert supplied not in str(caught.value)
    assert caught.value.__suppress_context__


def test_server_entrypoint_fails_safely_for_invalid_configuration() -> None:
    supplied = "startup-redaction-canary"
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app"],
        env={**os.environ, "DEVPULSE_LOG_LEVEL": supplied},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "ConfigurationError" in result.stderr
    assert supplied not in result.stdout + result.stderr
