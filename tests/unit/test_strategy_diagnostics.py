"""Unit tests — Strategy Diagnostics (advisory / observation only)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.strategy_diagnostics import (
    compute_diagnostics_statistics,
    extract_cycle_diagnostics,
    generate_smart_insights,
    reason_label,
    reset_strategy_diagnostics_store,
)
from app.domain.institutional_trading.decision_models import (
    ConfluenceResult,
    DecisionAction,
    EligibilityResult,
    TradeDecision,
    TradeDirection,
)
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    NewsProtectionStatus,
    SessionFilterResult,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.market_context.enums import MarketSession
from app.domain.market_structure.enums import TrendDirection


def _snapshot(*, quality: int = 58, aligned: bool = False) -> MarketAnalysisSnapshot:
    return MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=datetime.now(UTC),
        config_version="ite-v1.0.0",
        input_hash="abc",
        structure_by_tf={},
        primary_structure=None,
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=TrendSnapshot(
            macro_bias=TrendDirection.UP,
            primary=TrendDirection.DOWN if not aligned else TrendDirection.UP,
            entry=TrendDirection.UP,
            execution=TrendDirection.UP,
            alignment_score=40 if not aligned else 90,
            aligned=aligned,
            why="test",
        ),
        session=SessionFilterResult(
            session=MarketSession.LONDON,
            allowed=True,
            reason="London session",
        ),
        news=NewsProtectionStatus(enabled=True, blocked=False, reason="clear"),
        trade_quality=TradeQualityScore(
            total=quality, passed=quality >= 80, band="reject"
        ),
        spread=Decimal("0.20"),
    )


def _decision(
    snapshot: MarketAnalysisSnapshot,
    *,
    quality: int = 58,
    confidence: int = 55,
) -> TradeDecision:
    confluence = ConfluenceResult(
        confidence=confidence,
        direction=TradeDirection.NONE,
        reasons=("Trade quality 58 below gate", "MTF not aligned"),
        rejected_rules=(
            "quality_below_threshold",
            "mtf_not_aligned",
            "confidence_below_threshold",
        ),
        input_hash="x",
        band="reject",
        passed=False,
        factors={
            "mtf": 20,
            "m15": 0,
            "structure": 25,
            "liquidity": 20,
            "order_block": 20,
            "fvg": 25,
            "quality": quality,
            "session": 100,
            "news": 100,
            "spread": 100,
            "volatility": 60,
            "drawdown": 80,
        },
    )
    eligibility = EligibilityResult(
        eligible=False,
        checks={},
        rejection_reasons=("quality_below_threshold",),
    )
    return TradeDecision(
        action=DecisionAction.NO_TRADE,
        direction=TradeDirection.NONE,
        confidence=confidence,
        quality=quality,
        risk_score=0,
        reasons=confluence.reasons,
        invalidations=(),
        entry_zone=None,
        stop_zone=None,
        target_zone=None,
        estimated_rr=None,
        expected_duration="",
        confluence=confluence,
        eligibility=eligibility,
        input_hash="x",
        config_version="ite-v1.0.0",
        symbol="XAUUSD",
        as_of=datetime.now(UTC),
        id=uuid4(),
    )


@pytest.mark.unit
class TestStrategyDiagnostics:
    def setup_method(self) -> None:
        reset_strategy_diagnostics_store()

    def test_reason_labels(self) -> None:
        assert reason_label("quality_below_threshold") == "Quality below threshold"
        assert reason_label("mtf_not_aligned") == "MTF misalignment"

    def test_extract_quality_difference(self) -> None:
        snap = _snapshot(quality=58)
        decision = _decision(snap, quality=58, confidence=55)
        row = extract_cycle_diagnostics(
            snapshot=snap,
            decision=decision,
            cycle_outcome="no_trade",
            decision_action="NO_TRADE",
            decision_reasons=decision.reasons,
            market_context_diagnostics={"volume": "42"},
        )
        assert row["market_session"] == "london"
        assert row["quality"]["score"] == 58
        assert row["quality"]["required"] == 80
        assert row["quality"]["difference"] == -22
        assert row["confluence"]["total"] == 55
        assert row["confluence"]["required"] == 80
        assert row["confluence"]["components"]["order_block"] == 20
        assert row["confluence"]["components"]["fair_value_gap"] == 25
        assert row["confluence"]["components"]["volume"] == 70
        assert row["trend"]["h4"] == "up"
        assert row["trend"]["h1"] == "down"
        assert row["rejection"]["primary"] == "mtf_not_aligned"
        assert "Quality below threshold" in row["rejection"]["all_labels"]
        assert row["rejected"] is True
        assert row["executed"] is False
        assert row["advisory_only"] is True

    @pytest.mark.trading_core
    def test_buy_take_is_not_executed_without_oms_forward(self) -> None:
        snap = _snapshot(quality=80)
        decision = _decision(snap, quality=80, confidence=80)
        row = extract_cycle_diagnostics(
            snapshot=snap,
            decision=decision,
            cycle_outcome="aborted",
            decision_action="BUY",
            abort_reason="DAILY_LOSS_BLOCK",
            forwarded_to_oms=False,
        )
        assert row["take"] is True
        assert row["executed"] is False
        assert row["forwarded_to_oms"] is False

    @pytest.mark.trading_core
    def test_hourly_scan_rates_separate_take_from_fill(self) -> None:
        from app.application.services.strategy_diagnostics import hourly_scan_rates

        cycles = [
            {
                "recorded_at": "2026-08-27T14:00:00+00:00",
                "decision_action": "SELL",
                "take": True,
                "forwarded_to_oms": False,
                "executed": False,
                "opportunity_score": 71,
                "opportunity_threshold": 70,
                "setup_state": "TAKE",
                "rejection": {"primary": "DAILY_LOSS_BLOCK"},
            },
            {
                "recorded_at": "2026-08-27T14:01:00+00:00",
                "decision_action": "WAIT",
                "take": False,
                "forwarded_to_oms": False,
                "opportunity_score": 44,
                "setup_state": "WAIT",
                "rejection": {"primary": "WAIT_CHASE"},
            },
        ]
        rates = hourly_scan_rates(
            cycles, now=datetime(2026, 8, 27, 14, 30, tzinfo=UTC)
        )
        assert rates["scans"] == 2
        assert rates["candidate_setups"] == 1
        assert rates["take_count"] == 1
        assert rates["executed_count"] == 0
        assert rates["WAIT_CHASE_count"] == 1
        assert rates["SELL_count"] == 1
        assert rates["executions_per_hour"] == 0.0
        assert rates["DAILY_LOSS_BLOCK"] == 1
        assert rates["take_count"] == 1
        assert rates["mt5_fills"] == 0

    def test_statistics_and_insights(self) -> None:
        snap = _snapshot(quality=58)
        decision = _decision(snap)
        cycles = [
            extract_cycle_diagnostics(
                snapshot=snap,
                decision=decision,
                cycle_outcome="no_trade",
                decision_action="NO_TRADE",
                decision_reasons=decision.reasons,
            )
            for _ in range(5)
        ]
        stats = compute_diagnostics_statistics(cycles, window=100)
        assert stats["signals_rejected"] == 5
        assert stats["signals_executed"] == 0
        assert stats["execution_rate_pct"] == 0.0
        assert stats["average_quality"] == 58.0
        assert stats["top_rejection_reasons"][0]["code"] == "mtf_not_aligned"
        insights = generate_smart_insights(stats, cycles[-1])
        assert any("Most signals fail because" in line for line in insights)
        assert any("never lowers thresholds" in line.lower() for line in insights)

    def test_store_ring_buffer(self) -> None:
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        store = get_strategy_diagnostics_store()
        snap = _snapshot()
        decision = _decision(snap)
        for _ in range(3):
            store.record_from_artefacts(
                snapshot=snap,
                decision=decision,
                cycle_outcome="no_trade",
                decision_action="NO_TRADE",
            )
        payload = store.snapshot(limit=100)
        assert payload["mutates_engines"] is False
        assert payload["statistics"]["cycles_in_window"] == 3
        assert payload["latest"]["quality"]["difference"] == -22
        assert len(payload["smart_insights"]) >= 1
