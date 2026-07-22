"""Unit tests — Institutional Performance Intelligence (advisory only)."""

from __future__ import annotations

import pytest

from app.domain.performance_intelligence.dashboard import (
    build_performance_intelligence,
    compute_no_trade_analytics,
    compute_performance_dashboard,
    compute_signal_analytics,
    compute_time_analytics,
    enrich_regime_analytics,
    enrich_session_analytics,
)


def _trades() -> list[dict]:
    return [
        {
            "net_pnl": 20,
            "session": "london",
            "regime": "trend",
            "r_multiple": 2.0,
            "opened_at": "2026-07-01T08:00:00+00:00",
            "closed_at": "2026-07-01T09:00:00+00:00",
            "bos": True,
            "order_block": True,
            "liquidity_sweep": True,
            "confluence_score": 92,
            "exit_cause": "tp",
        },
        {
            "net_pnl": -8,
            "session": "new_york",
            "regime": "range",
            "r_multiple": -0.8,
            "opened_at": "2026-07-01T14:00:00+00:00",
            "closed_at": "2026-07-01T14:30:00+00:00",
            "choch": True,
            "fair_value_gap": True,
            "confluence_score": 81,
            "exit_cause": "sl",
        },
        {
            "net_pnl": 12,
            "session": "overlap",
            "regime": "high_volatility",
            "r_multiple": 1.5,
            "opened_at": "2026-07-01T13:00:00+00:00",
            "closed_at": "2026-07-01T15:00:00+00:00",
            "bos": True,
            "liquidity_sweep": True,
            "order_block": True,
            "confluence_score": 88,
        },
    ]


@pytest.mark.unit
class TestPerformanceIntelligence:
    def test_dashboard_metrics(self) -> None:
        dash = compute_performance_dashboard(_trades())
        assert dash["status"] == "available"
        m = dash["metrics"]
        assert m["total_trades"] == 3
        assert m["winning_trades"] == 2
        assert m["losing_trades"] == 1
        assert m["win_rate"] == pytest.approx(2 / 3, rel=1e-3)
        assert m["profit_factor"] is not None
        assert m["expectancy"] is not None
        assert m["consecutive_wins"] is not None

    def test_sessions_never_mixed(self) -> None:
        sessions = enrich_session_analytics(_trades())
        assert sessions["sessions"]["london"]["trade_count"] == 1
        assert sessions["sessions"]["new_york"]["trade_count"] == 1
        assert sessions["sessions"]["overlap"]["trade_count"] == 1
        assert sessions["sessions"]["tokyo"]["trade_count"] == 0

    def test_regimes_separate(self) -> None:
        regimes = enrich_regime_analytics(_trades())
        assert regimes["regimes"]["trend"]["trade_count"] == 1
        assert regimes["regimes"]["range"]["trade_count"] == 1
        assert regimes["regimes"]["high_volatility"]["trade_count"] == 1

    def test_signal_combinations(self) -> None:
        signals = compute_signal_analytics(_trades())
        assert signals["tagged_trades"] == 3
        assert signals["best_combination"] is not None
        assert "bos" in signals["signals"]

    def test_no_trade_research_only(self) -> None:
        no_trade = compute_no_trade_analytics(
            [
                {"decision": "NO_TRADE", "reason": "spread too wide"},
                {"decision": "BUY", "reason": "ok"},
                {"action": "WATCH", "reason": "mtf_not_aligned"},
            ]
        )
        assert no_trade["no_trade_count"] == 2
        assert no_trade["research_only"] is True
        assert no_trade["estimated_bad_trades_avoided"]["status"] == "research_only"

    def test_time_analytics(self) -> None:
        time_a = compute_time_analytics(_trades())
        assert time_a["metrics"]["average_trade_duration_seconds"] is not None
        assert time_a["metrics"]["fastest_trade_seconds"] is not None

    def test_full_pack_recommendations_only(self) -> None:
        pack = build_performance_intelligence(trades=_trades(), period="weekly")
        assert pack["never_modifies_strategy"] is True
        assert pack["advisory_only"] is True
        assert isinstance(pack["recommendations"], list)
        assert pack["report"]["period"] == "weekly"

    def test_empty_never_fabricates(self) -> None:
        dash = compute_performance_dashboard([])
        assert dash["status"] == "unavailable"
        pack = build_performance_intelligence(trades=[])
        assert pack["performance"]["status"] == "unavailable"
