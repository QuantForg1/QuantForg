"""Gateway transport: HTTP/1.1 pool by default so concurrent threads never
share one multiplexed socket (19 Nov: Errno 11 bursts + stalls under HTTP/2)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.infrastructure.brokers.mt5 import gateway_client as gc


def _pool(client):
    return client._transport._pool


def test_http1_pool_is_the_default(monkeypatch):
    monkeypatch.delenv("MT5_GATEWAY_HTTP2", raising=False)
    c = gc.GatewayMT5Client(base_url="https://gw.example", token="t")
    http = c._build_http_client()
    try:
        assert gc.gateway_http2_enabled() is False
        assert _pool(http)._http2 is False
        assert _pool(http)._http1 is True
        assert _pool(http)._max_connections == 20
    finally:
        http.close()


@pytest.mark.parametrize("value", ["1", "true", "ON"])
def test_http2_is_opt_in(monkeypatch, value):
    monkeypatch.setenv("MT5_GATEWAY_HTTP2", value)
    assert gc.gateway_http2_enabled() is True


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.startswith("/slow"):
            time.sleep(1.5)
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        pass


def test_slow_call_does_not_block_concurrent_calls(monkeypatch):
    monkeypatch.delenv("MT5_GATEWAY_HTTP2", raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    c = gc.GatewayMT5Client(base_url=base, token="t")
    http = c._http_client()
    try:
        with ThreadPoolExecutor(max_workers=6) as ex:
            slow = ex.submit(http.get, f"{base}/slow")
            time.sleep(0.1)
            t0 = time.monotonic()
            fast = [ex.submit(http.get, f"{base}/fast/{i}") for i in range(5)]
            results = [f.result(timeout=5) for f in fast]
            fast_elapsed = time.monotonic() - t0
            assert all(r.status_code == 200 for r in results)
            # Fast calls finish while the slow one is still running.
            assert fast_elapsed < 1.0
            assert not slow.done()
            assert slow.result(timeout=5).status_code == 200
    finally:
        http.close()
        server.shutdown()
        server.server_close()
