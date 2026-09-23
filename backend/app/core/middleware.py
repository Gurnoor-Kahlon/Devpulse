import logging
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.logging import logger, request_id_context


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started_at = perf_counter()
        status_code = 500
        response_started = False
        failed = False

        async def send_response(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers.setdefault("Cache-Control", "no-store")
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception:
            failed = True
            if response_started:
                # Headers cannot be replaced after delivery. Abort without exposing the cause.
                raise RuntimeError("Response processing failed.") from None
            response = error_response(
                request_id, 500, "internal_error", "An unexpected error occurred. Please try again."
            )
            await response(scope, receive, send_response)
        finally:
            try:
                method = scope["method"]
                if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
                    method = "OTHER"
                event = "request_failed" if failed or status_code >= 500 else "request_completed"
                logger.log(
                    logging.ERROR if event == "request_failed" else logging.INFO,
                    event,
                    extra={
                        "event": event,
                        "method": method,
                        "route": getattr(scope.get("route"), "path", "<unmatched>"),
                        "status_code": status_code,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                        **({"error_code": "internal_error"} if failed else {}),
                    },
                )
            finally:
                request_id_context.reset(token)
