from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, field_validator


class Payload(BaseModel):
    password: Annotated[str, Field(min_length=32)]


class CheckedPayload(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def reject(cls, value: str) -> str:
        raise ValueError(f"Private validation context: {value}")


def test_validation_omits_input_and_preserves_useful_field_errors(application: FastAPI) -> None:
    @application.post("/testing/payload")
    async def validate(payload: Payload) -> Payload:
        return payload

    with TestClient(application) as client:
        response = client.post("/testing/payload", json={"password": "validation-canary"})
    assert response.status_code == 422
    body = response.json()
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["error"]["fields"] == [
        {
            "field": "body.password",
            "code": "string_too_short",
            "message": "This value is too short.",
        }
    ]
    assert "validation-canary" not in response.text
    assert "input" not in body["error"]["fields"][0]


def test_custom_validation_context_cannot_leak_into_errors(application: FastAPI) -> None:
    @application.post("/testing/checked")
    async def validate(payload: CheckedPayload) -> CheckedPayload:
        return payload

    with TestClient(application) as client:
        response = client.post("/testing/checked", json={"value": "validator-context-canary"})
    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["code"] == "invalid_value"
    assert "validator-context-canary" not in response.text
    assert "Private validation context" not in response.text


def test_malformed_json_uses_the_same_error_contract(application: FastAPI) -> None:
    @application.post("/testing/payload")
    async def validate(payload: Payload) -> Payload:
        return payload

    with TestClient(application) as client:
        response = client.post(
            "/testing/payload",
            content='{"password": "malformed-body-canary',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["code"] == "json_invalid"
    assert "malformed-body-canary" not in response.text


def test_routing_errors_are_consistent_and_preserve_allow_header(application: FastAPI) -> None:
    with TestClient(application) as client:
        missing = client.get("/not-a-route")
        wrong_method = client.post("/health/live")
    assert missing.status_code == 404
    assert missing.json()["error"] == {"code": "not_found", "message": "Not Found"}
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"
    assert "GET" in wrong_method.headers["allow"]
    for response in (missing, wrong_method):
        assert response.json()["request_id"] == response.headers["x-request-id"]


def test_http_exception_details_are_private_but_retry_headers_survive(application: FastAPI) -> None:
    @application.get("/testing/unavailable")
    async def unavailable() -> None:
        raise HTTPException(
            status_code=503, detail="private-service-canary", headers={"Retry-After": "5"}
        )

    with TestClient(application) as client:
        response = client.get("/testing/unavailable")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert "private-service-canary" not in response.text


def test_response_validation_failure_is_a_safe_internal_error(application: FastAPI) -> None:
    @application.get("/testing/bad-response", response_model=Payload)
    async def bad_response() -> dict[str, str]:
        return {"password": "response-canary"}

    with TestClient(application) as client:
        response = client.get("/testing/bad-response")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "response-canary" not in response.text
