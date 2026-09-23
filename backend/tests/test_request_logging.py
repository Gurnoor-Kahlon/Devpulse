import asyncio
import json
import logging
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from app.core.logging import configure_logging, request_id_context
from app.core.middleware import RequestContextMiddleware


def test_concurrent_requests_keep_separate_ids_and_clear_context(application: FastAPI) -> None:
    @application.get("/testing/context")
    async def context() -> dict[str, str | None]:
        before = request_id_context.get()
        await asyncio.sleep(0)
        return {"before": before, "after": request_id_context.get()}

    async def issue_requests() -> list[httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            responses = await asyncio.gather(
                *(
                    client.get("/testing/context", headers={"X-Request-ID": "untrusted-id"})
                    for _ in range(8)
                )
            )
        assert request_id_context.get() is None
        return responses

    with TestClient(application):
        responses = asyncio.run(issue_requests())
    ids = [response.headers["x-request-id"] for response in responses]
    assert len(set(ids)) == len(responses)
    for response, request_id in zip(responses, ids, strict=True):
        assert UUID(request_id).version == 4
        assert response.json() == {"before": request_id, "after": request_id}
    assert request_id_context.get() is None


def test_request_logs_and_internal_errors_exclude_sensitive_values(
    application: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    @application.post("/testing/private/{value}")
    async def fail(request: Request, value: str) -> None:
        raise RuntimeError((await request.body()).decode())

    canaries = [
        "path-canary",
        "query-canary",
        "body-canary",
        "auth-canary",
        "cookie-canary",
        "id-canary",
    ]
    with TestClient(application) as client:
        response = client.post(
            "/testing/private/path-canary?token=query-canary",
            json={"password": "body-canary"},
            headers={
                "Authorization": "Bearer auth-canary",
                "Cookie": "session=cookie-canary",
                "X-Request-ID": "id-canary",
            },
        )
        missing = client.get("/unmatched-path-canary?key=query-canary")
    output = capsys.readouterr().out
    for canary in [*canaries, "unmatched-path-canary"]:
        assert canary not in output + response.text + missing.text
    records = [json.loads(line) for line in output.splitlines()]
    failed = next(record for record in records if record["event"] == "request_failed")
    assert response.status_code == 500
    assert failed["request_id"] == response.headers["x-request-id"]
    assert failed["route"] == "/testing/private/{value}"
    assert failed["status_code"] == 500
    assert failed["level"] == "ERROR"
    assert failed["duration_ms"] >= 0
    assert failed["error_code"] == "internal_error"
    assert failed["timestamp"].endswith("Z")
    assert (
        next(record for record in records if record.get("status_code") == 404)["route"]
        == "<unmatched>"
    )


def test_logging_configuration_deduplicates_handlers_and_suppresses_raw_server_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    logging.getLogger("uvicorn.access").info("GET /?token=access-canary")
    try:
        raise RuntimeError("exception-canary")
    except RuntimeError:
        logging.getLogger("uvicorn.error").exception(
            "message-canary", extra={"token": "extra-canary"}
        )
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    assert json.loads(output)["event"] == "server_error"
    for canary in ("access-canary", "exception-canary", "message-canary", "extra-canary"):
        assert canary not in output


def test_errors_after_headers_abort_without_sending_a_second_response() -> None:
    messages: list[Message] = []

    async def broken_app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"partial", "more_body": True})
        raise RuntimeError("late-error-canary")

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    async def send(message: Message) -> None:
        messages.append(message)

    with pytest.raises(RuntimeError, match="^Response processing failed\\.$") as caught:
        asyncio.run(
            RequestContextMiddleware(broken_app)({"type": "http", "method": "GET"}, receive, send)
        )
    assert caught.value.__suppress_context__
    assert sum(message["type"] == "http.response.start" for message in messages) == 1
    assert request_id_context.get() is None
