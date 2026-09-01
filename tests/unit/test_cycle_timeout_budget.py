"""CYCLE_TIMEOUT root-cause guards — budgeted scan, isolation, no fake fills."""

from __future__ import annotations

import asyncio
import inspect

import pytest

from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.institutional_multi_asset_scanner import (
    focus_broker_discovered_scan_universe,
    score_universe_with_budget,
)
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    classify_cycle_execution_status,
)
from app.domain.institutional_trading.operations.worker_runtime_state import (
    CYCLE_EXECUTION_RESERVE_SECONDS,
    SCAN_SYMBOL_TIMEOUT_SECONDS,
    cycle_hard_timeout_seconds,
    cycle_scan_budget_seconds,
)
from app.infrastructure.brokers.mt5.gateway_budget import request_attempts
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from core.config.environments import production_settings

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_scan_budget_leaves_reserve_for_execution() -> None:
    hard = cycle_hard_timeout_seconds(5.0)
    budget = cycle_scan_budget_seconds(5.0, remaining=hard)
    assert budget <= 75.0
    assert budget + CYCLE_EXECUTION_RESERVE_SECONDS <= hard
    assert SCAN_SYMBOL_TIMEOUT_SECONDS <= 15.0


def test_production_stays_broker_discovered() -> None:
    settings = production_settings(
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
        execution_universe_mode="GOLD_ONLY",
    )
    assert str(settings.execution_universe_mode).upper() == "BROKER_DISCOVERED"
    assert settings.gold_only_mode is False


def test_83_symbol_catalogue_does_not_become_scan_universe() -> None:
    live = (
        *(f"SYM{i:03d}_i" for i in range(83)),
        "EURUSD_i",
        "GBPUSD_i",
        "XAUUSD_i",
        "BTCUSD",
    )
    mapped = focus_broker_discovered_scan_universe(
        live,
        seed=("EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"),
        research_focus=(),
        cap=36,
    )
    assert len(mapped) <= 36
    assert len(mapped) < 83
    upper = {s.upper() for s in mapped}
    assert "EURUSD_I" in upper
    assert "XAUUSD_I" in upper


@pytest.mark.asyncio
async def test_slow_symbol_does_not_stop_other_desks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_score(_adapter, symbol, **_kw):
        if "EURUSD" in str(symbol).upper():
            await asyncio.sleep(2.0)
            return {"symbol": "EURUSD", "reject": False, "direction": "BUY"}
        return {
            "symbol": str(symbol).upper(),
            "reject": False,
            "direction": "SELL",
            "ai_confidence": 80,
            "trade_quality": 80,
        }

    import app.application.services.institutional_multi_asset_scanner as scanner

    monkeypatch.setattr(scanner, "score_symbol_for_scan", fake_score)
    rows, stats = await score_universe_with_budget(
        object(),
        ("EURUSD_i", "GBPUSD_i", "USDJPY"),
        budget_seconds=3.0,
        per_symbol_timeout=0.2,
        concurrency=2,
    )
    reasons = {str(r.get("symbol")): str(r.get("reject_reason") or "") for r in rows}
    assert stats["symbols_timed_out"] >= 1
    assert any("GBPUSD" in (r.get("symbol") or "") for r in rows)
    assert any(
        r.get("reject") is False and str(r.get("direction")) == "SELL" for r in rows
    )
    assert "SYMBOL_TIMEOUT" in reasons.get("EURUSD_I", reasons.get("EURUSD", ""))
    timeout_rows = [
        r
        for r in rows
        if str(r.get("reject_reason") or "") == "SYMBOL_TIMEOUT"
    ]
    assert timeout_rows
    assert all(r.get("failure_class") == "SYMBOL_FAILURE" for r in timeout_rows)


@pytest.mark.asyncio
async def test_one_gateway_failure_does_not_stop_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_score(_adapter, symbol, **_kw):
        if "BTCUSD" in str(symbol).upper():
            raise RuntimeError("gateway failure")
        return {
            "symbol": str(symbol).upper(),
            "reject": False,
            "direction": "BUY",
        }

    import app.application.services.institutional_multi_asset_scanner as scanner

    monkeypatch.setattr(scanner, "score_symbol_for_scan", fake_score)
    rows, stats = await score_universe_with_budget(
        object(),
        ("EURUSD_i", "BTCUSD", "XAUUSD_i"),
        budget_seconds=5.0,
        per_symbol_timeout=1.0,
        concurrency=2,
    )
    assert stats["symbols_completed"] >= 2
    assert any(
        r.get("reject") is False and "EURUSD" in str(r.get("symbol")) for r in rows
    )
    assert any("XAUUSD" in str(r.get("symbol")) for r in rows)


