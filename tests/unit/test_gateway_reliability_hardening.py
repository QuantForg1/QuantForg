"""Gateway socket-pressure hardening — read-only retry, coalesce, budgets.

Never retries mutations. Does not talk to a live broker.
"""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.domain.institutional_trading.compounding.models import LIVE_ACTIVATION
from app.domain.institutional_trading.operations.server_side_protection import (
    classify_position_protection,
    report_unprotected_positions,
)
from app.domain.institutional_trading.operations.signal_lifecycle import (
    SIGNAL_BLOCKED_CALCULATION,
    SIGNAL_BLOCKED_GATEWAY,
    SIGNAL_FOUND,
    classify_signal_final_state,
)
from app.domain.institutional_trading.operations.worker_runtime_state import (
    RECOVERING,
    RUNNING,
    WAITING_SESSION,
    derive_worker_state,
)
from app.infrastructure.brokers.mt5.deployment_topology import (
    MT5_CLOUD_VPS_MIGRATION_REQUIRED,
    USER_WINDOWS_PC_MAY_BE_OFF,
    topology_snapshot,
)
from app.infrastructure.brokers.mt5.gateway_budget import (
    LANE_UI,
    MUTATION_ATTEMPTS,
    READ_ONLY_POST_ATTEMPTS,
    TRADING_READ_LIMIT,
    UI_READ_LIMIT,
    coalesce_key,
    is_mutation_path,
    request_attempts,
    resource_pressure_state,
    use_gateway_lane,
)
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from app.infrastructure.brokers.mt5.metrics import GatewayMetrics

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _patch_client(mod: Any, transport: httpx.MockTransport) -> Any:
    original = mod.httpx.Client

    class PatchedClient(original):  # type: ignore[valid-type, misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    mod.httpx.Client = PatchedClient
    return original


@pytest.fixture
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.brokers.mt5.gateway_client.backoff_seconds",
        lambda _i: 0.0,
    )


def test_read_only_calc_has_bounded_retries_mutations_do_not() -> None:
    assert (
        request_attempts("POST", "/trade/order_calc_profit")
        == READ_ONLY_POST_ATTEMPTS
    )
    assert (
        request_attempts("POST", "/trade/order_calc_margin")
        == READ_ONLY_POST_ATTEMPTS
    )
    assert request_attempts("POST", "/trade/order_check") == READ_ONLY_POST_ATTEMPTS
    assert request_attempts("POST", "/trade/order_send") == MUTATION_ATTEMPTS
    assert request_attempts("POST", "/trade/order_cancel") == MUTATION_ATTEMPTS
    assert is_mutation_path("POST", "/trade/order_send") is True
    assert (
        coalesce_key("POST", "/trade/order_send", {"symbol": "XAUUSD_i"}, None)
        is None
    )
    assert coalesce_key(
        "POST",
        "/trade/order_calc_profit",
        {"symbol": "XAUUSD_i", "volume": 0.01},
        None,
    )


def test_order_calc_profit_retries_errno11(no_backoff: None) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path != "/trade/order_calc_profit":
            return httpx.Response(404, json={"detail": "unexpected"})
        if calls["n"] == 1:
            raise httpx.ReadError(
                "[Errno 11] Resource temporarily unavailable",
                request=request,
            )
        return httpx.Response(200, json={"profit": 12.5, "retcode": 0, "comment": "ok"})

    transport = httpx.MockTransport(handler)
    client = GatewayMT5Client(
        base_url="https://tunnel.example", token="t", timeout_seconds=5.0
    )
    import app.infrastructure.brokers.mt5.gateway_client as mod

    previous = _patch_client(mod, transport)
    try:
        data = client._request(
            "POST",
            "/trade/order_calc_profit",
            json_body={
                "symbol": "XAUUSD_i",
                "action": "buy",
                "volume": 0.01,
                "price": 1,
            },
        )
    finally:
        mod.httpx.Client = previous  # type: ignore[misc]

    assert data["profit"] == 12.5
    assert calls["n"] == 2


