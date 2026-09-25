import asyncio
import errno
import socket
import ssl
import time
import zlib
from dataclasses import dataclass
from datetime import datetime

import httpcore
import httpx

from app.core.config import Settings
from app.core.security import now_utc
from app.monitoring.policy import DestinationPolicy, ProbeError, Resolver, resolve_addresses
from app.monitoring.transport import ProbeTransport

BODY_LIMIT = 1024 * 1024
ERROR_MESSAGES = {
    "destination_blocked": "The destination is not allowed.",
    "dns_error": "The destination could not be resolved.",
    "timeout": "The request exceeded its time limit.",
    "tls_error": "The TLS connection could not be verified.",
    "connection_error": "The destination connection failed.",
    "invalid_response": "The destination returned an invalid HTTP response.",
    "invalid_body": "The response encoding is unsupported or malformed.",
    "response_too_large": "The response exceeded its size limit.",
    "unexpected_status": "The HTTP status did not match the expected status.",
    "infrastructure_error": "Local probe resources are temporarily unavailable.",
}


@dataclass(frozen=True)
class ProbeResult:
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    outcome: str
    http_status: int | None
    error_code: str | None
    error_message: str | None


async def consume_body(response: httpx.Response, method: str) -> None:
    if method == "HEAD":
        return
    length = response.headers.get("content-length")
    if length and length.isdecimal() and int(length) > BODY_LIMIT:
        raise ProbeError("response_too_large")
    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if encoding not in {"identity", "gzip", "deflate"}:
        raise ProbeError("invalid_body")
    decoder = (
        zlib.decompressobj(31 if encoding == "gzip" else 15) if encoding != "identity" else None
    )
    wire = decoded = 0
    async for chunk in response.aiter_raw():
        wire += len(chunk)
        if wire > BODY_LIMIT:
            raise ProbeError("response_too_large")
        output = decoder.decompress(chunk, BODY_LIMIT - decoded + 1) if decoder else chunk
        decoded += len(output)
        if decoded > BODY_LIMIT or (decoder and decoder.unconsumed_tail):
            raise ProbeError("response_too_large")
        if decoder and decoder.unused_data:
            raise ProbeError("invalid_body")
    if decoder and not decoder.eof:
        raise ProbeError("invalid_body")


async def execute_probe(
    url: str,
    method: str,
    expected_status: int,
    timeout_seconds: int,
    settings: Settings,
    *,
    resolver: Resolver = resolve_addresses,
    ssl_context: ssl.SSLContext | None = None,
) -> ProbeResult:
    started = now_utc()
    clock = time.perf_counter()
    status: int | None = None
    code: str | None = None
    outcome = "failure"
    try:
        async with asyncio.timeout(timeout_seconds):
            policy = DestinationPolicy(settings)
            destination = policy.validate_url(url)
            transport = ProbeTransport(policy, resolver=resolver, ssl_context=ssl_context)
            async with httpx.AsyncClient(
                transport=transport,
                trust_env=False,
                follow_redirects=False,
                timeout=timeout_seconds,
            ) as client:
                async with client.stream(method, destination) as response:
                    status = response.status_code
                    await consume_body(response, method)
                    code = None if status == expected_status else "unexpected_status"
                    outcome = "success" if code is None else "failure"
    except ProbeError as exc:
        code = exc.code
        if code == "destination_blocked":
            outcome = "blocked"
    except (TimeoutError, httpcore.TimeoutException, httpx.TimeoutException):
        code = "timeout"
    except ssl.SSLError:
        code = "tls_error"
    except socket.gaierror as exc:
        code = "infrastructure_error" if exc.errno == socket.EAI_AGAIN else "dns_error"
    except OSError as exc:
        code = (
            "infrastructure_error"
            if exc.errno
            in {errno.EMFILE, errno.ENFILE, errno.ENOMEM, errno.ENOBUFS, errno.ENETDOWN}
            else "connection_error"
        )
    except (httpcore.ProtocolError, httpx.ProtocolError):
        code = "invalid_response"
    except (zlib.error, httpx.DecodingError):
        code = "invalid_body"
    except (httpcore.NetworkError, httpx.NetworkError):
        code = "connection_error"
    if code == "infrastructure_error":
        outcome = "infrastructure_failure"
    elif code and outcome != "blocked":
        outcome = "failure"
    return ProbeResult(
        started,
        now_utc(),
        round((time.perf_counter() - clock) * 1000, 3),
        outcome,
        status,
        code,
        ERROR_MESSAGES[code] if code else None,
    )
