from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.factory import create_app


def test_health_endpoints_follow_application_lifecycle(application: FastAPI) -> None:
    assert application.state.ready is False
    with TestClient(application) as client:
        for endpoint in ("/health/live", "/health/ready"):
            response = client.get(endpoint)
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            assert response.headers["cache-control"] == "no-store"
            assert UUID(response.headers["x-request-id"]).version == 4
    assert application.state.ready is False


def test_readiness_does_not_claim_startup_without_a_lifespan(application: FastAPI) -> None:
    client = TestClient(application)
    try:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_unavailable"
        assert response.json()["request_id"] == response.headers["x-request-id"]
    finally:
        client.close()


def test_factory_instances_do_not_share_runtime_state() -> None:
    first = create_app(Settings(environment="test"))
    second = create_app(Settings(environment="test"))
    with TestClient(first):
        assert first.state.ready is True
        assert second.state.ready is False


@pytest.mark.parametrize(
    "settings",
    [Settings(environment="production"), Settings(api_docs_enabled=False)],
)
def test_docs_can_be_disabled_without_disabling_health(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health/live").status_code == 200


def test_openapi_documents_health_and_actual_error_models(application: FastAPI) -> None:
    with TestClient(application) as client:
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/health/live", "/health/ready"}
    ready_responses = schema["paths"]["/health/ready"]["get"]["responses"]
    assert ready_responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/HealthResponse"
    )
    for status in ("422", "500", "503"):
        assert ready_responses[status]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ErrorResponse"
        )
