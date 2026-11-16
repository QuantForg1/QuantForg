"""Gateway timeouts / open circuit must surface as 503, never an anonymous 500.

16 Nov 2026: History, Portfolio, Orders and Positions returned 500 for hours
while the gateway's history endpoint hung.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.infrastructure.brokers.mt5 import gateway_circuit
from app.infrastructure.brokers.mt5.gateway_circuit import GatewayUnavailableError
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from app.presentation.middleware.error_handler import register_exception_handlers


def _app(exc: Exception) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/x")
    def boom() -> None:
        raise exc

    return TestClient(app, raise_server_exceptions=False)


def test_gateway_unavailable_maps_to_503() -> None:
    r = _app(GatewayUnavailableError("timeout")).get("/x")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "gateway_unavailable"
    assert r.headers["retry-after"] == "30"


def test_other_runtime_errors_stay_500() -> None:
    assert _app(RuntimeError("bug")).get("/x").status_code == 500


def test_is_still_a_runtime_error() -> None:
    assert issubclass(GatewayUnavailableError, RuntimeError)


def test_open_circuit_raises_gateway_unavailable() -> None:
    gateway_circuit.record_failure("/history/deals", now=0.0)
    gateway_circuit.record_failure("/history/deals", now=1.0)
    with pytest.raises(GatewayUnavailableError):
        gateway_circuit.check("/history/deals", now=2.0)


@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("slow"), httpx.ConnectError("refused")]
)
def test_client_transport_failures_raise_gateway_unavailable(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail(*_a: object, **_k: object) -> None:
        raise error

    monkeypatch.setattr(httpx.Client, "request", fail)
    monkeypatch.setattr(httpx.Client, "send", fail)
    client = GatewayMT5Client(base_url="https://gw.invalid", token="t" * 64)
    with pytest.raises(GatewayUnavailableError):
        client._request_http("GET", "/positions")


def test_history_reads_fail_closed_within_15s() -> None:
    client = GatewayMT5Client(base_url="https://gw.invalid", token="t" * 64)
    client.timeout_seconds = 60.0
    t = client._timeout(path="/history/deals")
    assert t.read == 15.0
    assert client._timeout(path="/history/orders").read == 15.0


def test_history_reads_are_not_retried() -> None:
    from app.infrastructure.brokers.mt5.gateway_budget import request_attempts

    assert request_attempts("GET", "/history/deals") == 1
    assert request_attempts("GET", "/history/orders?days=30") == 1
    assert request_attempts("GET", "/account") == 3
    assert request_attempts("POST", "/trade/order_send") == 1
