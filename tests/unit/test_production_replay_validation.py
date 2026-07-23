"""Unit tests — Production Replay & Validation (simulation only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.production_replay_validation import (
    ALLOWED_SESSIONS,
    build_synthetic_bars,
    report_to_markdown,
    run_production_replay,
)
from app.domain.institutional_trading.session_filter import classify_session_utc


@pytest.mark.unit
class TestProductionReplayValidation:
    @pytest.mark.asyncio
    async def test_default_small_window_never_fabricates_orders(self) -> None:
        """days=3 is below the ~8-day H4 history floor.

        Must not crash and may legitimately produce zero opportunities.
        """
        report = await run_production_replay(days=3, max_evaluations=5)

        assert report["simulation_only"] is True
        assert report["order_send_called"] is False
        assert report["mt5_order_send_invoked"] is False
        assert report["strategy_engine_modified"] is False
        assert report["risk_engine_modified"] is False
        assert report["safety_engine_modified"] is False
        assert "opportunities" in report
        assert "statistics" in report
        assert isinstance(report["opportunities"], list)

        for opp in report["opportunities"]:
            assert opp["session"] in {s.value for s in ALLOWED_SESSIONS}

    @pytest.mark.asyncio
    async def test_sufficient_history_produces_bounded_opportunities(self) -> None:
        """days=15 clears the H4 history floor — expect a bounded, non-empty walk."""
        max_evaluations = 5
        report = await run_production_replay(
            days=15, max_evaluations=max_evaluations
        )

        opportunities = report["opportunities"]
        assert len(opportunities) <= max_evaluations
        assert len(opportunities) > 0

        allowed = {s.value for s in ALLOWED_SESSIONS}
        for opp in opportunities:
            assert opp["session"] in allowed
            assert opp["action"] in {"NO_TRADE", "WATCH", "BUY", "SELL"}
            assert opp["risk_result"] in {"PASS", "FAIL"}
            assert opp["safety_result"] in {"PASS", "BLOCK"}
            assert opp["would_reach_oms"] in {"YES", "NO"}
            assert opp["would_reach_mt5"] == opp["would_reach_oms"]
            if opp["action"] in {"BUY", "SELL"}:
                assert opp["would_reach_oms"] == "YES"
            else:
                assert opp["would_reach_oms"] == "NO"
                assert opp["rejection_reason"]

        stats = report["statistics"]
        assert stats["total_evaluations"] == len(opportunities)
        assert stats["signals"] + stats["rejected"] == len(opportunities)
        assert stats["avg_latency_ms"] >= 0

        # Markdown export must render without error and mention the header.
        md = report_to_markdown(report)
        assert md.startswith("# Production Replay & Validation Report")
        assert "order_send_called: False" in md

    @pytest.mark.asyncio
    async def test_injected_bars_by_tf_used_over_synthetic(self) -> None:
        """Injecting bars_by_tf (M15 + M5 only) should derive H1/H4 and still walk."""
        from app.domain.market_data.timeframe import Timeframe

        base_t = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)  # Monday
        bars = build_synthetic_bars(days=15, end=base_t + timedelta(days=15))
        injected = {
            Timeframe.M15: bars[Timeframe.M15],
            Timeframe.M5: bars[Timeframe.M5],
        }

        report = await run_production_replay(
            days=15, max_evaluations=3, bars_by_tf=injected
        )
        assert report["order_send_called"] is False
        assert isinstance(report["opportunities"], list)
        assert len(report["opportunities"]) <= 3

    def test_session_classifier_matches_allowed_set(self) -> None:
        overlap = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
        assert classify_session_utc(overlap) in ALLOWED_SESSIONS

        weekend = datetime(2026, 1, 4, 14, 0, tzinfo=UTC)  # Sunday
        assert classify_session_utc(weekend) not in ALLOWED_SESSIONS
