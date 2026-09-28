"""A real loopback SMTP server with controlled acceptance/failure for worker tests."""

import socketserver
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser


class SMTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.code = 250
        self.attempt_times = []
        self.attempt_wall_times = []
        self.accepted = []
        self.pause_ack = False
        self.received = threading.Event()
        self.release = threading.Event()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(15)
        self.wfile.write(b"220 fixture ESMTP\r\n")
        try:
            while command := self.rfile.readline(8192):
                verb = command.split(b" ", 1)[0].strip().upper()
                if verb == b"DATA":
                    self.wfile.write(b"354 Send message\r\n")
                    data = bytearray()
                    while line := self.rfile.readline(8192):
                        if line == b".\r\n":
                            break
                        data.extend(line[1:] if line.startswith(b"..") else line)
                        if len(data) > 65536:
                            raise OSError("Fixture message bound")
                    self.server.attempt_times.append(time.monotonic())
                    self.server.attempt_wall_times.append(datetime.now(UTC))
                    if self.server.code == 250:
                        self.server.accepted.append(
                            BytesParser(policy=policy.default).parsebytes(bytes(data))
                        )
                    self.server.received.set()
                    if self.server.pause_ack:
                        self.server.release.wait(timeout=15)
                    self.wfile.write(f"{self.server.code} fixture response\r\n".encode())
                elif verb == b"QUIT":
                    self.wfile.write(b"221 Bye\r\n")
                    return
                else:
                    self.wfile.write(b"250 fixture\r\n")
        except OSError:
            pass


@contextmanager
def smtp_server() -> Iterator[SMTPServer]:
    server = SMTPServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
