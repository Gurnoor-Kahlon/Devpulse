import base64

import pytest
from pydantic import ValidationError

from app.core.errors import ApiError
from app.schemas.monitors import MonitorCreate, MonitorUpdate
from app.services.monitors import decode_cursor


def test_monitor_settings_boundaries_and_normalization() -> None:
    low = MonitorCreate(
        name=" x ",
        url="https://EXAMPLE.com",
        expected_status=200,
        timeout_seconds=1,
        interval_seconds=60,
    )
    high = MonitorCreate(
        name="x" * 100,
        url="http://example.com/" + "x" * 2029,
        method="HEAD",
        expected_status=599,
        timeout_seconds=10,
        interval_seconds=86400,
        enabled=False,
    )
    assert low.name == "x" and low.url == "https://example.com/"
    assert high.enabled is False and len(high.url) == 2048


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "  "},
        {"name": "x" * 101},
        {"url": "https://example.com/" + "x" * 2048},
        {"method": "POST"},
        {"expected_status": 199},
        {"expected_status": 600},
        {"timeout_seconds": 0},
        {"timeout_seconds": 11},
        {"interval_seconds": 59},
        {"interval_seconds": 86401},
        {"interval_seconds": True},
        {"timeout_seconds": "5"},
        {"enabled": "false"},
        {"headers": {"Authorization": "unsupported"}},
        {"user_id": "cannot-set-owner"},
    ],
)
def test_invalid_monitor_settings(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MonitorCreate.model_validate({"name": "API", "url": "https://example.com", **changes})


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "https:example.com",
        "https://",
        "https://[invalid]/",
        "https://user:secret@example.com",
        "https://@example.com",
        "https://example.com:8080",
        "https://example.com:0",
        "https://example.com/#fragment",
        "https://example.com/#",
        "https://example.com/path\n",
        "https://example.com/a b",
        "https://example.com\\@localhost",
    ],
)
def test_unsupported_url_syntax(url: str) -> None:
    with pytest.raises(ValidationError):
        MonitorCreate(name="API", url=url)


def test_patch_requires_version_and_non_null_settings() -> None:
    for body in (
        {"name": "new"},
        {"configuration_version": 0, "name": "new"},
        {"configuration_version": 1},
        {"configuration_version": 1, "name": None},
        {"configuration_version": 1, "current_state": "operational"},
    ):
        with pytest.raises(ValidationError):
            MonitorUpdate.model_validate(body)
    patch = MonitorUpdate(configuration_version=1, enabled=False)
    assert patch.model_dump(exclude_unset=True) == {"configuration_version": 1, "enabled": False}


def test_cursor_rejects_malformed_or_timezone_free_values() -> None:
    values = [
        "%%%",
        "not-a-cursor",
        base64.urlsafe_b64encode(
            b"2026-01-01T00:00:00|00000000-0000-0000-0000-000000000001"
        ).decode(),
    ]
    for value in values:
        with pytest.raises(ApiError) as error:
            decode_cursor(value)
        assert error.value.code == "invalid_cursor"
