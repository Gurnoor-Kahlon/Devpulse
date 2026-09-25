import asyncio
import socket
import ssl
from collections.abc import AsyncIterator, Iterable
from typing import Any

import httpcore
import httpx

from app.monitoring.policy import DestinationPolicy, ProbeError, Resolver, resolve_addresses

SocketOption = (
    tuple[int, int, int] | tuple[int, int, bytes | bytearray] | tuple[int, int, None, int]
)
# Bound framing and headers too; payload limits are enforced separately by the executor.
MAX_NETWORK_BYTES = 1024 * 1024 + 64 * 1024


class SocketStream(httpcore.AsyncNetworkStream):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader, self.writer = reader, writer
        self.received = 0

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        remaining = MAX_NETWORK_BYTES - self.received
        if remaining <= 0:
            raise ProbeError("response_too_large")
        async with asyncio.timeout(timeout):
            data = await self.reader.read(min(max_bytes, remaining, 16384))
        self.received += len(data)
        return data

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        async with asyncio.timeout(timeout):
            self.writer.write(buffer)
            await self.writer.drain()

    async def aclose(self) -> None:
        # Do not await peer TLS shutdown: a hostile peer cannot extend the total deadline.
        self.writer.close()

    async def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> "SocketStream":
        if not ssl_context.check_hostname or ssl_context.verify_mode != ssl.CERT_REQUIRED:
            raise ProbeError("tls_error")
        async with asyncio.timeout(timeout):
            try:
                await self.writer.start_tls(ssl_context, server_hostname=server_hostname)
            except BaseException:
                self.writer.close()
                raise
        return self

    def get_extra_info(self, info: str) -> Any:
        if info == "is_readable":
            return self.reader.at_eof()
        return self.writer.get_extra_info(info)


class PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, policy: DestinationPolicy, resolver: Resolver = resolve_addresses) -> None:
        self.policy, self.resolver = policy, resolver

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[SocketOption] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if local_address is not None or socket_options is not None:
            raise ProbeError("destination_blocked")
        if port not in (80, 443) and not self.policy.fixture_addresses(host, port):
            raise ProbeError("destination_blocked")
        async with asyncio.timeout(timeout):
            addresses = await self.policy.addresses(host, port, self.resolver)
            last_error: OSError | None = None
            for address in addresses:
                sock = socket.socket(
                    socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM
                )
                sock.setblocking(False)
                try:
                    # Numeric sockaddr: inet_pton succeeds without another hostname lookup.
                    await asyncio.get_running_loop().sock_connect(sock, (address, port))
                    reader, writer = await asyncio.open_connection(sock=sock, limit=16384)
                    return SocketStream(reader, writer)
                except OSError as exc:
                    last_error = exc
                    sock.close()
                except BaseException:
                    sock.close()
                    raise
            assert last_error is not None
            raise last_error

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class CoreResponseStream(httpx.AsyncByteStream):
    def __init__(self, response: httpcore.Response) -> None:
        self.response = response

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.response.aiter_stream():
            yield chunk

    async def aclose(self) -> None:
        await self.response.aclose()


class ProbeTransport(httpx.AsyncBaseTransport):
    """Narrow HTTPX/HTTPCore adapter using only their public transport/backend interfaces."""

    def __init__(
        self,
        policy: DestinationPolicy,
        *,
        resolver: Resolver = resolve_addresses,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.policy = policy
        context = ssl_context or ssl.create_default_context()
        if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("Probe TLS verification is required.")
        self.pool = httpcore.AsyncConnectionPool(
            ssl_context=context,
            network_backend=PinnedNetworkBackend(policy, resolver),
            max_connections=1,
            max_keepalive_connections=0,
            http2=False,
            retries=0,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.policy.validate_url(str(request.url))
        # Do not accept caller-controlled Host, TLS names, tracing callbacks or arbitrary methods.
        if request.method not in ("GET", "HEAD"):
            raise ProbeError("destination_blocked")
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=[
                (b"Host", request.url.netloc),
                (b"User-Agent", b"DevPulse/0.1"),
                (b"Accept-Encoding", b"gzip, deflate"),
                (b"Connection", b"close"),
            ],
            content=b"",
            extensions={"timeout": request.extensions.get("timeout", {})},
        )
        response = await self.pool.handle_async_request(core_request)
        return httpx.Response(
            response.status, headers=response.headers, stream=CoreResponseStream(response)
        )

    async def aclose(self) -> None:
        await self.pool.aclose()
