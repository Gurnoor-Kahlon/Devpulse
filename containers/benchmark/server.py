"""Fixed 10 ms HTTP fixture with an independent count of completed response writes."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BODY = b'{"fixture":"milestone-19","ok":true}'


class Handler(BaseHTTPRequestHandler):
    lock = threading.Lock()
    completed = 0

    def do_GET(self):
        if self.path == "/probe":
            time.sleep(0.010)
            self.respond(BODY)
            with self.lock:
                type(self).completed += 1
        elif self.path == "/stats":
            with self.lock:
                body = json.dumps({"completed_responses": self.completed}).encode()
            self.respond(body)
        elif self.path == "/health":
            self.respond(b"ok")
        else:
            self.send_error(404)

    def respond(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8081), Handler).serve_forever()
