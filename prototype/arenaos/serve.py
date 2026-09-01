"""Serve the ArenaOS prototype.

    python serve.py            # http://127.0.0.1:8090  -> ArenaOS/single-file view
    ARENA_DIR=dist python serve.py

Termux ships `python` but no `python3` alias, so this file is deliberately
stdlib-only and works with either. It binds 0.0.0.0 so a second device on the
same Wi-Fi can open the phone's LAN address if you want that.
"""
import functools
import http.server
import os
import socketserver
import sys

PORT = int(os.environ.get("ARENA_PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8090))
DIRECTORY = os.environ.get("ARENA_DIR") or os.getcwd()


class Handler(http.server.SimpleHTTPRequestHandler):
    """No-cache, so a phone browser reload always shows the file you just edited."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(
        ("0.0.0.0", PORT), functools.partial(Handler, directory=DIRECTORY)
    ) as httpd:
        print(f"serving {DIRECTORY} at http://127.0.0.1:{PORT}/  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
