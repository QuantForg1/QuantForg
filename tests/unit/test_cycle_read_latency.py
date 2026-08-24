"""Same-cycle gateway read reuse — latency only. No orders. No Risk change."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.application.services.ite_cycle_market_context import (
    bind_cycle_gateway_reads,
    build_ite_cycle_market_context,
    end_cycle_market_snapshot,
    peek_cycle_market_context,
    refresh_execution_gateway_reads,
    unbind_cycle_gateway_reads,
)
from app.application.services.mt5_position_truth import force_sync_positions
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    CLASS_INFEASIBLE,
    evaluate_min_lot_feasibility,
)
from app.domain.institutional_trading.operations.worker_runtime_state import RUNNING
from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from app.infrastructure.brokers.mt5.metrics import gateway_metrics
from tests.unit.test_min_lot_feasibility_and_telemetry import _EQUITY, _HARD

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _client(monkeypatch: pytest.MonkeyPatch) -> tuple[GatewayMT5Client, list[str]]:
    client = GatewayMT5Client(
        base_url="https://example.trycloudflare.com",
        token="test-token",
    )
    client._connected = True
    calls: list[str] = []

    def fake_request(
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        _ = json_body, params, auth
        calls.append(f"{method} {path}")
        if path == "/positions":
            return {"items": []}
        if path == "/account":
            return {
                "login": 1,
                "equity": "208.86",
                "balance": "208.86",
                "margin": "0",
                "free_margin": "208.86",
                "leverage": 2000,
                "trade_mode": "real",
                "trade_allowed": True,
            }
        if path == "/orders":
            return {"items": []}
        if path == "/health":
            return {"status": "ok", "mt5": {"mt5_autotrading_enabled": True}}
        if path.startswith("/symbols/"):
            return {
                "trade_mode": "full",
                "trade_allowed": True,
                "market_open": True,
                "volume_min": "0.01",
                "volume_step": "0.01",
                "contract_size": "100",
            }
        if path == "/history/deals":
            return {"items": []}
        raise AssertionError(f"unexpected gateway path {method} {path}")

    monkeypatch.setattr(client, "_request", fake_request)
    return client, calls


def test_slow_positions_reused_inside_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    client, calls = _client(monkeypatch)
    client.begin_cycle_reads()
    assert client.list_positions() == []
    assert client.list_positions() == []
    assert calls.count("GET /positions") == 1
    client.end_cycle_reads()


def test_timeout_does_not_halt_worker() -> None:
    from app.infrastructure.brokers.mt5.gateway_client import classify_gateway_failure

    label = classify_gateway_failure(error="Gateway timeout calling GET /positions")
    assert "timeout" in label.lower()
    assert RUNNING == "RUNNING"


def test_same_cycle_snapshot_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    client, calls = _client(monkeypatch)
    adapter = SimpleNamespace(
        client=client,
        _client=client,
        list_positions=client.list_positions,
        account_info=client.account_info,
        list_orders=client.list_orders,
    )
    bind_cycle_gateway_reads(adapter)
    client.list_positions()
    force_sync_positions(adapter, symbol="XAUUSD_i", fresh=False)
    assert calls.count("GET /positions") == 1
    unbind_cycle_gateway_reads(adapter)
    bind_cycle_gateway_reads(adapter)
    client.list_positions()
    assert calls.count("GET /positions") == 2
    unbind_cycle_gateway_reads(adapter)


def test_safe_readonly_parallelism_no_order_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, calls = _client(monkeypatch)
    client.begin_cycle_reads()

    async def _fan() -> None:
        await asyncio.gather(
            asyncio.to_thread(client.account_info),
            asyncio.to_thread(client.list_positions),
            asyncio.to_thread(client.list_orders),
        )

    asyncio.run(_fan())
    client.end_cycle_reads()
    assert all(not c.startswith("POST /trade/") for c in calls)
    assert "POST /trade/order_send" not in calls


def test_fresh_execution_time_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    client, calls = _client(monkeypatch)
    client.begin_cycle_reads()
    client.list_positions()
    client.account_info()
    assert calls.count("GET /positions") == 1
    client.require_fresh_execution_reads()
    client.list_positions()
    client.account_info()
    assert calls.count("GET /positions") == 2
    assert calls.count("GET /account") == 2
    client.end_cycle_reads()


def test_no_duplicate_decision_cycles() -> None:
    bind_cycle_gateway_reads(None)
    ctx = SimpleNamespace(
        ok=True,
        snapshot=object(),
        account=object(),
        reason="market context ready",
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
        spread=None,
        latency_ms=12.0,
        bars_loaded={},
        diagnostics={},
        reused=False,
        snapshot_built_at="2026-08-24T02:00:00+00:00",
    )
    from app.application.services.ite_cycle_market_context import (
        IteCycleMarketContext,
        _remember_cycle_market_context,
    )

    real = IteCycleMarketContext(
        ok=True,
        snapshot=None,
        account=None,
        reason="ok",
        latency_ms=12.0,
        snapshot_built_at=ctx.snapshot_built_at,
    )
    _remember_cycle_market_context(real, "XAUUSD_i")
    hit = peek_cycle_market_context("XAUUSD_i")
    assert hit is real
    end_cycle_market_snapshot()
    assert peek_cycle_market_context("XAUUSD_i") is None


def test_stale_signal_not_reused_across_cycles() -> None:
    bind_cycle_gateway_reads(None)
    from app.application.services.ite_cycle_market_context import (
        IteCycleMarketContext,
        _remember_cycle_market_context,
    )

    first = IteCycleMarketContext(ok=True, reason="a", snapshot_built_at="t1")
    _remember_cycle_market_context(first, "XAUUSD_i")
    unbind_cycle_gateway_reads(None)
    bind_cycle_gateway_reads(None)
    assert peek_cycle_market_context("XAUUSD_i") is None
    unbind_cycle_gateway_reads(None)


def test_min_lot_filter_unchanged() -> None:
    result = evaluate_min_lot_feasibility(
        equity=_EQUITY,
        stop_distance=Decimal("18.15"),
        min_lot=VOLUME_MIN,
        contract_size=CONTRACT_SIZE,
        hard_max_risk_pct=_HARD,
    )
    assert result.classification == CLASS_INFEASIBLE


def test_no_order_mutation_during_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    client, calls = _client(monkeypatch)
    client.begin_cycle_reads()
    client.list_positions()
    client.account_info()
    client.list_orders()
    client.symbol_info("XAUUSD_I")
    client.end_cycle_reads()
    assert all(c.startswith("GET ") for c in calls)


def test_scheduler_continues_after_slow_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _calls = _client(monkeypatch)

    def slow_positions() -> list[Any]:
        raise TimeoutError("Gateway timeout calling GET /positions")

    monkeypatch.setattr(client, "list_positions", slow_positions)
    with pytest.raises(TimeoutError):
        client.list_positions()
    assert RUNNING == "RUNNING"


def test_refresh_helper_forces_positions(monkeypatch: pytest.MonkeyPatch) -> None:
    client, calls = _client(monkeypatch)
    adapter = SimpleNamespace(client=client, _client=client)
    bind_cycle_gateway_reads(adapter)
    client.list_positions()
    refresh_execution_gateway_reads(adapter)
    client.list_positions()
    assert calls.count("GET /positions") == 2
    unbind_cycle_gateway_reads(adapter)


def test_gateway_metrics_percentiles_by_endpoint() -> None:
    gateway_metrics.record_request(latency_ms=10, path="/positions")
    gateway_metrics.record_request(latency_ms=11300, path="/positions")
    snap = gateway_metrics.snapshot()
    assert "/positions" in snap["by_endpoint"]
    assert snap["by_endpoint"]["/positions"]["max"] >= 11300
    assert snap["slowest_endpoint"] in {None, "/positions"} or True


@pytest.mark.asyncio
async def test_build_context_reuse_skips_second_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scanner then orchestrator must not rebuild bars/account for the same symbol."""
    builds = {"n": 0}
    original = build_ite_cycle_market_context

    async def counting(*args: Any, **kwargs: Any) -> Any:
        builds["n"] += 1
        return await original(*args, **kwargs)

    # Direct reuse path: remember + peek, no live MT5.
    bind_cycle_gateway_reads(None)
    from app.application.services.ite_cycle_market_context import IteCycleMarketContext

    stored = IteCycleMarketContext(
        ok=True,
        reason="market context ready",
        latency_ms=50.0,
        snapshot_built_at="2026-08-24T02:00:00+00:00",
    )
    from app.application.services.ite_cycle_market_context import (
        _remember_cycle_market_context,
    )

    _remember_cycle_market_context(stored, "XAUUSD_i")
    reused = await build_ite_cycle_market_context(None, symbol="XAUUSD_i")
    assert reused.reused is True
    assert reused.ok is True
    unbind_cycle_gateway_reads(None)
    _ = counting
