"""Unit tests — Institutional Alpha Engine v5."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.alpha_engine.config import DEFAULT_ALPHA_CONFIG
from app.domain.institutional_trading.alpha_engine.correlation import (
    correlation_matrix,
    may_open_with_correlation,
)
from app.domain.institutional_trading.alpha_engine.ranking import (
    rank_opportunities,
    score_opportunity,
    top_executable,
)
from app.domain.institutional_trading.alpha_engine.risk_allocation import (
    SmartRecoveryState,
    allocate_risk_pct,
    min_score_with_recovery,
)
from app.domain.institutional_trading.alpha_engine.scanner import (
    SymbolMarketFacts,
    scan_universe,
)


@pytest.mark.unit
def test_opportunity_ranking_orders_highest_first() -> None:
    a = score_opportunity(
        symbol="EURUSD",
        ai_confidence=90,
        trend_strength=80,
        momentum=75,
        liquidity=70,
        volatility=60,
        spread_score=90,
        expected_rr=Decimal("2.0"),
        session_score=100,
        direction="BUY",
    )
    b = score_opportunity(
        symbol="GBPUSD",
        ai_confidence=60,
        trend_strength=50,
        momentum=50,
        liquidity=50,
        volatility=50,
        spread_score=50,
        expected_rr=Decimal("1.0"),
        session_score=40,
        direction="SELL",
    )
    ranked = rank_opportunities([b, a])
    assert ranked[0].symbol == "EURUSD"
    assert ranked[0].rank == 1
    assert ranked[0].opportunity_score >= ranked[1].opportunity_score


@pytest.mark.unit
def test_correlation_blocks_eurusd_gbpusd() -> None:
    blocked = may_open_with_correlation(
        candidate_symbol="GBPUSD",
        open_symbols=["EURUSD"],
    )
    assert blocked.allow is False
    ok = may_open_with_correlation(
        candidate_symbol="USDJPY",
        open_symbols=["EURUSD"],
    )
    assert ok.allow is True


@pytest.mark.unit
def test_correlation_blocks_nas_us30() -> None:
    blocked = may_open_with_correlation(
        candidate_symbol="US30",
        open_symbols=["NAS100"],
    )
    assert blocked.allow is False


@pytest.mark.unit
def test_dynamic_risk_allocation_by_quality() -> None:
    high = allocate_risk_pct(90, recovery=SmartRecoveryState())
    mid = allocate_risk_pct(80, recovery=SmartRecoveryState())
    low = allocate_risk_pct(73, recovery=SmartRecoveryState())
    assert high.risk_pct == DEFAULT_ALPHA_CONFIG.risk_pct_high
    assert mid.risk_pct == DEFAULT_ALPHA_CONFIG.risk_pct_mid
    assert low.risk_pct == DEFAULT_ALPHA_CONFIG.risk_pct_low
    assert high.risk_pct > mid.risk_pct > low.risk_pct


@pytest.mark.unit
def test_smart_recovery_reduces_risk_and_raises_min_score() -> None:
    rec = SmartRecoveryState()
    rec.record_outcome(win=False)
    assert rec.active()
    alloc = allocate_risk_pct(90, recovery=rec)
    assert alloc.recovery_active
    assert alloc.risk_pct < DEFAULT_ALPHA_CONFIG.risk_pct_high
    assert min_score_with_recovery(recovery=rec) > DEFAULT_ALPHA_CONFIG.min_opportunity_score
    rec.record_outcome(win=True)
    assert rec.active() is False


@pytest.mark.unit
def test_scan_universe_selects_top_non_correlated() -> None:
    facts = [
        SymbolMarketFacts(
            symbol="EURUSD",
            mid=Decimal("1.1"),
            spread=Decimal("0.0001"),
            session="london",
            trend_strength=85,
            momentum=80,
            liquidity=80,
            volatility=60,
            ai_confidence=88,
            expected_rr=Decimal("2"),
            direction="BUY",
        ),
        SymbolMarketFacts(
            symbol="GBPUSD",
            mid=Decimal("1.25"),
            spread=Decimal("0.0002"),
            session="london",
            trend_strength=84,
            momentum=79,
            liquidity=78,
            volatility=60,
            ai_confidence=87,
            expected_rr=Decimal("1.9"),
            direction="BUY",
        ),
        SymbolMarketFacts(
            symbol="XAUUSD",
            mid=Decimal("2400"),
            spread=Decimal("0.2"),
            session="london",
            trend_strength=70,
            momentum=70,
            liquidity=70,
            volatility=70,
            ai_confidence=75,
            expected_rr=Decimal("1.5"),
            direction="BUY",
        ),
    ]
    result = scan_universe(facts, open_symbols=())
    assert result.opportunities[0].rank == 1
    # Top selected should not include both EUR and GBP
    selected_syms = {o.symbol for o in result.selected}
    assert not ({"EURUSD", "GBPUSD"} <= selected_syms)


@pytest.mark.unit
def test_correlation_matrix_marks_groups() -> None:
    m = correlation_matrix(["EURUSD", "GBPUSD", "USDJPY"])
    assert m["EURUSD"]["GBPUSD"] == 1.0
    assert m["EURUSD"]["USDJPY"] == 0.0
    assert m["EURUSD"]["EURUSD"] == 1.0


@pytest.mark.unit
def test_top_executable_respects_min_score() -> None:
    weak = score_opportunity(
        symbol="BTCUSD",
        ai_confidence=40,
        trend_strength=40,
        momentum=40,
        liquidity=40,
        volatility=40,
        spread_score=40,
        expected_rr=Decimal("1"),
        session_score=40,
        direction="BUY",
    )
    ranked = rank_opportunities([weak])
    assert top_executable(ranked) == []
