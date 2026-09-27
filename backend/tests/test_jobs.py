import asyncio
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.logging import configure_logging
from app.jobs import tasks
from app.jobs.configuration import (
    DISPATCH_TASK,
    MAINTENANCE_QUEUE,
    PROBE_QUEUE,
    PROBE_TASK,
    create_celery,
)


def test_worker_configuration_uses_bounded_json_late_acknowledged_tasks_without_results() -> None:
    app = create_celery(Settings(environment="test"))
    try:
        config = app.conf
        assert config.task_acks_late and config.task_reject_on_worker_lost
        assert config.task_acks_on_failure_or_timeout
        assert config.task_ignore_result and not config.task_store_errors_even_if_ignored
        assert config.result_backend is None and config.accept_content == ["json"]
        assert config.task_serializer == "json" and config.task_publish_retry is False
        assert config.task_routes[PROBE_TASK] == {"queue": PROBE_QUEUE}
        assert config.worker_concurrency == 2 and config.worker_prefetch_multiplier == 1
        assert config.worker_cancel_long_running_tasks_on_connection_loss
        assert config.task_time_limit < 60 < config.broker_transport_options["visibility_timeout"]
        assert not config.worker_enable_remote_control
        assert config.task_routes[DISPATCH_TASK] == {"queue": MAINTENANCE_QUEUE}
        assert config.beat_schedule["dispatch-monitors"]["schedule"] == 5
        assert config.beat_schedule["dispatch-monitors"]["options"]["expires"] == 5
    finally:
        app.close()


def test_broker_settings_reject_other_transports_and_tls_verification_bypass() -> None:
    for value in [
        "memory://",
        "amqp://host/0",
        "redis://host",
        "redis://host/99",
        "rediss://host/0?ssl_cert_reqs=none",
        "redis://host:0/0",
    ]:
        with pytest.raises(ValidationError):
            Settings(broker_url=SecretStr(value))
    import ssl

    app = create_celery(Settings(broker_url=SecretStr("rediss://example.com:6380/0")))
    assert app.conf.broker_use_ssl["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    app.close()


def test_task_database_failure_is_sanitized_and_never_executes_a_probe(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = Mock()
    probe = Mock()
    monkeypatch.setattr(tasks, "create_database_engine", lambda settings: engine)
    monkeypatch.setattr(tasks, "execute_spec", probe)
    monkeypatch.setattr(
        tasks,
        "claim_run",
        Mock(
            side_effect=OperationalError("secret SQL", {}, RuntimeError("database-password-canary"))
        ),
    )
    configure_logging("DEBUG")
    tasks.execute_job(str(uuid4()))
    assert not probe.called and engine.dispose.called
    output = capsys.readouterr().out
    assert "job_deferred" in output and "persistence_unavailable" in output
    assert "secret SQL" not in output and "database-password-canary" not in output


def test_invalid_job_payload_is_not_logged_or_used_for_database_access(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = Mock()
    monkeypatch.setattr(tasks, "create_database_engine", engine)
    configure_logging("INFO")
    tasks.execute_job("https://private.test/?token=payload-canary")
    assert not engine.called
    assert "payload-canary" not in capsys.readouterr().out


def test_each_task_has_a_separate_engine_and_explicit_async_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engines = [Mock(), Mock()]
    monkeypatch.setattr(tasks, "create_database_engine", Mock(side_effect=engines))
    monkeypatch.setattr(tasks, "claim_run", Mock(return_value=Mock(assertions=())))
    monkeypatch.setattr(tasks, "finish_run", Mock(return_value=uuid4()))
    probe = Mock()
    from app.monitoring import runs

    async def execute(*args: object, **kwargs: object) -> object:
        assert asyncio.get_running_loop().is_running()
        assert kwargs["assertions"] == ()
        return probe

    monkeypatch.setattr(runs, "execute_probe", execute)
    for _ in engines:
        tasks.execute_job(str(uuid4()))
    assert all(engine.dispose.call_count == 1 for engine in engines)
