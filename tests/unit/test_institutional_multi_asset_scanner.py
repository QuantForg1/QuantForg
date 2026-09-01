"""Unit tests — Institutional Multi-Asset Scanner (full AI score per symbol)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_multi_asset_scanner import (
    _noc_row_from_score,
    resolve_scan_universe,
    run_institutional_multi_asset_scan,
    score_symbol_for_scan,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
)


EXPECTED_UNIVERSE = {
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "AUDUSD",
    "NZDUSD",
    "BTCUSD",
    "ETHUSD",
}


@pytest.mark.unit
def test_institutional_watchlist_matches_approved_universe() -> None:
    assert set(DEFAULT_SCALPING_UNIVERSE) == EXPECTED_UNIVERSE
    assert set(DEFAULT_AI_SCALPING_CONFIG.universe) == EXPECTED_UNIVERSE
    assert "ETHUSD" in DEFAULT_SCALPING_UNIVERSE
    assert "NAS100" not in DEFAULT_SCALPING_UNIVERSE
    assert "GER40" not in DEFAULT_SCALPING_UNIVERSE
    assert DEFAULT_AI_SCALPING_CONFIG.multi_asset_scan_enabled is True
    assert DEFAULT_AI_SCALPING_CONFIG.parallel_scan_enabled is True
    assert DEFAULT_AI_SCALPING_CONFIG.max_entries_per_cycle >= 2
    # SCALPING_V1 floors
    assert DEFAULT_AI_SCALPING_CONFIG.normal_vol.quality == 74
    assert DEFAULT_AI_SCALPING_CONFIG.normal_vol.confidence == 71
    assert DEFAULT_AI_SCALPING_CONFIG.quality_baseline == "SCALPING_V1"


@pytest.mark.unit
def test_resolve_scan_universe_respects_plane_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
        reset_symbol_stats_book_for_tests,
    )

    reset_symbol_stats_book_for_tests()
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    plane = MagicMock()
    plane.allowed_symbols = ("XAUUSD", "EURUSD")
    cfg = replace(DEFAULT_AI_SCALPING_CONFIG, live_symbol_learning_enabled=False)
    assert set(resolve_scan_universe(cfg, plane=plane)) == {"XAUUSD", "EURUSD"}


@pytest.mark.unit
def test_resolve_scan_universe_ignores_stale_gold_only_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
        reset_symbol_stats_book_for_tests,
    )

    reset_symbol_stats_book_for_tests()
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    plane = MagicMock()
    plane.allowed_symbols = ("XAUUSD",)
    cfg = replace(DEFAULT_AI_SCALPING_CONFIG, live_symbol_learning_enabled=False)
    universe = resolve_scan_universe(cfg, plane=plane)
    assert "EURUSD" in universe
    assert "GBPUSD" in universe
    assert "BTCUSD" in universe
    assert "NAS100" not in universe
    assert len(universe) == len(DEFAULT_SCALPING_UNIVERSE)


@pytest.mark.unit
def test_resolve_scan_universe_strips_broker_dead_indexes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
        reset_symbol_stats_book_for_tests,
    )

    reset_symbol_stats_book_for_tests()
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    plane = MagicMock()
    plane.allowed_symbols = ("XAUUSD", "EURUSD", "NAS100", "US30", "GER40")
    cfg = replace(DEFAULT_AI_SCALPING_CONFIG, live_symbol_learning_enabled=False)
    universe = resolve_scan_universe(cfg, plane=plane)
    assert "XAUUSD" in universe
    assert "EURUSD" in universe
    assert "NAS100" not in universe
    assert "US30" not in universe
    assert "GER40" not in universe


@pytest.mark.unit
def test_noc_row_maps_blocking_gate() -> None:
    row = _noc_row_from_score(
        {
            "symbol": "XAUUSD",
            "reject": True,
            "reject_reason": "valid_volatility",
            "direction": "NONE",
            "trade_quality": 72,
            "ai_confidence": 70,
            "liquidity": 60,
            "mtf_alignment": 55,
            "volatility_decision": {"band": "compression", "passed": False},
        }
    )
    assert row["symbol"] == "XAUUSD"
    assert row["decision"] == "NO_TRADE"
    assert row["blocking_gate"] == "valid_volatility"
    assert row["eligible"] is False
    assert row["quality"] == 72
    assert row["confidence"] == 70
    assert row["volatility"] == "compression"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scan_disabled_does_not_force_trades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = replace(DEFAULT_AI_SCALPING_CONFIG, multi_asset_scan_enabled=False)
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=object(),
        config=cfg,
    )
    assert out["enabled"] is False
    assert out["best_symbol"] is None
    assert out["forced_trades"] is not True
    assert out["governed_by_existing_ai_and_risk"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scan_ranks_best_eligible_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_score(
        _adapter: Any,
        symbol: str,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        if symbol == "XAUUSD":
            return {
                "symbol": "XAUUSD",
                "reject": True,
                "reject_reason": "no edge",
                "direction": "NONE",
                "ai_confidence": 99,
                "trade_quality": 40,
                "liquidity": 50,
                "expected_rr": "1.0",
                "spread_score": 80,
                "market_regime": "range",
                "execution_health_ok": True,
            }
        if symbol == "EURUSD":
            return {
                "symbol": "EURUSD",
                "reject": False,
                "direction": "SELL",
                "ai_confidence": 91,
                "trade_quality": 92,
                "liquidity": 85,
                "expected_rr": "1.8",
                "spread_score": 90,
                "market_regime": "strong_trend",
                "setup_family": "bos_continuation",
                "execution_health_ok": True,
                "atr_pct": "0.90",
            }
        return {
            "symbol": symbol,
            "reject": True,
            "reject_reason": "below floors",
            "direction": "NONE",
            "ai_confidence": 50,
            "trade_quality": 50,
            "liquidity": 40,
            "spread_score": 70,
            "execution_health_ok": True,
        }

    from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
        reset_symbol_stats_book_for_tests,
    )

    reset_symbol_stats_book_for_tests()
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_symbol_for_scan",
        _fake_score,
    )
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    narrow = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=("XAUUSD", "EURUSD", "GBPUSD"),
        live_symbol_learning_enabled=False,
        dynamic_universe_enabled=False,
    )
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=object(),
        config=narrow,
        open_positions=0,
    )
    assert out["best_symbol"] == "EURUSD"
    assert out["eligible_count"] >= 1
    assert out["no_eligible_setup"] is False
    eligible = out.get("best_eligible_candidate") or {}
    assert eligible.get("symbol") == "EURUSD"
    assert out["forced_trades"] is False
    assert out["governed_by_existing_ai_and_risk"] is True
    symbols = {r["symbol"] for r in out["noc_rows"]}
    assert symbols == {"XAUUSD", "EURUSD", "GBPUSD"}
    eurusd = next(r for r in out["noc_rows"] if r["symbol"] == "EURUSD")
    assert eurusd["decision"] == "SELL"
    assert eurusd["eligible"] is True


@pytest.mark.unit
def test_portfolio_rank_must_include_dynamic_universe_symbols() -> None:
    """Regression: dynamic AUDNZD must not be dropped by stale DEFAULT universe.

    Exact gate that caused strategy Q91/C84 → eligible_count=0:
      portfolio_scanner.scan_multi_asset_portfolio
      if universe and sym and sym not in universe: continue
      universe = cfg.universe  # was DEFAULT without AUDNZD
    """
    from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
        scan_multi_asset_portfolio,
    )
    from app.domain.institutional_trading.ai_scalping.symbol_state import SymbolStateBook

    audnzd = {
        "symbol": "AUDNZD",
        "reject": False,
        "direction": "SELL",
        "ai_confidence": 84,
        "trade_quality": 91,
        "liquidity": 80,
        "expected_rr": "1.20",
        "spread_score": 85,
        "market_regime": "strong_trend",
        "setup_family": "pullback_continuation",
        "execution_health_ok": True,
        "atr_pct": "0.12",
        "momentum": 70,
        "structure_score": 65,
    }
    # Stale default universe — reproduces the LIVE bug
    stale = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=DEFAULT_SCALPING_UNIVERSE,
        adaptive_cooldown_enabled=False,
    )
    dropped = scan_multi_asset_portfolio(
        [audnzd],
        open_positions=0,
        config=stale,
        state_book=SymbolStateBook(),
    )
    assert dropped.best is None or str(dropped.best.get("symbol") or "") != "AUDNZD"
    assert all(str(r.get("symbol") or "").upper() != "AUDNZD" for r in dropped.ranked)

    # Fixed path — rank with the resolved scan universe
    fixed = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=("AUDNZD", "XAUUSD", "EURUSD"),
        adaptive_cooldown_enabled=False,
    )
    kept = scan_multi_asset_portfolio(
        [audnzd],
        open_positions=0,
        config=fixed,
        state_book=SymbolStateBook(),
    )
    assert kept.best is not None
    assert str(kept.best.get("symbol") or "").upper() == "AUDNZD"
    assert any(str(r.get("symbol") or "").upper() == "AUDNZD" for r in kept.ranked)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dynamic_symbol_reaches_eligible_after_universe_align(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full scan: AUDNZD strategy-quality setup must land in eligible_symbols."""

    async def _fake_score(mt5: Any, symbol: str, **_k: Any) -> dict[str, Any]:
        if symbol == "AUDNZD":
            return {
                "symbol": "AUDNZD",
                "reject": False,
                "direction": "SELL",
                "ai_confidence": 84,
                "trade_quality": 91,
                "liquidity": 80,
                "expected_rr": "1.20",
                "spread_score": 85,
                "market_regime": "strong_trend",
                "setup_family": "pullback_continuation",
                "execution_health_ok": True,
                "atr_pct": "0.12",
                "momentum": 72,
                "structure_score": 68,
                "factors": {
                    "momentum": 72,
                    "trend_strength": 70,
                    "mtf": 80,
                    "volume": 70,
                    "bos": 60,
                    "choch": 55,
                },
            }
        return {
            "symbol": symbol,
            "reject": True,
            "reject_reason": "below floors",
            "direction": "NONE",
            "ai_confidence": 40,
            "trade_quality": 40,
            "liquidity": 40,
            "spread_score": 70,
            "execution_health_ok": True,
            "atr_pct": "0.10",
        }

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_symbol_for_scan",
        _fake_score,
    )
    # cfg.universe stays DEFAULT (no AUDNZD); resolve_scan_universe returns AUDNZD.
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.resolve_scan_universe",
        lambda *_a, **_k: ("AUDNZD", "XAUUSD"),
    )
    cfg = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=DEFAULT_SCALPING_UNIVERSE,
        adaptive_cooldown_enabled=False,
        multi_strategy_enabled=True,
        dynamic_universe_enabled=True,
        parallel_scan_enabled=False,
    )
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=object(),
        config=cfg,
        open_positions=0,
    )
    assert "AUDNZD" in (out.get("eligible_symbols") or [])
    assert int(out.get("eligible_count") or 0) >= 1
    assert out.get("best_symbol") == "AUDNZD"

    async def _bad_ctx(*_a: Any, **_k: Any) -> Any:
        return MagicMock(ok=False, snapshot=None, account=None, reason="no bars")

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.build_ite_cycle_market_context",
        _bad_ctx,
    )
    row = await score_symbol_for_scan(object(), "NAS100")
    assert row["reject"] is True
    assert row["symbol"] == "NAS100"
    assert "no bars" in str(row["reject_reason"])
    assert row["context_status"] == "SYMBOL_CONTEXT_NOT_READY"
    assert row["context_reason"] == "no bars"
    assert row["failure_class"] == "SYMBOL_FAILURE"


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_score_records_ready_context_and_broker_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    ctx = SimpleNamespace(
        ok=True,
        snapshot=SimpleNamespace(
            entry_opens=(),
            entry_highs=(),
            entry_lows=(),
            entry_closes=(),
            trend=None,
        ),
        account=SimpleNamespace(
            atr=Decimal("1"),
            mid_price=Decimal("1.1"),
            bid=Decimal("1.1"),
            ask=Decimal("1.11"),
        ),
        reason="market context ready",
        diagnostics={"broker_symbol_resolved": "EURUSD_i", "symbol": "EURUSD_i"},
        spread=Decimal("0.0001"),
        market_data_live=True,
    )

    async def _ok_ctx(*_a: Any, **_k: Any) -> Any:
        assert _k.get("purpose") == "scan"
        return ctx

    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.domain.trading.execution_universe.broker_discovered_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.domain.trading.execution_universe.execution_symbol_allowed",
        lambda *_a, **_k: True,
    )

    score = MagicMock()
    score.to_dict.return_value = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "reject": False,
        "trade_quality": 90,
        "ai_confidence": 90,
    }
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.build_ite_cycle_market_context",
        _ok_ctx,
    )
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_scalping_setup",
        lambda *_a, **_k: score,
    )
    row = await score_symbol_for_scan(object(), "EURUSD")
    assert row["context_status"] == "SYMBOL_CONTEXT_READY"
    assert row["broker_symbol"] == "EURUSD_I"
    assert row["reject"] is False
