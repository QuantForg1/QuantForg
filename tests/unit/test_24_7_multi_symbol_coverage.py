"""24/7 multi-symbol coverage regressions — no live orders, no gate weakening."""

from __future__ import annotations

import asyncio
import inspect
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.institutional_multi_asset_scanner import (
    focus_broker_discovered_scan_universe,
    independent_evaluation_symbols,
    reset_scan_rotation_for_tests,
    resolve_scan_universe,
    score_universe_with_budget,
)
from app.application.services.public_signal_payload import (
    PUBLIC_FOOTER,
    render_public_signal,
)
from app.application.services.strategy_diagnostics import extract_cycle_diagnostics
from app.application.services.telegram_events import opportunity_score_above_70
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
)
from app.domain.institutional_trading.ai_scalping.direction import DirectionDecision
from app.domain.institutional_trading.ai_scalping.sniper_entry import (
    evaluate_sniper_entry,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    build_dynamic_scalping_universe,
    catalogue_ordered_candidates,
    discover_from_broker_rows,
    resolve_seed_to_broker_symbol,
)
from app.domain.institutional_trading.config import (
    MAX_PLANNED_SL_RISK_USD,
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_WELTRADE_LIVE = [
    {"code": "EURUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "GBPUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "AUDUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "NZDUSD_I", "trade_mode": 4, "digits": 5},
    {"code": "USDCHF_I", "trade_mode": 4, "digits": 5},
    {"code": "USDCAD_I", "trade_mode": 4, "digits": 5},
    {"code": "USDJPY_I", "trade_mode": 4, "digits": 3},
    {"code": "XAUUSD", "trade_mode": 3, "digits": 3},
    {"code": "XAUUSD_I", "trade_mode": 4, "digits": 3},
    {"code": "BTCUSD", "trade_mode": 4, "digits": 2},
    {"code": "ETHUSD", "trade_mode": 4, "digits": 2},
    {"code": "FAKEUSD", "trade_mode": 0, "digits": 5},
]


@pytest.fixture(autouse=True)
def _reset_scan_rotation() -> None:
    reset_scan_rotation_for_tests()
    yield
    reset_scan_rotation_for_tests()


def _runtime() -> InstitutionalIteRuntime:
    return InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions={})),
    )


def test_configured_majors_enter_scanner_when_broker_lists_them() -> None:
    discovered = discover_from_broker_rows(_WELTRADE_LIVE)
    universe = build_dynamic_scalping_universe(discovered, max_symbols=36)
    for desk, broker in (
        ("AUDUSD", "AUDUSD_I"),
        ("NZDUSD", "NZDUSD_I"),
        ("USDCAD", "USDCAD_I"),
        ("USDJPY", "USDJPY_I"),
        ("EURUSD", "EURUSD_I"),
        ("GBPUSD", "GBPUSD_I"),
    ):
        assert resolve_seed_to_broker_symbol(desk, discovered=discovered) == broker
        assert broker in universe
        assert desk not in universe


def test_btc_eth_enter_universe_only_when_broker_supports_them() -> None:
    discovered = discover_from_broker_rows(_WELTRADE_LIVE)
    universe = build_dynamic_scalping_universe(discovered, max_symbols=36)
    assert "BTCUSD" in universe
    assert "ETHUSD" in universe
    fx_only = discover_from_broker_rows(
        [
            row
            for row in _WELTRADE_LIVE
            if "BTC" not in row["code"] and "ETH" not in row["code"]
        ]
    )
    uni_fx = build_dynamic_scalping_universe(fx_only, max_symbols=36)
    assert "BTCUSD" not in uni_fx
    assert "ETHUSD" not in uni_fx


def test_xauusd_i_maps_when_bare_gold_is_close_only() -> None:
    discovered = discover_from_broker_rows(_WELTRADE_LIVE)
    assert (
        resolve_seed_to_broker_symbol("XAUUSD", discovered=discovered) == "XAUUSD_I"
    )
    assert (
        resolve_seed_to_broker_symbol("XAUUSD_I", discovered=discovered) == "XAUUSD_I"
    )
    universe = build_dynamic_scalping_universe(discovered, max_symbols=36)
    gold = [s for s in universe if s.upper().startswith("XAU")]
    assert gold == ["XAUUSD_I"]


