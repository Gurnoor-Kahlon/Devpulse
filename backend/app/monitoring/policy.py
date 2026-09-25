import ipaddress
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx

from app.core.config import Settings

Resolver = Callable[[str, int], Awaitable[list[str]]]


class ProbeError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def resolve_addresses(host: str, port: int) -> list[str]:
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        # Async DNS avoids uncancellable getaddrinfo executor threads at asyncio.run shutdown.
        async def resolve_family(kind: str) -> list[str]:
            try:
                answer = await resolver.resolve(host, kind, search=False, lifetime=10)
                return [record.to_text() for record in answer]
            except dns.resolver.NoAnswer:
                return []

        try:
            resolver = dns.asyncresolver.Resolver()
            return await resolve_family("A") + await resolve_family("AAAA")
        except dns.resolver.NXDOMAIN:
            raise ProbeError("dns_error") from None
        except dns.exception.DNSException:
            raise ProbeError("infrastructure_error") from None


def public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if "%" in value:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.is_site_local:
            return False
        if address.ipv4_mapped:
            address = address.ipv4_mapped
        elif address.sixtofour or address.teredo or address in ipaddress.ip_network("64:ff9b::/96"):
            return False
    # is_global alone allows multicast; explicitly reject all special classes.
    return (
        address.is_global
        and not any(
            (
                address.is_private,
                address.is_loopback,
                address.is_link_local,
                address.is_multicast,
                address.is_unspecified,
                address.is_reserved,
            )
        )
        and str(address) not in {"168.63.129.16", "169.254.169.254", "100.100.100.200"}
    )


@dataclass(frozen=True)
class DestinationPolicy:
    settings: Settings

    def fixture_addresses(self, host: str, port: int) -> set[str]:
        # Defense in depth even if a caller bypassed Pydantic with model_copy().
        if self.settings.environment == "production":
            return set()
        return {
            entry.address
            for entry in self.settings.probe_fixture_destinations
            if entry.host == host and entry.port == port
        }

    def validate_url(self, value: str) -> httpx.URL:
        try:
            if len(value) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
                raise ValueError()
            if (
                "\\" in value
                or "#" in value
                or not value.lower().startswith(("http://", "https://"))
            ):
                raise ValueError()
            parts = urlsplit(value)
            if not parts.hostname or parts.username is not None or "%" in parts.hostname:
                raise ValueError()
            url = httpx.URL(value)
            host = url.raw_host.decode("ascii")
            port = url.port or (443 if url.scheme == "https" else 80)
            if len(str(url)) > 2048 or url.scheme not in ("http", "https"):
                raise ValueError()
            if port not in (80, 443) and not self.fixture_addresses(host, port):
                raise ValueError()
            if not self.fixture_addresses(host, port) and (
                host.rstrip(".") == "localhost"
                or host.rstrip(".").endswith(".localhost")
                or host.rstrip(".") in {"metadata.google.internal", "metadata.goog"}
            ):
                raise ValueError()
            return url
        except (ValueError, httpx.InvalidURL, UnicodeError):
            raise ProbeError("destination_blocked") from None

    async def addresses(self, host: str, port: int, resolver: Resolver) -> list[str]:
        answers = await resolver(host, port)
        if not answers or len(answers) > 64:
            raise ProbeError("dns_error")
        exceptions = self.fixture_addresses(host, port)
        normalized = []
        for answer in answers:
            if not public_address(answer) and answer not in exceptions:
                raise ProbeError("destination_blocked")
            address = ipaddress.ip_address(answer)
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            normalized.append(str(address))
        return list(dict.fromkeys(normalized))
