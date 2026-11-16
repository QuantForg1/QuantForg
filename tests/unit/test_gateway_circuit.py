"""Gateway read circuit: a hung endpoint fails fast instead of starving the API."""

from __future__ import annotations

import pytest

from app.infrastructure.brokers.mt5 import gateway_circuit as gc

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset() -> None:
    gc.reset_for_tests()


def test_opens_after_two_timeouts_and_only_for_that_family() -> None:
    gc.record_failure("/history/deals", now=0)
    gc.check("/history/deals", now=1)  # one failure: still closed
    gc.record_failure("/history/orders", now=2)
    with pytest.raises(RuntimeError, match="circuit open for /history"):
        gc.check("/history/deals", now=3)
    gc.check("/account", now=3)  # other endpoints unaffected


def test_half_open_probe_then_close_on_success() -> None:
    gc.record_failure("/history/deals", now=0)
    gc.record_failure("/history/deals", now=1)
    gc.check("/history/deals", now=1 + gc.OPEN_FOR + 1)  # probe allowed
    gc.record_success("/history/deals")
    gc.check("/history/deals", now=500)


def test_old_failures_do_not_open() -> None:
    gc.record_failure("/history/deals", now=0)
    gc.record_failure("/history/deals", now=gc.WINDOW + 10)
    gc.check("/history/deals", now=gc.WINDOW + 11)


def test_transport_failure_detection() -> None:
    assert gc.is_transport_failure(RuntimeError("Gateway timeout calling GET"))
    assert gc.is_transport_failure(RuntimeError("Gateway unreachable calling GET"))
    assert not gc.is_transport_failure(RuntimeError("HTTP 404 symbol not found"))


def test_client_fails_fast_when_open(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.brokers.mt5.gateway_client import (
        GatewayMT5Client as MT5GatewayClient,
    )

    calls: list[str] = []

    def hang(self, method, path, **_k):
        calls.append(path)
        raise RuntimeError("Gateway timeout: Gateway timeout calling GET (timed out)")

    monkeypatch.setattr(MT5GatewayClient, "_request_http", hang)
    client = MT5GatewayClient(base_url="https://gw.test", token="x" * 32)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            client._request_leader("GET", "/history/deals")
    with pytest.raises(RuntimeError, match="circuit open"):
        client._request_leader("GET", "/history/deals")
    assert len(calls) == 2  # third call never reached the gateway