def test_xauusd_i_does_not_duplicate_xauusd_handoff() -> None:
    queued = independent_evaluation_symbols(
        [
            {"symbol": "XAUUSD", "direction": "SELL", "opportunity_score": 82},
            {"symbol": "XAUUSD_I", "direction": "SELL", "opportunity_score": 80},
            {"symbol": "EURUSD_I", "direction": "BUY", "opportunity_score": 78},
        ],
        cap=8,
    )
    assert queued.count("XAUUSD") + queued.count("XAUUSD_I") == 1
    assert "EURUSD_I" in queued


def test_focus_mapping_prefers_institutional_suffix() -> None:
    mapped = focus_broker_discovered_scan_universe(
        ("XAUUSD", "XAUUSD_I", "AUDUSD_I", "NZDUSD_I"),
        seed=("XAUUSD", "AUDUSD", "NZDUSD"),
        cap=36,
    )
    upper = [s.upper() for s in mapped]
    assert "XAUUSD_I" in upper
    assert "AUDUSD_I" in upper
    assert "NZDUSD_I" in upper
    assert "XAUUSD" not in upper


def test_expand_live_universe_does_not_keep_bare_gold() -> None:
    from app.application.services.institutional_multi_asset_scanner import (
        expand_live_liquid_scan_universe,
    )

    live = ("XAUUSD", "XAUUSD_I", "AUDUSD_I", "EURUSD_I")
    focused = focus_broker_discovered_scan_universe(
        live,
        seed=("XAUUSD", "AUDUSD", "EURUSD"),
        cap=36,
    )
    expanded = expand_live_liquid_scan_universe(
        live,
        focused=focused,
        broker_symbol_rows=_WELTRADE_LIVE,
        cap=36,
    )
    upper = [s.upper() for s in expanded]
    assert "XAUUSD_I" in upper
    assert "XAUUSD" not in upper
    assert "AUDUSD_I" in upper
    assert upper.count("XAUUSD_I") == 1


@pytest.mark.asyncio
async def test_one_symbol_timeout_does_not_abort_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_score(_adapter, symbol, **_kw):
        if "XAUUSD" in str(symbol).upper():
            await asyncio.sleep(2.0)
            return {"symbol": str(symbol).upper(), "direction": "SELL"}
        return {
            "symbol": str(symbol).upper(),
            "reject": False,
            "direction": "BUY",
            "opportunity_score": 81,
        }

    import app.application.services.institutional_multi_asset_scanner as scanner

    monkeypatch.setattr(scanner, "score_symbol_for_scan", fake_score)
    rows, stats = await score_universe_with_budget(
        object(),
        ("XAUUSD_I", "AUDUSD_I", "NZDUSD_I"),
        budget_seconds=3.0,
        per_symbol_timeout=0.2,
        concurrency=2,
    )
    assert stats["symbols_timed_out"] >= 1
    live = [r for r in rows if r.get("reject") is False]
    assert any("AUDUSD" in str(r.get("symbol")) for r in live)
    assert any("NZDUSD" in str(r.get("symbol")) for r in live)


@pytest.mark.asyncio
async def test_one_missing_snapshot_does_not_abort_other_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_score(_adapter, symbol, **_kw):
        if "GBPUSD" in str(symbol).upper():
            return {
                "symbol": str(symbol).upper(),
                "reject": True,
                "reject_reason": "NO_SNAPSHOT",
                "failure_class": "SYMBOL_FAILURE",
            }
        return {
            "symbol": str(symbol).upper(),
            "reject": False,
            "direction": "BUY",
            "opportunity_score": 80,
        }

    import app.application.services.institutional_multi_asset_scanner as scanner

    monkeypatch.setattr(scanner, "score_symbol_for_scan", fake_score)
    rows, stats = await score_universe_with_budget(
        object(),
        ("EURUSD_I", "GBPUSD_I", "USDCAD_I"),
        budget_seconds=5.0,
        per_symbol_timeout=1.0,
        concurrency=2,
    )
    assert stats["symbols_completed"] >= 2
    assert any(
        r.get("reject") is False and "EURUSD" in str(r.get("symbol")) for r in rows
    )
    assert any(
        r.get("reject") is False and "USDCAD" in str(r.get("symbol")) for r in rows
    )


def test_wait_and_missing_snapshot_release_entry_slot() -> None:
    rt = _runtime()
    rt._eligible_handoff_queue = ["EURUSD_I", "AUDUSD_I", "NZDUSD_I"]
    rt._eligible_consumed = {"EURUSD_I"}
    rt._entries_this_scan = 3
    rt._release_non_entry_slot()
    assert rt._entries_this_scan == 2
    assert rt._take_next_handoff_symbol() == "AUDUSD_I"


