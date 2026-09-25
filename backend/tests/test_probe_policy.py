import asyncio
import socket
from unittest.mock import AsyncMock

import dns.resolver
import pytest
from pydantic import ValidationError

from app.core.config import ProbeFixtureDestination, Settings
from app.monitoring.executor import execute_probe
from app.monitoring.policy import DestinationPolicy, ProbeError, public_address, resolve_addresses


def test_address_policy_blocks_special_ranges_and_mapped_ipv6() -> None:
    blocked = [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.100.100.200",
        "168.63.129.16",
        "0.0.0.0",
        "224.0.0.1",
        "255.255.255.255",
        "192.0.2.1",
        "198.18.0.1",
        "100.64.0.1",
        "::",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "fec0::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "2001:db8::1",
        "2002:7f00:1::",
        "64:ff9b::7f00:1",
        "fe80::1%eth0",
        "not-an-address",
    ]
    assert all(not public_address(address) for address in blocked)
    assert all(
        public_address(address)
        for address in ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "::ffff:8.8.8.8"]
    )


def test_url_policy_rejects_ambiguous_and_unsupported_destinations() -> None:
    policy = DestinationPolicy(Settings())
    for url in [
        "file:///etc/passwd",
        "ftp://example.com",
        "http:example.com",
        "https://u:p@example.com",
        "https://@example.com",
        "https://example.com/#",
        "https://example.com:8080",
        "https://example.com\\@127.0.0.1",
        "https://example.com/\n",
        "http://localhost.",
        "http://a.localhost",
        "http://metadata.google.internal",
        "http://[fe80::1%25eth0]",
    ]:
        with pytest.raises(ProbeError):
            policy.validate_url(url)
    assert policy.validate_url("https://EXAMPLE.com/health?q=private").host == "example.com"


def test_all_dns_answers_are_validated_and_ipv4_mapped_is_normalized() -> None:
    policy = DestinationPolicy(Settings())
    for answers in (["8.8.8.8", "127.0.0.1"], ["::ffff:10.0.0.1", "1.1.1.1"], []):
        with pytest.raises(ProbeError):
            asyncio.run(policy.addresses("example.com", 443, AsyncMock(return_value=answers)))
    assert asyncio.run(
        policy.addresses("example.com", 443, AsyncMock(return_value=["::ffff:8.8.8.8"]))
    ) == ["8.8.8.8"]


def test_fixture_exceptions_are_exact_loopback_only_and_rejected_in_production() -> None:
    entry = ProbeFixtureDestination(host="probe.test", port=12345, address="127.0.0.1")
    settings = Settings(environment="test", probe_fixture_destinations=(entry,))
    policy = DestinationPolicy(settings)
    assert policy.fixture_addresses("probe.test", 12345) == {"127.0.0.1"}
    assert not policy.fixture_addresses("probe.test", 12346)
    assert not policy.fixture_addresses("other.test", 12345)
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            app_origin="https://devpulse.example",
            smtp_mode="tls",
            probe_fixture_destinations=(entry,),
        )
    with pytest.raises(ValidationError):
        ProbeFixtureDestination(host="probe.test", port=80, address="10.0.0.1")
    assert not DestinationPolicy(
        settings.model_copy(update={"environment": "production"})
    ).fixture_addresses("probe.test", 12345)


def test_dns_failures_and_resource_failures_are_sanitized() -> None:
    for error, code, outcome in [
        (socket.gaierror(socket.EAI_NONAME, "query-secret"), "dns_error", "failure"),
        (
            socket.gaierror(socket.EAI_AGAIN, "query-secret"),
            "infrastructure_error",
            "infrastructure_failure",
        ),
    ]:
        result = asyncio.run(
            execute_probe(
                "https://example.com/?token=query-secret",
                "GET",
                200,
                1,
                Settings(),
                resolver=AsyncMock(side_effect=error),
            )
        )
        assert result.error_code == code and result.outcome == outcome
        assert "query-secret" not in repr(result)


def test_async_resolver_checks_both_families_without_search_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = AsyncMock()
    # Return DNS-like records for the second family.
    from unittest.mock import Mock

    record = Mock()
    record.to_text.return_value = "::1"
    resolver.resolve.side_effect = [dns.resolver.NoAnswer(), [record]]
    monkeypatch.setattr("dns.asyncresolver.Resolver", lambda: resolver)
    assert asyncio.run(resolve_addresses("probe.test", 443)) == ["::1"]
    assert [call.args[1] for call in resolver.resolve.call_args_list] == ["A", "AAAA"]
    assert all(call.kwargs["search"] is False for call in resolver.resolve.call_args_list)
    resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
    with pytest.raises(ProbeError, match="dns_error"):
        asyncio.run(resolve_addresses("probe.test", 443))
