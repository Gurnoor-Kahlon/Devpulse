import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.config import dictConfig

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("devpulse")

_EVENTS = {"application_started", "application_stopped", "request_completed", "request_failed"}
_FIELDS = {"method", "route", "status_code", "duration_ms", "environment", "error_code"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", None)
        known_event = isinstance(event, str) and event in _EVENTS
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "event": event if known_event else "server_error" if record.exc_info else "server_log",
        }
        if request_id := request_id_context.get():
            payload["request_id"] = request_id
        if record.name == "devpulse" and known_event:
            payload.update({key: record.__dict__[key] for key in _FIELDS if key in record.__dict__})
        # Free-form messages, exception text, and arbitrary extras may contain credentials.
        return json.dumps(payload, ensure_ascii=True, allow_nan=False)


def configure_logging(level: str) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                }
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "devpulse": {"handlers": [], "level": level, "propagate": True},
                "uvicorn": {"handlers": [], "level": "INFO", "propagate": True},
                "uvicorn.error": {"handlers": [], "level": "INFO", "propagate": True},
                # Raw access URLs may contain secrets; the middleware logs route templates instead.
                "uvicorn.access": {"handlers": [], "level": "CRITICAL", "propagate": False},
                "httpx": {"handlers": [], "level": "WARNING", "propagate": True},
                "httpcore": {"handlers": [], "level": "WARNING", "propagate": True},
            },
        }
    )
