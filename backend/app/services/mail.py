import smtplib
import ssl
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import logger
from app.core.security import now_utc
from app.models.auth import AuthToken
from app.services.auth import Purpose


def send_auth_email(settings: Settings, destination: str, purpose: Purpose, token: str) -> None:
    message = EmailMessage()
    message["From"] = str(settings.mail_from)
    message["To"] = destination
    verification = purpose == "verification"
    message["Subject"] = (
        "Verify your DevPulse email" if verification else "Reset your DevPulse password"
    )
    action = "verify your email address" if verification else "reset your password"
    lifetime = "24 hours" if verification else "30 minutes"
    message.set_content(
        f"Use this single-use code to {action}:\n\n{token}\n\n"
        f"It expires in {lifetime}. If you did not request this, ignore this email.\n"
    )
    connection: smtplib.SMTP
    if settings.smtp_mode == "tls":
        connection = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=5, context=ssl.create_default_context()
        )
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5)
    with connection as smtp:
        if settings.smtp_mode == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username and settings.smtp_password:
            smtp.login(
                settings.smtp_username.get_secret_value(), settings.smtp_password.get_secret_value()
            )
        smtp.send_message(message)


def deliver_token(
    db: Session, settings: Settings, destination: str, purpose: Purpose, token_id: UUID, raw: str
) -> None:
    """Called after commit; SMTP never holds a database transaction open."""
    try:
        send_auth_email(settings, destination, purpose, raw)
    except (OSError, smtplib.SMTPException):
        logger.warning(
            "auth_email_failed",
            extra={"event": "auth_email_failed", "error_code": "smtp_unavailable"},
        )
        # A failed/ambiguous delivery is not usable; resend creates a fresh token.
        db.execute(update(AuthToken).where(AuthToken.id == token_id).values(consumed_at=now_utc()))
        db.commit()