def test_pick_is_not_wrapped_in_cycle_budget() -> None:
    src = inspect.getsource(InstitutionalIteRuntime.run_forever)
    assert 'what="pick_executable_symbol"' not in src
    assert "pick_timeout" in src
    assert "asyncio.wait_for" in src
    assert "_pick_executable_symbol_async()" in src


def test_scanner_opportunity_score_copied_into_ite_diagnostics() -> None:
    cycle = extract_cycle_diagnostics(
        snapshot=None,
        decision=None,
        cycle_outcome="wait",
        decision_action="WAIT",
        abort_reason="WAIT_NO_SNIPER_TRIGGER",
        market_context_diagnostics={
            "symbol": "EURUSD_I",
            "opportunity_score": 82,
            "opportunity_score_source": "ai_payload",
            "opportunity_threshold": 70,
        },
    )
    assert cycle["opportunity_score"] == 82
    assert cycle["opportunity_score_source"] == "ai_payload"
    assert opportunity_score_above_70(cycle["opportunity_score"]) is True
    assert opportunity_score_above_70(70) is False
    assert opportunity_score_above_70(64) is False


def test_p70_floor_unchanged() -> None:
    assert int(OPPORTUNITY_SCORE_THRESHOLD) == 70
    assert opportunity_score_above_70(70) is False
    assert opportunity_score_above_70(71) is True


def test_sniper_still_requires_structure_confirmation() -> None:
    direction = DirectionDecision(
        direction=TradeDirection.BUY,
        buy_score=80,
        sell_score=20,
        reasons=(),
        structure_score=80,
        factors={},
        directional_edge=20,
        ltf_buy_score=80,
        ltf_sell_score=20,
    )
    snapshot = SimpleNamespace(
        symbol="EURUSD_I",
        structure_by_tf={},
        primary_structure=None,
        liquidity=SimpleNamespace(sweeps=(), equal_highs=(), equal_lows=()),
        order_blocks=(),
        ltf_order_blocks=(),
        fair_value_gaps=(),
        ltf_fair_value_gaps=(),
        trend=SimpleNamespace(alignment_score=80, primary="bullish"),
    )
    verdict = evaluate_sniper_entry(
        snapshot,
        direction=direction,
        mid=Decimal("1.1000"),
        atr=Decimal("0.0010"),
        expected_rr=Decimal("2.0"),
        min_expected_rr=Decimal("1.2"),
    )
    assert verdict.passed is False
    assert verdict.primary_reason == "WAIT_NO_SNIPER_TRIGGER"


def test_no_direct_order_send_on_runtime_or_scanner() -> None:
    scan_src = inspect.getsource(score_universe_with_budget)
    pick_src = inspect.getsource(InstitutionalIteRuntime._pick_executable_symbol_async)
    assert "order_send(" not in scan_src
    assert "order_send(" not in pick_src
    assert "execute_now(" not in scan_src
    assert "execute_now(" not in pick_src


def test_risk_usd_bands_immutable() -> None:
    assert Decimal("6.00") == MIN_PLANNED_RISK_USD
    assert Decimal("20.00") == MAX_PLANNED_SL_RISK_USD
    assert Decimal("30.00") == MAX_TOTAL_PLANNED_RISK_USD


def test_invalid_broker_symbol_fails_closed() -> None:
    discovered = discover_from_broker_rows(_WELTRADE_LIVE)
    assert catalogue_ordered_candidates("NOTASYMBOL", discovered=discovered) == ()
    missing = resolve_seed_to_broker_symbol("NOTASYMBOL", discovered=discovered)
    assert missing == "NOTASYMBOL"
    uni = resolve_scan_universe(
        DEFAULT_AI_SCALPING_CONFIG,
        broker_symbol_rows=_WELTRADE_LIVE,
        session="london",
    )
    assert "NOTASYMBOL" not in uni
    assert "FAKEUSD" not in uni


def test_public_signals_remain_canonical() -> None:
    text = render_public_signal(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry": "1.08420",
            "stop_loss": "1.08200",
            "take_profit": "1.09080",
            "opportunity_score": 82,
        }
    )
    assert PUBLIC_FOOTER in text
    assert "MT5 Ticket" not in text
    assert "Automated Trading System" not in text
    assert "Status: EXECUTED" not in text


def test_scan_context_not_reused_for_execution() -> None:
    src = inspect.getsource(
        __import__(
            "app.application.services.ite_cycle_market_context",
            fromlist=["build_ite_cycle_market_context"],
        ).build_ite_cycle_market_context
    )
    assert "scan_reuse_blocked" in src
    assert 'cached_purpose == "scan"' in src


