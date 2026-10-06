"""Loopback-only controlled HTTP endpoints for the disposable portfolio showcase."""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock


class Handler(BaseHTTPRequestHandler):
    phase = "healthy"
    counts = {}
    lock = Lock()

    def do_GET(self):
        if self.path == "/health":
            status, payload = 200, {"ready": True}
        elif self.path in ("/catalog", "/search", "/billing", "/inventory", "/checkout"):
            with self.lock:
                count = self.counts.get(self.path, 0)
                self.counts[self.path] = count + 1
                phase = self.phase
            # Real server-side delays, measured by the unmodified HTTP probe executor.
            delay = (0.48, 0.64, 0.82, 0.56)[count % 4] if self.path == "/search" else 0.025
            time.sleep(delay)
            failing = phase != "healthy" and self.path == "/billing"
            failing |= phase == "incident" and self.path == "/checkout"
            status = 503 if failing else 200
            payload = {"available": not (phase != "healthy" and self.path == "/inventory")}
        else:
            status, payload = 404, {"error": "unknown controlled endpoint"}
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        phase = self.path.removeprefix("/control/")
        if self.path != f"/control/{phase}" or phase not in ("healthy", "incident", "recovery"):
            self.send_error(404)
            return
        with self.lock:
            type(self).phase = phase
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8081), Handler).serve_forever()
