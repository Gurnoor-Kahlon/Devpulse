from email.message import EmailMessage
from email.utils import format_datetime
from html import escape
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from app.notifications.delivery import DeliverySpec


def incident_message(settings: Settings, spec: "DeliverySpec") -> EmailMessage:
    opened = spec.transition == "opened"
    title = "Incident confirmed" if opened else "Recovery observed"
    link = f"{settings.app_origin}/incidents/{spec.incident_id}"
    lines = [
        title,
        f"Monitor: {spec.monitor_name}",
        f"First failure: {spec.started_at.isoformat()}",
        f"Confirmed: {spec.confirmed_at.isoformat()}",
    ]
    if spec.resolved_at:
        lines.append(f"Recovery observed: {spec.resolved_at.isoformat()}")
    lines.extend(
        [
            "This email describes a recorded transition. Open the incident for its current status.",
            f"View incident: {link}",
            f"Email preferences: {settings.app_origin}/notifications",
        ]
    )
    message = EmailMessage()
    message["From"] = str(settings.mail_from)
    message["To"] = spec.destination
    message["Date"] = format_datetime(
        spec.confirmed_at if opened else (spec.resolved_at or spec.confirmed_at)
    )
    message["Subject"] = f"DevPulse: {title.lower()}"
    message["Message-ID"] = f"<{spec.id}@notifications.devpulse.invalid>"
    message.set_content("\n\n".join(lines) + "\n")
    message.add_alternative(
        '<!doctype html><html lang="en"><body>'
        + "".join(f"<p>{escape(line)}</p>" for line in lines[: 5 if spec.resolved_at else 4])
        + "<p>This email describes a recorded transition. "
        "Open the incident for its current status.</p>"
        + f'<p><a href="{escape(link, quote=True)}">View incident</a></p>'
        + f'<p><a href="{escape(settings.app_origin, quote=True)}/notifications">'
        "Email preferences</a></p>" + "</body></html>",
        subtype="html",
    )
    return message
