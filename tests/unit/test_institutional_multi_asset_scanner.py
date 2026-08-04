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
    # Floors locked
    assert DEFAULT_AI_SCALPING_CONFIG.normal_vol.quality == 82
    assert DEFAULT_AI_SCALPING_CONFIG.normal_vol.confidence == 82


@pytest.mark.unit
def test_resolve_scan_universe_respects_plane_allowlist() -> None:
    plane = MagicMock()
    plane.allowed_symbols = ("XAUUSD", "EURUSD")
    assert resolve_scan_universe(plane=plane) == ("XAUUSD", "EURUSD")


@pytest.mark.unit
def test_resolve_scan_universe_ignores_stale_gold_only_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    plane = MagicMock()
    plane.allowed_symbols = ("XAUUSD",)
    universe = resolve_scan_universe(plane=plane)
    assert "EURUSD" in universe
    assert "GBPUSD" in universe
    assert "BTCUSD" in universe
    assert "NAS100" not in universe
    assert len(universe) == len(DEFAULT_SCALPING_UNIVERSE)


@pytest.mark.unit
def test_resolve_scan_universe_strips_broker_dead_indexes() -> None:
    plane = MagicMock()
    plane.allowed_symbols = ("XAUUSD", "EURUSD", "NAS100", "US30", "GER40")
    universe = resolve_scan_universe(plane=plane)
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
                "ai_confidence": 40,
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

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_symbol_for_scan",
        _fake_score,
    )
    narrow = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=("XAUUSD", "EURUSD", "GBPUSD"),
    )
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=object(),
        config=narrow,
        open_positions=0,
    )
    assert out["best_symbol"] == "EURUSD"
    assert out["eligible_count"] >= 1
    assert out["forced_trades"] is False
    assert out["governed_by_existing_ai_and_risk"] is True
    symbols = {r["symbol"] for r in out["noc_rows"]}
    assert symbols == {"XAUUSD", "EURUSD", "GBPUSD"}
    eurusd = next(r for r in out["noc_rows"] if r["symbol"] == "EURUSD")
    assert eurusd["decision"] == "SELL"
    assert eurusd["eligible"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_score_symbol_fail_closed_on_bad_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
