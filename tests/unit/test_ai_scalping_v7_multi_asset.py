"""Unit tests — AI Scalping v7 multi-asset institutional portfolio scanner."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.ai_scalping_portfolio import run_multi_asset_scan
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
    check_portfolio_limits,
    scan_multi_asset_portfolio,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scheduler import (
    MultiAssetScanScheduler,
    get_multi_asset_scheduler,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    SymbolStateBook,
    get_symbol_state_book,
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


def _opp(
    symbol: str,
    *,
    reject: bool = False,
    confidence: int = 88,
    quality: int = 90,
    direction: str = "BUY",
    rr: str = "1.6",
    regime: str = "strong_trend",
    spread_score: int = 90,
) -> dict:
    return {
        "symbol": symbol,
        "reject": reject,
        "reject_reason": "no edge" if reject else None,
        "ai_confidence": confidence,
        "trade_quality": quality,
        "direction": direction,
        "expected_rr": rr,
        "market_regime": regime,
        "spread_score": spread_score,
        "liquidity": 85,
        "atr_pct": "0.90",
        "execution_health_ok": True,
        "setup_family": "bos_continuation",
        "reasons": ("test",),
    }


@pytest.mark.unit
def test_v7_universe_and_quality_risk_locked() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.version.startswith("ai-scalping-v8")
    assert cfg.quality_baseline == "ai-scalping-v6.3.0"
    assert set(DEFAULT_SCALPING_UNIVERSE) == EXPECTED_UNIVERSE
    assert set(cfg.universe) == EXPECTED_UNIVERSE
    # v6.3 quality / risk unchanged
    assert cfg.normal_vol.confidence == 82
    assert cfg.normal_vol.quality == 82
    assert cfg.min_expected_rr == Decimal("1.3")
    assert cfg.risk_per_trade_pct == Decimal("0.50")
    assert cfg.max_open_trades == 5
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False


@pytest.mark.unit
def test_xauusd_no_edge_trades_eurusd() -> None:
    book = SymbolStateBook()
    result = scan_multi_asset_portfolio(
        [
            _opp("XAUUSD", reject=True, confidence=40, quality=40),
            _opp("EURUSD", confidence=91, quality=92, direction="SELL", rr="1.8"),
            _opp("GBPUSD", confidence=80, quality=81),
        ],
        state_book=book,
    )
    assert result.best is not None
    assert result.best["symbol"] == "EURUSD"
    assert result.best["direction"] == "SELL"
    assert result.ranked[0]["symbol"] == "EURUSD"


@pytest.mark.unit
def test_rank_all_symbols_execute_best_only() -> None:
    result = scan_multi_asset_portfolio(
        [
            _opp("XAUUSD", confidence=85, quality=86),
            _opp("ETHUSD", confidence=93, quality=94, direction="SELL"),
            _opp("BTCUSD", confidence=88, quality=89),
            _opp("AUDUSD", confidence=70, quality=72),
        ],
        state_book=SymbolStateBook(),
    )
    assert result.best is not None
    assert result.best["symbol"] == "ETHUSD"
    assert len(result.ranked) >= 3


@pytest.mark.unit
def test_per_symbol_cooldown_independent() -> None:
    book = SymbolStateBook()
    book.note_entry("XAUUSD", seconds=120)
    # EURUSD untouched — still eligible
    result = scan_multi_asset_portfolio(
        [
            _opp("XAUUSD", confidence=95, quality=95),
            _opp("EURUSD", confidence=90, quality=91),
        ],
        state_book=book,
    )
    xau = next(r for r in result.rows if r.symbol == "XAUUSD")
    eur = next(r for r in result.rows if r.symbol == "EURUSD")
    assert xau.reject is True
    assert "cooldown" in (xau.reject_reason or "").lower()
    assert eur.reject is False
    assert result.best is not None
    assert result.best["symbol"] == "EURUSD"


@pytest.mark.unit
def test_portfolio_limits_block_best() -> None:
    blocked, reason = check_portfolio_limits(
        open_positions=2,
        max_open_positions=2,
        daily_loss_pct=Decimal("0"),
        max_daily_loss_pct=Decimal("3"),
        exposure_pct=Decimal("0"),
        max_exposure_pct=Decimal("2"),
    )
    assert blocked is True
    assert reason is not None

    result = scan_multi_asset_portfolio(
        [_opp("EURUSD", confidence=95, quality=95)],
        open_positions=2,
        max_open_positions=2,
        state_book=SymbolStateBook(),
    )
    assert result.blocked_by_portfolio is True
    assert result.best is None


@pytest.mark.unit
def test_scheduler_simultaneous_universe() -> None:
    sched = MultiAssetScanScheduler(config=DEFAULT_AI_SCALPING_CONFIG)
    cycle = sched.begin_cycle()
    assert set(cycle["symbols"]) == EXPECTED_UNIVERSE
    assert cycle["mode"] == "simultaneous"
    assert len(sched.symbols_for_cycle()) == len(DEFAULT_SCALPING_UNIVERSE)
    done = sched.complete_cycle(best_symbol="EURUSD", eligible_count=3)
    assert done["last_best_symbol"] == "EURUSD"
    assert done["last_eligible_count"] == 3


@pytest.mark.unit
def test_run_multi_asset_scan_facade() -> None:
    get_symbol_state_book().reset()
    get_multi_asset_scheduler(DEFAULT_AI_SCALPING_CONFIG).reset()
    payload = run_multi_asset_scan(
        [
            _opp("XAUUSD", reject=True),
            _opp("AUDUSD", confidence=92, quality=93, direction="BUY"),
        ]
    )
    assert payload["best"]["symbol"] == "AUDUSD"
    assert payload["scheduler"]["mode"] == "simultaneous"
    assert "AUDUSD" in payload["symbol_state"]["symbols"]
