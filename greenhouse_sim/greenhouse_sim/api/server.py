"""Serving the local API over HTTP, on this machine only.

    python -m greenhouse_sim.api [--port PORT]

The browser viewer's development server forwards `/api` here, so the API
needs no cross-origin headers. It binds to the loopback interface: it is a
tool for a developer's own machine, not a service.
"""

import argparse
import json
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

from greenhouse_sim.api.routes import Response, respond

LOOPBACK: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8765


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._send(respond("GET", self.path))

    def do_POST(self) -> None:
        self._send(respond("POST", self.path))

    def _send(self, response: Response) -> None:
        body = json.dumps(response.body).encode()
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """A server on the loopback interface; port 0 picks a free port."""
    return ThreadingHTTPServer((LOOPBACK, port), _Handler)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the simulator's local API.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    server = create_server(args.port)
    host, port = server.server_address[:2]
    print(f"greenhouse-sim API on http://{host!s}:{port}/api", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
