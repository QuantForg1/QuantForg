"""Unit tests — XAUUSD strategy audit (read-only; never mutates strategy)."""

from __future__ import annotations

import pytest

from app.application.services.xauusd_strategy_audit import (
    run_xauusd_strategy_audit,
    score_xauusd_signal,
)
from app.domain.institutional_trading.xauusd_strategy_audit import (
    audit_strategy_components,
    build_strategy_audit,
    score_signal_quality,
)


@pytest.mark.unit
class TestXauusdStrategyAudit:
    def test_components_cover_smc_stack(self) -> None:
        comps = audit_strategy_components()
        names = {c.component for c in comps}
        for required in (
            "Smart Money Concepts",
            "BOS",
            "CHOCH",
            "Order Blocks",
            "Fair Value Gaps",
            "Liquidity Sweeps",
            "Market Structure",
            "Trend Filter",
            "Session Filter",
            "Volatility Filter",
        ):
            assert required in names

    def test_signal_quality_example_score(self) -> None:
        scored = score_signal_quality(
            {
                "mtf_aligned": True,
                "bos": True,
                "choch": False,
                "liquidity_sweep": True,
                "order_block": True,
                "fair_value_gap": True,
                "session_allowed": True,
                "spread_acceptable": True,
                "volatility_acceptable": True,
            }
        )
        assert scored is not None
        assert scored.score == 92
        assert "SMC aligned" in scored.reasons
        assert "Liquidity sweep confirmed" in scored.reasons
        assert "Spread acceptable" in scored.reasons
        out = score_xauusd_signal(
            {
                "mtf_aligned": True,
                "bos": True,
                "liquidity_sweep": True,
                "order_block": True,
                "fair_value_gap": True,
                "session_allowed": True,
                "spread_acceptable": True,
                "volatility_acceptable": True,
            }
        )
        assert out["display"].startswith("Signal Quality")

    def test_sessions_never_mixed(self) -> None:
        trades = [
            {"session": "london", "pnl": 10, "win": True, "rr": 2},
            {"session": "tokyo", "pnl": -5, "win": False, "rr": -1},
            {"session": "overlap", "pnl": 8, "win": True, "rr": 1.5},
        ]
        report = build_strategy_audit(trades=trades)
        buckets = report.session_performance["buckets"]
        assert buckets["london"]["trades"] == 1
        assert buckets["tokyo"]["trades"] == 1
        assert buckets["overlap"]["trades"] == 1
        assert buckets["london"]["mixed_with_other_buckets"] is False

    def test_recommendations_only_never_auto(self) -> None:
        payload = run_xauusd_strategy_audit(trades=[], decisions=[])
        assert payload["never_auto_modifies_strategy"] is True
        assert payload["never_auto_applies"] is True
        assert any("London" in r for r in payload["recommendations"])
        assert any("News" in r for r in payload["recommendations"])

    def test_no_trade_insufficient_without_decisions(self) -> None:
        report = build_strategy_audit()
        assert report.no_trade_audit["status"] == "insufficient_data"
