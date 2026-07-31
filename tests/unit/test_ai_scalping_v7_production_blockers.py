"""Production-blocker validation — v7 multi-asset institutional fixes."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.ai_scalping_dashboard import build_ai_scalping_dashboard
from app.application.services.ai_scalping_portfolio import run_multi_asset_scan
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.live_health import LiveHealthMonitor
from app.domain.institutional_trading.ai_scalping.multi_symbol import (
    rank_scalping_opportunities,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk import (
    aggregate_portfolio_risk,
    portfolio_daily_loss_pct,
    portfolio_exposure_pct,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
    scan_multi_asset_portfolio,
)
from app.domain.institutional_trading.ai_scalping.post_trade_analytics import (
    PostTradeJournal,
    compute_post_trade_analytics,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import SymbolStateBook
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.decision_models import AccountRiskState


def _opp(symbol: str, **kwargs: object) -> dict:
    base = {
        "symbol": symbol,
        "reject": False,
        "ai_confidence": 90,
        "trade_quality": 90,
        "direction": "BUY",
        "expected_rr": "1.6",
        "market_regime": "strong_trend",
        "spread_score": 90,
        "liquidity": 85,
        "atr_pct": "0.90",
        "execution_health_ok": True,
        "setup_family": "bos_continuation",
        "reasons": ("test",),
    }
    base.update(kwargs)
    return base


@pytest.mark.unit
def test_blocker1_exposure_aggregated_across_all_symbols() -> None:
    """Exposure is portfolio-combined, not per-symbol silos."""
    # Two open positions → 2 x risk_per_trade_pct
    exp = portfolio_exposure_pct(
        open_positions=2,
        risk_per_trade_pct=DEFAULT_AI_SCALPING_CONFIG.risk_per_trade_pct,
    )
    assert exp == Decimal("1.00")  # 2 * 0.50
    # Explicit per-position risks sum across symbols
    exp2 = portfolio_exposure_pct(
        open_positions=2,
        risk_per_trade_pct=Decimal("0.50"),
        position_risk_pcts=(Decimal("0.50"), Decimal("0.50"), Decimal("0.50")),
    )
    assert exp2 == Decimal("1.50")

    account = AccountRiskState(
        equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        open_positions=1,
    )
    snap = aggregate_portfolio_risk(account, config=DEFAULT_AI_SCALPING_CONFIG)
    assert snap.exposure_pct == Decimal("0.50")
    assert snap.max_exposure_pct == DEFAULT_AI_SCALPING_CONFIG.max_daily_exposure_pct

    result = scan_multi_asset_portfolio(
        [_opp("EURUSD", ai_confidence=95, trade_quality=95)],
        account=account,
        config=DEFAULT_AI_SCALPING_CONFIG,
        state_book=SymbolStateBook(),
    )
    # 0.50% exposure < 2.00% max and open 1 < 2 → allowed
    assert result.blocked_by_portfolio is False
    assert result.exposure_pct == Decimal("0.50")

    # Hit portfolio exposure ceiling via summed position risks across symbols
    blocked = scan_multi_asset_portfolio(
        [_opp("NAS100", ai_confidence=99, trade_quality=99)],
        account=AccountRiskState(
            equity=Decimal("10000"), daily_pnl=Decimal("0"), open_positions=1
        ),
        position_risk_pcts=(Decimal("0.80"), Decimal("0.80"), Decimal("0.80")),
        state_book=SymbolStateBook(),
    )
    assert blocked.blocked_by_portfolio is True
    assert blocked.best is None
    assert "exposure" in (blocked.portfolio_block_reason or "").lower()


@pytest.mark.unit
def test_blocker2_daily_loss_from_account_ite_ceiling() -> None:
    dd = portfolio_daily_loss_pct(equity=Decimal("10000"), daily_pnl=Decimal("-300"))
    assert dd == Decimal("3.00")
    account = AccountRiskState(
        equity=Decimal("10000"),
        daily_pnl=Decimal("-300"),
        open_positions=0,
    )
    snap = aggregate_portfolio_risk(
        account,
        config=DEFAULT_AI_SCALPING_CONFIG,
        ite_config=DEFAULT_ITE_CONFIG,
    )
    assert snap.daily_loss_pct == Decimal("3.00")
    assert snap.max_daily_loss_pct == DEFAULT_ITE_CONFIG.max_daily_loss_pct

    result = scan_multi_asset_portfolio(
        [_opp("EURUSD", ai_confidence=99, trade_quality=99)],
        account=account,
        ite_config=DEFAULT_ITE_CONFIG,
        state_book=SymbolStateBook(),
    )
    assert result.blocked_by_portfolio is True
    assert "daily loss" in (result.portfolio_block_reason or "").lower()
    assert result.best is None

    payload = run_multi_asset_scan(
        [_opp("GBPUSD", ai_confidence=99, trade_quality=99)],
        account=account,
        ite_config=DEFAULT_ITE_CONFIG,
    )
    assert payload["blocked_by_portfolio"] is True
    assert payload["portfolio_risk"]["daily_loss_pct"] == "3.00"


@pytest.mark.unit
def test_blocker3_cooldown_no_cross_symbol_leak() -> None:
    book = SymbolStateBook()
    book.note_entry("XAUUSD", seconds=300)
    result = scan_multi_asset_portfolio(
        [
            _opp("XAUUSD", ai_confidence=99, trade_quality=99),
            _opp("EURUSD", ai_confidence=90, trade_quality=91),
        ],
        state_book=book,
    )
    xau = next(r for r in result.rows if r.symbol == "XAUUSD")
    eur = next(r for r in result.rows if r.symbol == "EURUSD")
    assert xau.reject is True
    assert eur.reject is False
    assert result.best is not None
    assert result.best["symbol"] == "EURUSD"


@pytest.mark.unit
def test_blocker4_reject_burst_per_symbol_only() -> None:
    mon = LiveHealthMonitor(reject_burst_threshold=3, reject_window_seconds=120)
    mon.record_reject(symbol="XAUUSD")
    mon.record_reject(symbol="XAUUSD")
    mon.record_reject(symbol="XAUUSD")
    ok_xau, why = mon.allow_new_entries(symbol="XAUUSD")
    ok_eur, _ = mon.allow_new_entries(symbol="EURUSD")
    assert ok_xau is False
    assert "XAUUSD" in why
    assert ok_eur is True

    # Global dependency still blocks everyone
    mon.update_dependencies(gateway_ok=False)
    assert mon.allow_new_entries(symbol="EURUSD")[0] is False


@pytest.mark.unit
def test_blocker5_ranking_deterministic_with_ties() -> None:
    rows = [
        _opp("GBPUSD", ai_confidence=90, trade_quality=90, expected_rr="1.5"),
        _opp("EURUSD", ai_confidence=90, trade_quality=90, expected_rr="1.5"),
    ]
    fwd = rank_scalping_opportunities(rows)
    rev = rank_scalping_opportunities(list(reversed(rows)))
    assert [r["symbol"] for r in fwd["ranked"]] == ["EURUSD", "GBPUSD"]
    assert [r["symbol"] for r in rev["ranked"]] == ["EURUSD", "GBPUSD"]
    assert fwd["best"]["symbol"] == rev["best"]["symbol"] == "EURUSD"


@pytest.mark.unit
def test_blocker6_metrics_per_symbol_and_portfolio() -> None:
    journal = PostTradeJournal()
    journal.record(
        compute_post_trade_analytics(
            symbol="XAUUSD",
            direction="buy",
            entry=Decimal("2300"),
            exit_price=Decimal("2305"),
            stop_distance=Decimal("5"),
            pnl="50",
        )
    )
    journal.record(
        compute_post_trade_analytics(
            symbol="EURUSD",
            direction="sell",
            entry=Decimal("1.10"),
            exit_price=Decimal("1.11"),
            stop_distance=Decimal("0.01"),
            pnl="-10",
        )
    )
    portfolio = journal.performance_snapshot()
    assert portfolio["scope"] == "portfolio"
    assert portfolio["trades"] == 2
    xau = journal.performance_snapshot(symbol="XAUUSD")
    assert xau["scope"] == "symbol"
    assert xau["trades"] == 1
    assert xau["win_rate"] == 100.0
    by_sym = journal.performance_by_symbol()
    assert "XAUUSD" in by_sym and "EURUSD" in by_sym

    dash = build_ai_scalping_dashboard()
    assert "performance_by_symbol" in dash
    assert dash["performance_metrics"].get("scope") == "portfolio"