def test_cycle_timeout_is_not_a_fill() -> None:
    status = classify_cycle_execution_status(
        abort_reason="CYCLE_TIMEOUT",
        cycle_outcome="error",
        forwarded_to_oms=False,
        mt5_ticket=None,
    )
    assert status not in {"EXECUTED", "EXECUTING", "ORDER_SUBMITTED"}


def test_await_cycle_budget_does_not_cancel_order_send() -> None:
    src = inspect.getsource(InstitutionalIteRuntime._await_cycle_budget)
    assert "cancel_on_timeout" in src
    orch = inspect.getsource(InstitutionalIteRuntime.run_forever)
    assert 'what="run_auto_cycle"' in orch
    assert "cancel_on_timeout=False" in orch
    assert "_manage_open_positions_after_timeout" in orch


def test_candle_reads_fail_closed_faster_than_cycle_budget() -> None:
    client = GatewayMT5Client(
        base_url="https://gateway.example.test",
        token="t",
    )
    timeout = client._timeout(path="/candles/EURUSD_I")
    assert float(timeout.read) <= 8.0
    assert request_attempts("GET", "/candles/EURUSD_I") <= 2
    hard = cycle_hard_timeout_seconds(5.0)
    assert float(timeout.read) * request_attempts("GET", "/candles/EURUSD_I") < hard


def test_worker_continues_after_timeout_handler() -> None:
    src = inspect.getsource(InstitutionalIteRuntime.run_forever)
    assert "Autonomous engine continuing after cycle timeout" in src
    assert "timeout_stage" in src


def test_xauusd_still_in_focused_universe() -> None:
    mapped = focus_broker_discovered_scan_universe(
        ("EURUSD_i", "XAUUSD_i", "BTCUSD"),
        seed=("EURUSD", "XAUUSD", "BTCUSD"),
    )
    assert any("XAUUSD" in s.upper() for s in mapped)
    assert any("EURUSD" in s.upper() for s in mapped)
    assert any("BTCUSD" in s.upper() for s in mapped)


@pytest.mark.asyncio
async def test_multiple_signals_are_evaluated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_score(_adapter, symbol, **_kw):
        token = str(symbol).upper()
        direction = "BUY" if "EUR" in token or "XAU" in token else "SELL"
        return {
            "symbol": token,
            "reject": False,
            "direction": direction,
            "ai_confidence": 82,
            "trade_quality": 80,
        }

    import app.application.services.institutional_multi_asset_scanner as scanner

    monkeypatch.setattr(scanner, "score_symbol_for_scan", fake_score)
    rows, stats = await score_universe_with_budget(
        object(),
        ("EURUSD_i", "GBPUSD_i", "XAUUSD_i", "BTCUSD"),
        budget_seconds=5.0,
        per_symbol_timeout=1.0,
        concurrency=2,
    )
    live = [r for r in rows if r.get("reject") is False]
    dirs = {str(r.get("direction")) for r in live}
    assert stats["symbols_completed"] == 4
    assert len(live) == 4
    assert "BUY" in dirs and "SELL" in dirs


@pytest.mark.asyncio
async def test_budget_exhaustion_skips_remaining_desks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_score(_adapter, symbol, **_kw):
        await asyncio.sleep(0.15)
        return {
            "symbol": str(symbol).upper(),
            "reject": False,
            "direction": "BUY",
        }

    import app.application.services.institutional_multi_asset_scanner as scanner

    monkeypatch.setattr(scanner, "score_symbol_for_scan", fake_score)
    _rows, stats = await score_universe_with_budget(
        object(),
        tuple(f"SYM{i}" for i in range(20)),
        budget_seconds=0.2,
        per_symbol_timeout=0.3,
        concurrency=2,
    )
    skipped = int(stats["symbols_budget_skipped"]) + int(stats["symbols_timed_out"])
    assert int(stats["symbols_queued"]) == 20
    assert skipped >= 1
    assert int(stats["symbols_evaluated"]) < 20


def test_research_ranked_desks_are_scanned_before_seed() -> None:
    mapped = focus_broker_discovered_scan_universe(
        ("EURUSD_i", "GBPUSD_i", "XAUUSD_i", "BTCUSD"),
        seed=("XAUUSD", "BTCUSD"),
        research_focus=("EURUSD", "GBPUSD"),
    )
    upper = [s.upper() for s in mapped]
    assert upper.index("EURUSD_I") < upper.index("XAUUSD_I")
    assert upper.index("GBPUSD_I") < upper.index("BTCUSD")


