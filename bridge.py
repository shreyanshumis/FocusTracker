"""Read-only loopback status endpoint for the optional YouTube extension."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 47653


class StatusBridge:
    def __init__(self, status, port=PORT):
        self.last_browser_seen = 0
        bridge = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.headers.get("Host") not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
                    self.send_error(403)
                    return
                if self.path != "/status":
                    self.send_error(404)
                    return
                if self.headers.get("X-Focus-Harbor-Client") == "companion-1.2":
                    bridge.last_browser_seen = time.monotonic()
                payload = json.dumps(status()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_):
                pass  # No browsing or request logs.

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
