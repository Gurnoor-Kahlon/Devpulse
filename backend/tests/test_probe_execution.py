import asyncio
import ssl
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import Settings
from app.monitoring.executor import execute_probe
from app.monitoring.policy import DestinationPolicy
from app.monitoring.transport import ProbeTransport
from tests.probe_fixtures import fixture_resolver, fixture_server, fixture_settings


@pytest.mark.parametrize(
    "path,expected,code",
    [
        ("/ok", 200, None),
        ("/fail", 200, "unexpected_status"),
        ("/fail", 503, None),
        ("/redirect", 302, None),
        ("/redirect", 200, "unexpected_status"),
        ("/json", 200, None),
        ("/limit", 200, None),
        ("/large", 200, "response_too_large"),
        ("/chunked-large", 200, "response_too_large"),
        ("/gzip", 200, None),
        ("/gzip-limit", 200, None),
        ("/deflate", 200, None),
        ("/unsupported", 200, "invalid_body"),
        ("/bomb", 200, "response_too_large"),
        ("/bad-gzip", 200, "invalid_body"),
        ("/truncated-gzip", 200, "invalid_body"),
        ("/malformed", 200, "invalid_response"),
        ("/truncated", 200, "invalid_response"),
        ("/headers", 200, "invalid_response"),
    ],
)
def test_real_http_responses_are_bounded_and_evaluated(
    path: str, expected: int, code: str | None
) -> None:
    with fixture_server() as (server, _):
        result = asyncio.run(
            execute_probe(
                f"http://127.0.0.1:{server.server_port}{path}",
                "GET",
                expected,
                3,
                fixture_settings(server),
            )
        )
        assert result.error_code == code
        assert result.outcome == ("success" if code is None else "failure")
        assert result.finished_at >= result.started_at and result.duration_ms > 0
        assert len(server.hits) == 1  # Redirects never cause another request.
        assert "response-secret-canary" not in repr(result)


def test_head_does_not_consume_the_advertised_body() -> None:
    with fixture_server() as (server, _):
        result = asyncio.run(
            execute_probe(
                f"http://127.0.0.1:{server.server_port}/large",
                "HEAD",
                200,
                2,
                fixture_settings(server),
            )
        )
        assert result.outcome == "success"
        assert server.hits[0][0] == "HEAD"


@pytest.mark.parametrize("path", ["/slow", "/drip"])
def test_total_deadline_covers_headers_and_streaming_body(path: str) -> None:
    with fixture_server() as (server, _):
        clock = time.monotonic()
        result = asyncio.run(
            execute_probe(
                f"http://127.0.0.1:{server.server_port}{path}",
                "GET",
                200,
                1,
                fixture_settings(server),
            )
        )
        assert result.error_code == "timeout"
        assert time.monotonic() - clock < 1.8


def test_dns_resolution_is_inside_the_total_deadline() -> None:
    async def slow(host: str, port: int) -> list[str]:
        await asyncio.sleep(5)
        return ["8.8.8.8"]

    clock = time.monotonic()
    result = asyncio.run(
        execute_probe("https://example.com", "GET", 200, 1, Settings(), resolver=slow)
    )
    assert result.error_code == "timeout" and time.monotonic() - clock < 1.8


def test_numeric_connection_does_not_resolve_a_second_time_and_ignores_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with fixture_server() as (server, _):
        resolver = AsyncMock(side_effect=[["127.0.0.1"], ["10.0.0.1"]])
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
        monkeypatch.setattr(
            "socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected second DNS lookup")
        )
        result = asyncio.run(
            execute_probe(
                f"http://probe.test:{server.server_port}/ok",
                "GET",
                200,
                2,
                fixture_settings(server, "probe.test"),
                resolver=resolver,
            )
        )
        assert result.outcome == "success" and resolver.await_count == 1
        assert server.hits[0][2] == f"probe.test:{server.server_port}"
        rebound = asyncio.run(
            execute_probe(
                f"http://probe.test:{server.server_port}/ok",
                "GET",
                200,
                2,
                fixture_settings(server, "probe.test"),
                resolver=resolver,
            )
        )
        assert rebound.outcome == "blocked" and resolver.await_count == 2
        assert len(server.hits) == 1


def test_mixed_answers_are_blocked_before_any_connection() -> None:
    with fixture_server() as (server, _):
        result = asyncio.run(
            execute_probe(
                f"http://probe.test:{server.server_port}/ok",
                "GET",
                200,
                2,
                fixture_settings(server, "probe.test"),
                resolver=AsyncMock(return_value=["127.0.0.1", "10.0.0.1"]),
            )
        )
        assert result.outcome == "blocked" and server.hits == []


def test_https_preserves_host_sni_and_certificate_verification() -> None:
    with fixture_server(tls=True) as (server, context):
        url = f"https://probe.test:{server.server_port}/ok"
        result = asyncio.run(
            execute_probe(
                url,
                "GET",
                200,
                3,
                fixture_settings(server, "probe.test"),
                resolver=fixture_resolver,
                ssl_context=context,
            )
        )
        assert result.outcome == "success"
        assert server.sni == ["probe.test"]
        assert server.hits[0][2] == f"probe.test:{server.server_port}"
        wrong = asyncio.run(
            execute_probe(
                f"https://wrong.test:{server.server_port}/ok",
                "GET",
                200,
                3,
                fixture_settings(server, "wrong.test"),
                resolver=fixture_resolver,
                ssl_context=context,
            )
        )
        assert wrong.error_code == "tls_error"
        untrusted = asyncio.run(
            execute_probe(
                url,
                "GET",
                200,
                3,
                fixture_settings(server, "probe.test"),
                resolver=fixture_resolver,
            )
        )
        assert untrusted.error_code == "tls_error" and len(server.hits) == 1


def test_transport_strips_host_sni_and_authorization_overrides() -> None:
    with fixture_server(tls=True) as (server, context):

        async def request() -> None:
            transport = ProbeTransport(
                DestinationPolicy(fixture_settings(server, "probe.test")),
                resolver=fixture_resolver,
                ssl_context=context,
            )
            async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
                response = await client.get(
                    f"https://probe.test:{server.server_port}/ok",
                    headers={"Host": "evil.test", "Authorization": "secret"},
                    extensions={"sni_hostname": "evil.test"},
                )
                assert response.status_code == 200

        asyncio.run(request())
        assert server.sni == ["probe.test"] and server.hits[0][2].startswith("probe.test:")
        assert server.authorization == [None]
    insecure = ssl._create_unverified_context()
    with pytest.raises(ValueError, match="verification"):
        ProbeTransport(DestinationPolicy(Settings()), ssl_context=insecure)