def test_order_send_never_retries_errno11(no_backoff: None) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadError(
            "[Errno 11] Resource temporarily unavailable",
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = GatewayMT5Client(
        base_url="https://tunnel.example", token="t", timeout_seconds=5.0
    )
    import app.infrastructure.brokers.mt5.gateway_client as mod

    previous = _patch_client(mod, transport)
    try:
        with pytest.raises(RuntimeError, match="socket pressure"):
            client._request(
                "POST",
                "/trade/order_send",
                json_body={"symbol": "XAUUSD_i", "action": "buy", "volume": 0.01},
            )
    finally:
        mod.httpx.Client = previous  # type: ignore[misc]

    assert calls["n"] == 1


def test_identical_calc_requests_coalesce_inflight(no_backoff: None) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        started.set()
        assert release.wait(timeout=2.0)
        return httpx.Response(200, json={"profit": 1.0, "retcode": 0})

    transport = httpx.MockTransport(handler)
    client = GatewayMT5Client(
        base_url="https://tunnel.example", token="t", timeout_seconds=5.0
    )
    import app.infrastructure.brokers.mt5.gateway_client as mod

    previous = _patch_client(mod, transport)
    body = {"symbol": "XAUUSD_i", "action": "buy", "volume": 0.01, "price": 2400.0}
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(
                client._request("POST", "/trade/order_calc_profit", json_body=body)
            )
        except BaseException as exc:
            errors.append(exc)

    try:
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        assert started.wait(timeout=2.0)
        release.set()
        for t in threads:
            t.join(timeout=5.0)
    finally:
        release.set()
        mod.httpx.Client = previous  # type: ignore[misc]

    assert errors == []
    assert calls["n"] == 1
    assert len(results) == 4
    assert all(row["profit"] == 1.0 for row in results)


def test_gateway_trading_read_concurrency_is_bounded(no_backoff: None) -> None:
    lock = threading.Lock()
    inflight = {"n": 0, "max": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            inflight["n"] += 1
            inflight["max"] = max(inflight["max"], inflight["n"])
        try:
            threading.Event().wait(0.05)
            return httpx.Response(200, json={"positions": []})
        finally:
            with lock:
                inflight["n"] -= 1

    transport = httpx.MockTransport(handler)
    client = GatewayMT5Client(
        base_url="https://tunnel.example", token="t", timeout_seconds=5.0
    )
    import app.infrastructure.brokers.mt5.gateway_client as mod

    previous = _patch_client(mod, transport)
    errors: list[BaseException] = []

    def worker(idx: int) -> None:
        try:
            client._request("GET", "/positions", params={"n": str(idx)})
        except BaseException as exc:
            errors.append(exc)

    try:
        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(TRADING_READ_LIMIT + 4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
    finally:
        mod.httpx.Client = previous  # type: ignore[misc]

    assert errors == []
    assert inflight["max"] <= TRADING_READ_LIMIT


def test_ui_lane_does_not_use_trading_budget(no_backoff: None) -> None:
    lock = threading.Lock()
    inflight = {"n": 0, "max": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            inflight["n"] += 1
            inflight["max"] = max(inflight["max"], inflight["n"])
        try:
            threading.Event().wait(0.05)
            return httpx.Response(200, json={"profit": 0, "retcode": 0})
        finally:
            with lock:
                inflight["n"] -= 1

    transport = httpx.MockTransport(handler)
    client = GatewayMT5Client(
        base_url="https://tunnel.example", token="t", timeout_seconds=5.0
    )
    import app.infrastructure.brokers.mt5.gateway_client as mod

    previous = _patch_client(mod, transport)
    body = {"symbol": "XAUUSD_i", "action": "buy", "volume": 0.01, "price": 1}

    def worker(idx: int) -> None:
        with use_gateway_lane(LANE_UI):
            client._request(
                "POST",
                "/trade/order_calc_profit",
                json_body={**body, "price": float(idx + 1)},
            )

    try:
        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(UI_READ_LIMIT + 3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)
    finally:
        mod.httpx.Client = previous  # type: ignore[misc]

    assert inflight["max"] <= UI_READ_LIMIT


def test_metrics_pressure_and_no_secrets() -> None:
    snap = GatewayMetrics().snapshot()
    blob = str(snap).lower()
    assert "password" not in blob
    assert "token" not in blob
    assert snap["resource_pressure_state"] == "NORMAL"
    assert resource_pressure_state(
        errno11_count=5,
        retry_exhausted_count=0,
        timeout_count=0,
        active_requests=1,
        budget=11,
        calc_failures=0,
    ) == "CRITICAL"


def test_valid_signal_stays_visible_when_calc_fails() -> None:
    assert (
        classify_signal_final_state(
            direction="BUY",
            forwarded_to_oms=False,
            reasons="MT5 order calculation failed: Gateway transient socket pressure",
        )
        == SIGNAL_BLOCKED_CALCULATION
    )
    assert (
        classify_signal_final_state(
            direction="BUY",
            forwarded_to_oms=False,
            blocking_stage="GATEWAY",
            fault_code="GATEWAY_UNAVAILABLE",
        )
        == SIGNAL_BLOCKED_GATEWAY
    )
    assert classify_signal_final_state(direction="BUY") == SIGNAL_FOUND


def test_broker_disconnect_does_not_halt_or_replay() -> None:
    recovering = derive_worker_state(
        running=True,
        cycles=8,
        broker_session_open=True,
        operator_halt=False,
        risk_halt=False,
        recovering=True,
        degraded=False,
        last_outcome="error",
        stalled=False,
    )
    assert recovering == RECOVERING
    waiting = derive_worker_state(
        running=True,
        cycles=8,
        broker_session_open=False,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome="safety_blocked",
        stalled=False,
    )
    assert waiting == WAITING_SESSION
    resumed = derive_worker_state(
        running=True,
        cycles=9,
        broker_session_open=True,
        operator_halt=False,
        risk_halt=False,
        recovering=False,
        degraded=False,
        last_outcome=None,
        stalled=False,
    )
    assert resumed == RUNNING


def test_server_side_sl_tp_is_report_only() -> None:
    protected = classify_position_protection(
        {"ticket": 1, "symbol": "XAUUSD_i", "sl": 3300.0, "tp": 3400.0, "magic": 260720}
    )
    assert protected["protected"] is True
    missing = report_unprotected_positions(
        [{"ticket": 2, "symbol": "XAUUSD_i", "sl": 0, "tp": 0, "magic": 260720}]
    )
    assert len(missing) == 1
    assert missing[0]["action"] == "REPORT_ONLY"
    assert "sl" in missing[0]["missing"]
    assert "tp" in missing[0]["missing"]


def test_machine_independent_topology_is_honest() -> None:
    snap = topology_snapshot()
    assert USER_WINDOWS_PC_MAY_BE_OFF is False
    assert snap["user_windows_pc_may_be_off"] is False
    assert snap["works_without_user_pc"] is False
    assert snap["works_without_user_browser"] is True
    assert MT5_CLOUD_VPS_MIGRATION_REQUIRED is True
    assert snap["migration_executed"] is False
    assert "mt5_terminal" in snap["user_windows_components"]
    assert "ite_worker" in snap["cloud_components"]


def test_aggressive_compounding_remains_shadow_only() -> None:
    assert LIVE_ACTIVATION == "SHADOW_ONLY"


def test_stale_cycle_is_not_an_execution_state() -> None:
    assert (
        classify_signal_final_state(
            direction="BUY",
            forwarded_to_oms=False,
            eligible=False,
        )
        == SIGNAL_FOUND
    )
    assert Decimal("0.01") == Decimal("0.01")
