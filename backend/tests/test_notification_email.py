from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.jobs.configuration import (
    MAINTENANCE_QUEUE,
    NOTIFICATION_DISPATCH_TASK,
    NOTIFICATION_QUEUE,
    NOTIFICATION_TASK,
    RETENTION_TASK,
    create_celery,
)
from app.notifications.delivery import DeliverySpec
from app.notifications.email import incident_message


def spec(transition="opened"):
    now = datetime(2026, 9, 28, tzinfo=UTC)
    return DeliverySpec(
        uuid4(),
        uuid4(),
        "recipient@example.com",
        uuid4(),
        transition,
        '<script>alert("fixture")</script>\nBcc: injected@example.com',
        now,
        now,
        now if transition == "resolved" else None,
    )


@pytest.mark.parametrize("transition", ["opened", "resolved"])
def test_safe_multipart_templates_and_stable_message_id(transition):
    delivery = spec(transition)
    settings = Settings(app_origin="https://devpulse.example.com")
    message = incident_message(settings, delivery)
    assert message["To"] == "recipient@example.com"
    assert message["Bcc"] is None
    assert message["Subject"] == (
        "DevPulse: incident confirmed" if transition == "opened" else "DevPulse: recovery observed"
    )
    assert message["Message-ID"] == incident_message(settings, delivery)["Message-ID"]
    text = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert str(delivery.incident_id) in text and "/notifications" in text
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "https://devpulse.example.com/incidents/" in html
    assert str(delivery.lease_token) not in str(message)


def test_notifications_and_retention_route_away_from_probe_workers():
    app = create_celery(Settings(environment="test"))
    try:
        assert app.conf.task_routes[NOTIFICATION_TASK] == {"queue": NOTIFICATION_QUEUE}
        assert app.conf.task_routes[NOTIFICATION_DISPATCH_TASK] == {"queue": MAINTENANCE_QUEUE}
        assert app.conf.task_routes[RETENTION_TASK] == {"queue": MAINTENANCE_QUEUE}
        assert app.conf.beat_schedule["dispatch-notifications"]["schedule"] == 5
        assert app.conf.beat_schedule["prune-history"]["schedule"] == 60
    finally:
        app.close()


@pytest.mark.parametrize("data_rejected", [False, True])
def test_smtp_teardown_does_not_mask_known_acceptance_or_data_rejection(monkeypatch, data_rejected):
    import smtplib
    from unittest.mock import Mock

    from app.services.mail import send_message

    smtp = Mock()
    smtp.quit.side_effect = smtplib.SMTPResponseException(500, b"quit-error-canary")
    if data_rejected:
        smtp.send_message.side_effect = smtplib.SMTPDataError(451, b"data-error-canary")
    monkeypatch.setattr(smtplib, "SMTP", Mock(return_value=smtp))
    settings = Settings()
    message = incident_message(settings, spec())
    if data_rejected:
        with pytest.raises(smtplib.SMTPDataError):
            send_message(settings, message)
    else:
        send_message(settings, message)
    smtp.send_message.assert_called_once()
    smtp.close.assert_called_once()
