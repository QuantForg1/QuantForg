"""Unit tests — offline institutional execution validation (no live order_send)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.services.institutional_execution_validation import (
    _is_production_quality_setup,
    report_to_markdown,
    run_institutional_execution_validation,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    DecisionAction,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    NewsProtectionStatus,
    SessionFilterResult,
    TradeQualityFactor,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.value_objects.identity import SymbolCode

AS_OF = datetime(2026, 6, 15, 14, 30, tzinfo=UTC)
INPUT_HASH = "execval_snap_hash_00112233445566778899aabb"


def _structure(direction: TrendDirection = TrendDirection.UP) -> StructureSnapshot:
    code = SymbolCode(value="XAUUSD")
    return StructureSnapshot(
        symbol_code=code,
        timeframe=Timeframe.H1,
        as_of=AS_OF,
        swings=(),
        nodes=(),
        trend=TrendState(
            symbol_code=code,
            timeframe=Timeframe.H1,
            direction=direction,
            as_of=AS_OF,
            last_structure_role=StructureRole.HIGHER_HIGH,
            swing_count=4,
        ),
        breaks_of_structure=(),
        changes_of_character=(),
    )


def _snapshot(*, aligned: bool = True) -> MarketAnalysisSnapshot:
    direction = TrendDirection.UP
    return MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=AS_OF,
        config_version="ite-v1.0.0",
        input_hash=INPUT_HASH,
        structure_by_tf={"H1": _structure(direction)},
        primary_structure=_structure(direction),
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=TrendSnapshot(
            macro_bias=direction,
            primary=direction,
            entry=direction,
            execution=direction,
            alignment_score=95 if aligned else 40,
            aligned=aligned,
            frames={"H4": direction.value},
            why="test",
        ),
        session=SessionFilterResult(
            session=MarketSession.LONDON_NY_OVERLAP,
            allowed=True,
            reason="ok",
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="clear"),
        trade_quality=TradeQualityScore(
            total=92,
            passed=True,
            band="high_confidence",
            factors=(TradeQualityFactor(code="trend", weight=20, score=92),),
        ),
        spread=Decimal("0.30"),
    )


def _account() -> AccountRiskState:
    return AccountRiskState(
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        weekly_pnl=Decimal("0"),
        open_positions=0,
        already_in_trade=False,
        consecutive_losses=0,
        cooldown_active=False,
        market_open=True,
        atr=Decimal("5"),
        mid_price=Decimal("2300"),
        free_margin=Decimal("10000"),
    )


def _buy_decision(*, quality: int = 92, lots: Decimal = Decimal("0.05")):
    from dataclasses import replace

    snap = _snapshot()
    conf = ConfluenceResult(
        confidence=88,
        direction=TradeDirection.BUY,
        reasons=("aligned",),
        rejected_rules=(),
        input_hash="conf1",
        band="tradable",
        passed=True,
        factors={"mtf": 95},
    )
    acct = _account()
    elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=acct,
        risk_allowed=True,
    )
    decision = TradeDecisionEngine(config=ITEConfig()).decide(
        snapshot=snap,
        confluence=conf,
        eligibility=elig,
        account=acct,
        risk_score=20,
        approved_lots=lots,
    )
    if quality != decision.quality:
        decision = replace(decision, quality=quality)
    return snap, decision


@pytest.mark.unit
def test_production_quality_gate_rejects_low_quality() -> None:
    snap, decision = _buy_decision(quality=79)
    ok, reason = _is_production_quality_setup(snap, decision)
    assert ok is False
    assert "quality" in reason


@pytest.mark.unit
def test_production_quality_gate_rejects_below_min_lot() -> None:
    snap, decision = _buy_decision(lots=Decimal("0.00"))
    ok, reason = _is_production_quality_setup(snap, decision)
    assert ok is False
    assert "approved_lots" in reason


@pytest.mark.unit
def test_production_quality_gate_accepts_full_pass() -> None:
    snap, decision = _buy_decision()
    assert decision.action in {DecisionAction.BUY, DecisionAction.SELL}
    ok, reason = _is_production_quality_setup(snap, decision)
    assert ok is True
    assert "satisfied" in reason


@pytest.mark.unit
@pytest.mark.asyncio
async def test_offline_validation_does_not_call_live_order_send() -> None:
    """Smoke: short walk stays offline and preserves production gates."""
    report = await run_institutional_execution_validation(
        days=30,
        max_evaluations=40,
        max_valid_setups=1,
        equity=Decimal("10000"),
    )
    assert report["live_order_send_called"] is False
    assert report["strategy_modified"] is False
    assert report["thresholds_modified"] is False
    assert report["production_gates"]["min_quality"] == (
        DEFAULT_ITE_CONFIG.min_trade_quality_score
    )
    assert report["production_gates"]["min_confluence"] == (
        DEFAULT_ITE_CONFIG.min_confluence_score
    )
    md = report_to_markdown(report)
    assert "Institutional Execution Validation Report" in md
    if report["valid_production_setup_exists"]:
        setup = report["valid_setups"][0]
        stages = {s["stage"]: s["status"] for s in setup["execution_trace"]["stages"]}
        assert stages["Quality"] == "PASS"
        assert stages["Confluence"] == "PASS"
        assert stages["Safety"] == "PASS"
        assert stages["Execution Decision"] == "EXECUTE_TRADE"
        assert stages["OMS"] == "PASS"
        assert "Order Sent" in stages["MT5 Gateway"]
        assert "Order Filled" in stages["Broker"]