def test_no_live_test_order_hook_in_coverage_path() -> None:
    src = inspect.getsource(InstitutionalIteRuntime._pick_executable_symbol_async)
    assert "FORCE_FIRST_TRADE" not in src
    assert "execute_now" not in src
    assert DEFAULT_SCALPING_UNIVERSE[:4] == ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")


def test_final_volume_must_be_risk_revalidated() -> None:
    from app.application.services.institutional_execution_engine import (
        InstitutionalExecutionEngine,
    )

    src = inspect.getsource(InstitutionalExecutionEngine)
    assert "approved != intent.volume.value" in src
    assert "order_send(" not in inspect.getsource(
        InstitutionalIteRuntime._pick_executable_symbol_async
    )


def test_symbol_spread_skip_does_not_abort_universe() -> None:
    from app.domain.institutional_trading.auto_trading import (
        AutoTradeLiveFacts,
        AutoTradePolicy,
        evaluate_auto_trade_safety,
        safety_blocks_decision,
        safety_failure_scope,
    )

    policy = AutoTradePolicy(enabled=True, run_state="running")
    gold = evaluate_auto_trade_safety(
        policy,
        AutoTradeLiveFacts(
            gateway_connected=True,
            broker_connected=True,
            market_data_live=True,
            risk_engine_pass=True,
            account_trading_enabled=True,
            mt5_autotrading_enabled=True,
            symbol="XAUUSD",
            symbol_tradable=True,
            margin_available=True,
            no_broker_restrictions=True,
            session="london",
            spread=Decimal("9.04"),
            ops_mode="LIVE",
            execution_enabled=True,
        ),
    )
    eurusd = evaluate_auto_trade_safety(
        policy,
        AutoTradeLiveFacts(
            gateway_connected=True,
            broker_connected=True,
            market_data_live=True,
            risk_engine_pass=True,
            account_trading_enabled=True,
            mt5_autotrading_enabled=True,
            symbol="EURUSD",
            symbol_tradable=True,
            margin_available=True,
            no_broker_restrictions=True,
            session="london",
            spread=Decimal("0.00012"),
            ops_mode="LIVE",
            execution_enabled=True,
        ),
    )
    assert safety_failure_scope(gold) == "symbol"
    assert safety_blocks_decision(gold) is False
    assert eurusd.allowed is True
    src = inspect.getsource(InstitutionalIteRuntime.run_auto_cycle)
    assert "symbol_skip" in src
    assert "safety_failure_scope" in src


def test_data_failure_on_one_desk_still_rotates_handoff() -> None:
    rt = _runtime()
    rt._eligible_handoff_queue = ["XAUUSD_I", "EURUSD_I", "GBPUSD_I"]
    rt._eligible_consumed = {"XAUUSD_I"}
    rt._entries_this_scan = 3
    rt._release_non_entry_slot()
    assert rt._take_next_handoff_symbol() == "EURUSD_I"


def test_safety_diagnostics_include_symbol() -> None:
    cycle = extract_cycle_diagnostics(
        snapshot=None,
        decision=None,
        cycle_outcome="safety_blocked",
        decision_action="NO_TRADE",
        abort_reason="SAFETY_BLOCKED",
        decision_reasons=("Spread 9.04 exceeds max 2.00 (gold usd_price)",),
        market_context_diagnostics={
            "symbol": "XAUUSD_I",
            "safety_scope": "symbol",
            "spread_raw": "9.04",
            "spread_normalized": "9.04",
            "spread_limit": "2.00",
            "spread_unit": "usd_price",
            "spread_asset_class": "gold",
            "safety_failed_reasons": [
                "Spread 9.04 exceeds max 2.00 (gold usd_price)"
            ],
        },
    )
    assert cycle["symbol"] == "XAUUSD_I"
    assert cycle["abort_reason"] == "SAFETY_BLOCKED"
    assert cycle["safety_scope"] == "symbol"
    assert cycle["spread_limit"] == "2.00"
    assert cycle["cycle_outcome"] == "safety_blocked"


def test_canonical_gold_desk_still_one_identity() -> None:
    discovered = discover_from_broker_rows(_WELTRADE_LIVE)
    uni = build_dynamic_scalping_universe(discovered, seed=("XAUUSD",))
    gold = [s for s in uni if "XAUUSD" in str(s).upper()]
    assert len(gold) <= 1
    assert resolve_seed_to_broker_symbol("XAUUSD", discovered=discovered) == (
        resolve_seed_to_broker_symbol("XAUUSD_I", discovered=discovered)
    )