def test_timeout_diagnostics_do_not_claim_oms_or_fill() -> None:
    from types import SimpleNamespace

    from app.application.services.institutional_ite_runtime import ShadowCycleResult
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        EXEC_EXECUTION_FAILED,
        classify_cycle_execution_status,
    )
    from app.domain.institutional_trading.operations.worker_runtime_state import (
        last_blocker_from_cycle,
    )

    diag = {
        "timeout_stage": "cycle_budget_exhausted:pick_executable_symbol",
        "orders_submitted": 0,
        "oms_attempts": 0,
        "execution_result": "NO BROKER ORDER WAS SUBMITTED",
        "mt5_ticket": None,
    }
    status = classify_cycle_execution_status(
        abort_reason="CYCLE_TIMEOUT",
        cycle_outcome="error",
        forwarded_to_oms=False,
        mt5_ticket=None,
    )
    assert status == EXEC_EXECUTION_FAILED
    cycle = ShadowCycleResult(
        ok=False,
        trace_id="t",
        mode="live",
        cycle_outcome="error",
        abort_reason="CYCLE_TIMEOUT",
        forwarded_to_oms=False,
        mt5_ticket=None,
        market_context_diagnostics=diag,
    )
    payload = cycle.to_dict()
    assert payload["mt5_ticket"] is None
    assert payload["forwarded_to_oms"] is False
    assert payload["execution_result"] == "NO BROKER ORDER WAS SUBMITTED"
    blocker, stage = last_blocker_from_cycle(cycle)
    assert blocker == "CYCLE_TIMEOUT"
    assert "pick_executable_symbol" in str(stage)
    ns = SimpleNamespace(
        abort_reason="CYCLE_TIMEOUT",
        cycle_outcome="error",
        detail="cycle timeout",
        market_context_diagnostics=diag,
    )
    _blocker, named = last_blocker_from_cycle(ns)
    assert "pick_executable_symbol" in str(named)


def test_kill_switch_and_risk_still_block_before_oms() -> None:
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        EXEC_RISK_BLOCKED,
        classify_cycle_execution_status,
    )
    from app.infrastructure.brokers.mt5.gateway_budget import MUTATION_LIMIT

    assert (
        classify_cycle_execution_status(
            abort_reason="KILL_SWITCH",
            cycle_outcome="safety_blocked",
            forwarded_to_oms=False,
            mt5_ticket=None,
            kill_switch=True,
        )
        == EXEC_RISK_BLOCKED
    )
    assert (
        classify_cycle_execution_status(
            abort_reason="DAILY_LOSS_EXCEEDED",
            cycle_outcome="safety_blocked",
            forwarded_to_oms=False,
            mt5_ticket=None,
        )
        == EXEC_RISK_BLOCKED
    )
    assert MUTATION_LIMIT == 1


def test_duplicate_signal_still_blocked_after_timeout_shape() -> None:
    from decimal import Decimal

    from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
        may_add_scalping_trade,
    )

    blocked = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="BUY",
        open_directions=("BUY",),
        entry=Decimal("4380.00"),
        open_entries=(Decimal("4380.00"),),
        min_entry_distance=Decimal("1.00"),
    )
    assert blocked.allow is False


def test_fx_and_crypto_remain_in_execution_focus() -> None:
    from app.application.services.institutional_execution_engine import (
        parse_order_intent,
    )
    from app.domain.enums.order import OrderType

    mapped = focus_broker_discovered_scan_universe(
        ("EURUSD_i", "XAUUSD_i", "BTCUSD", "ETHUSD"),
        seed=("EURUSD", "XAUUSD", "BTCUSD", "ETHUSD"),
    )
    upper = {s.upper() for s in mapped}
    assert "EURUSD_I" in upper
    assert "XAUUSD_I" in upper
    assert "BTCUSD" in upper
    fx = parse_order_intent(
        symbol="EURUSD_i", side="buy", order_type="market", volume="0.01"
    )
    crypto = parse_order_intent(
        symbol="BTCUSD", side="buy", order_type="limit", volume="0.01", price="60000"
    )
    assert fx.order_type is OrderType.MARKET
    assert crypto.order_type is OrderType.LIMIT


def test_restart_recovery_remains_fail_closed() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        recover_after_restart,
    )

    assert recover_after_restart("ENABLED") == "PAUSED"
    assert recover_after_restart("KILLED") == "DISABLED"


def test_position_management_is_not_starved_by_scan() -> None:
    src = inspect.getsource(InstitutionalIteRuntime.run_forever)
    assert "_protect_open_positions" in src
    assert 'reason="pre_scan_manage"' in src
    protect = inspect.getsource(InstitutionalIteRuntime._protect_open_positions)
    assert "recover_positions_from_mt5" in protect
    assert "order_send" not in protect
