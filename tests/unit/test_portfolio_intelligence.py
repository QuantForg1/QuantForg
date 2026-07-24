"""Unit tests for Portfolio Intelligence — no invented fills / no execution."""

from __future__ import annotations

import pytest

from app.application.services.portfolio_intelligence_lab import PortfolioIntelligenceService
from app.domain.portfolio_intelligence.statistics import (
    expected_shortfall,
    historical_var,
    pearson,
)
from app.domain.portfolio_intelligence.taxonomy import (
    classify_currency,
    classify_sector,
)


@pytest.mark.unit
class TestStatistics:
    def test_var_cvar_need_enough_samples(self) -> None:
        assert historical_var([1, 2, 3]) is None
        pnls = [-100, -50, -20, -10, 5, 10, 20, 30, 40, 50]
        var = historical_var(pnls, 0.9)
        assert var is not None and var >= 0
        cvar = expected_shortfall(pnls, 0.9)
        assert cvar is not None and cvar >= var

    def test_pearson_perfect(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert pearson(xs, ys) == pytest.approx(1.0)

    def test_taxonomy(self) -> None:
        assert classify_sector("EURUSD") == "fx"
        assert classify_sector("XAUUSD") == "metals"
        assert classify_currency("EURUSD") == "USD"


@pytest.mark.unit
class TestPortfolioIntelligenceService:
    def setup_method(self) -> None:
        self.svc = PortfolioIntelligenceService()

    def test_risk_from_positions(self) -> None:
        result = self.svc.compute_risk(
            account={
                "equity": "10000",
                "balance": "10000",
                "margin": "1000",
                "leverage": 100,
                "currency": "USD",
            },
            positions=[
                {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "volume": "1.0",
                    "open_price": "1.10",
                    "current_price": "1.10",
                    "profit": "0",
                },
                {
                    "symbol": "XAUUSD",
                    "side": "sell",
                    "volume": "0.1",
                    "open_price": "2000",
                    "current_price": "2000",
                    "profit": "-5",
                },
            ],
            deals=[{"profit": str(v)} for v in [-40, -20, -10, 5, 10, 15, 20, 25]],
        )
        assert result["status"] == "available"
        assert result["metrics"]["exposure"] > 0
        assert result["metrics"]["margin_usage_pct"] == pytest.approx(10.0)
        assert any(s["sector"] == "fx" for s in result["sector_allocation"])
        assert result["metrics"]["portfolio_var"] is not None

    def test_unavailable_portfolio(self) -> None:
        result = self.svc.compute_risk(
            account=None,
            positions=[],
            deals=[],
            portfolio_available=False,
            portfolio_unavailable_reason="MT5 not connected",
        )
        assert result["status"] == "unavailable"

    def test_stress_marks_empty_positions(self) -> None:
        result = self.svc.compute_stress(
            account={"equity": "10000", "margin": "0"},
            positions=[],
            deals=[],
        )
        flash = next(s for s in result["scenarios"] if s["key"] == "flash_crash")
        assert flash["status"] == "unavailable"
        hist = next(
            s for s in result["scenarios"] if s["key"] == "historical_worst_day"
        )
        assert hist["status"] == "unavailable"

    def test_stress_model_on_positions(self) -> None:
        result = self.svc.compute_stress(
            account={"equity": "10000", "margin": "500"},
            positions=[
                {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "volume": "1",
                    "current_price": "1.2",
                    "open_price": "1.2",
                    "profit": "0",
                }
            ],
            deals=[{"profit": "-100", "time": "2024-01-01T00:00:00+00:00"}],
        )
        flash = next(s for s in result["scenarios"] if s["key"] == "flash_crash")
        assert flash["status"] == "available"
        assert flash["impact_pnl"] < 0
        assert flash["autonomous_trading"] is False

    def test_correlation_unavailable_without_overlap(self) -> None:
        result = self.svc.compute_correlation(
            positions=[{"symbol": "EURUSD"}, {"symbol": "GBPUSD"}],
            deals=[],
        )
        assert result["status"] == "unavailable"

    def test_correlation_with_overlap(self) -> None:
        deals = []
        for i in range(1, 12):
            day = f"2024-01-{i:02d}T12:00:00+00:00"
            deals.append({"symbol": "EURUSD", "profit": str(i), "time": day})
            deals.append({"symbol": "GBPUSD", "profit": str(i * 2), "time": day})
        result = self.svc.compute_correlation(
            positions=[{"symbol": "EURUSD"}, {"symbol": "GBPUSD"}],
            deals=deals,
        )
        assert result["status"] == "available"
        assert result["diversification_score"] is not None
        assert result["heatmap"]

    def test_optimizer_never_trades(self) -> None:
        result = self.svc.compute_optimizer(
            positions=[
                {
                    "symbol": "EURUSD",
                    "volume": "1",
                    "current_price": "1.1",
                    "open_price": "1.1",
                },
                {
                    "symbol": "GBPUSD",
                    "volume": "1",
                    "current_price": "1.3",
                    "open_price": "1.3",
                },
            ],
            deals=[],
            max_allocation_pct=50,
            max_risk_pct=80,
        )
        assert result["autonomous_trading"] is False
        assert result["status"] == "available"
        assert result["recommendations"]
        for rec in result["recommendations"]:
            assert "explanation" in rec
            assert "reason" in rec["explanation"]
            assert "data_source" in rec["explanation"]

    def test_journal_and_attribution(self) -> None:
        lab = self.svc.build_lab(
            account={
                "equity": "10000",
                "balance": "10000",
                "margin": "0",
                "leverage": 1,
            },
            positions=[],
            deals=[
                {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "profit": "50",
                    "time": "2024-06-03T10:00:00+00:00",
                },
                {
                    "symbol": "EURUSD",
                    "side": "sell",
                    "profit": "-20",
                    "time": "2024-06-03T15:00:00+00:00",
                },
                {
                    "symbol": "XAUUSD",
                    "side": "buy",
                    "profit": "10",
                    "time": "2024-06-04T02:00:00+00:00",
                    "opened_at": "2024-06-04T01:00:00+00:00",
                    "closed_at": "2024-06-04T02:00:00+00:00",
                },
            ],
        )
        assert lab["journal"]["status"] == "available"
        assert lab["journal"]["metrics"]["win_rate"] is not None
        assert lab["attribution"]["status"] == "available"
        assert lab["attribution"]["by_symbol"]
        assert lab["execution_policy"]["autonomous_trading"] is False
