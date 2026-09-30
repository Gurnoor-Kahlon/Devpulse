"""Local-only real HTTP fixture; shares the probe worker's network namespace."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):
        status = 200 if self.path == "/health" else Handler.status
        body = b'{"fixture":"controlled","ok":true}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path not in ("/control/200", "/control/503"):
            self.send_error(404)
            return
        Handler.status = int(self.path.rsplit("/", 1)[1])
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        pass


ThreadingHTTPServer(("127.0.0.1", 8081), Handler).serve_forever()
