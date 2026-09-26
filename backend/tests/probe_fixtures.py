import gzip
import ssl
import threading
import time
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import trustme

from app.core.config import ProbeFixtureDestination, Settings


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.hits: list[tuple[str, str, str]] = []
        self.hit_times: list[float] = []
        self.response_status = 503
        self.sni: list[str | None] = []
        self.authorization: list[str | None] = []


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        self.server.hit_times.append(time.monotonic())
        self.server.hits.append((self.command, self.path, self.headers.get("Host", "")))
        self.server.authorization.append(self.headers.get("Authorization"))
        route = self.path.split("?", 1)[0]
        if route == "/malformed":
            self.connection.sendall(b"INVALID HTTP\r\n\r\n")
            self.close_connection = True
            return
        if route == "/slow":
            time.sleep(1.4)
        body = b'{"ok":true}'
        status = 503 if route == "/fail" else 302 if route == "/redirect" else 200
        if route == "/controlled":
            status = self.server.response_status
        encoding = None
        if route == "/json":
            body = b"{invalid json and response-secret-canary"
        elif route in {"/large", "/chunked-large"}:
            body = b"x" * (1024 * 1024 + 1)
        elif route == "/limit":
            body = b"x" * (1024 * 1024)
        elif route == "/gzip":
            body, encoding = gzip.compress(b"hello"), "gzip"
        elif route == "/gzip-limit":
            body, encoding = gzip.compress(b"x" * (1024 * 1024)), "gzip"
        elif route == "/deflate":
            body, encoding = zlib.compress(b"hello"), "deflate"
        elif route == "/unsupported":
            body, encoding = b"hello", "br"
        elif route == "/bomb":
            body, encoding = gzip.compress(b"x" * (16 * 1024 * 1024)), "gzip"
        elif route == "/bad-gzip":
            body, encoding = b"not-gzip", "gzip"
        elif route == "/truncated-gzip":
            body, encoding = gzip.compress(b"hello")[:-4], "gzip"
        self.send_response(status)
        if route == "/chunked-large":
            self.send_header("Transfer-Encoding", "chunked")
        else:
            self.send_header("Content-Length", str(999 if route == "/truncated" else len(body)))
        self.send_header("Connection", "close")
        if encoding:
            self.send_header("Content-Encoding", encoding)
        if route == "/redirect":
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
        if route == "/headers":
            self.send_header("X-Large", "a" * (128 * 1024))
        self.end_headers()
        try:
            if self.command != "HEAD":
                if route == "/chunked-large":
                    for offset in range(0, len(body), 16384):
                        chunk = body[offset : offset + 16384]
                        self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                elif route == "/drip":
                    for byte in body:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.2)
                else:
                    self.wfile.write(body)
        except (OSError, ssl.SSLError):
            pass
        self.close_connection = True


@contextmanager
def fixture_server(tls: bool = False) -> Iterator[tuple[FixtureServer, ssl.SSLContext | None]]:
    server = FixtureServer()
    client_context = None
    if tls:
        ca = trustme.CA()
        certificate = ca.issue_cert("probe.test", "127.0.0.1")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        certificate.configure_cert(context)
        context.set_servername_callback(lambda socket, name, ctx: server.sni.append(name))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        client_context = ssl.create_default_context()
        ca.configure_trust(client_context)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, client_context
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def fixture_settings(server: FixtureServer, host: str = "127.0.0.1") -> Settings:
    return Settings(
        environment="test",
        probe_fixture_destinations=(
            ProbeFixtureDestination(
                host=host,
                port=server.server_port,
                address="127.0.0.1",
            ),
        ),
    )


async def fixture_resolver(host: str, port: int) -> list[str]:
    return ["127.0.0.1"]
